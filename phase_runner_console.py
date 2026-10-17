"""Phase Runner 1.7.2: control-room consoles with their source UVs (user report, 18 October 2026).

The two control-room console sets (console_ship_center_tower_01 and
ship_console_control_med_v1_off, 8 placements) were drawn from a 25%
budget simplification with a 2-unit error that merged UV seams, so their
screen and panel textures look stretched. Their drawn triangles are removed
and replaced by the source mesh: the towers at LOD0 (their only LOD), the
side consoles simplified by meshoptimizer at 0.5% relative error with UVs
weighted, keeping exact source vertices. Lightmap coordinates and page come
come from the old console surface under each new triangle: the nearest old
triangle with a matching normal, each vertex mapped into that triangle's chart
by clamped barycentric projection (one chart per triangle, no new bake).
Collision is unchanged.

Run after phase_runner_details.py.  python phase_runner_console.py cache|apply
"""
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from phase_runner_blend import ROOT, WORK, write
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps, validate_index_padding
from compact_preview_bsp import compact
from build_composite_map import DT

BSP = WORK/'mp_phase_runner.bsp'
PROJECT = WORK/'console'
STATIC = Path('D:/Games/ApexToTitanfallWork/project-storage/output/phase-runner/static-props.json')
CONSOLES = (5816, 5817, 5818, 5819, 16840, 16841, 16843, 16844)
SIMPLIFY = {'ship_console_control_med_v1_off': .005}
MARGIN = 1.5
PREFIX = 'world/phase_runner_preview/'


def cache():
    """meshoptimizer runs in its own process (it faults intermittently beside SciPy)."""
    PROJECT.mkdir(parents=True, exist_ok=True)
    for stem in SIMPLIFY:
        out = PROJECT/f'{stem}.npz'
        for attempt in range(3):
            if not out.exists():
                subprocess.run([sys.executable, __file__, 'cache-one', stem, str(out)])
        if not out.exists():
            raise RuntimeError('Simplification failed: '+stem)
    print('Cached', list(SIMPLIFY), flush=True)


def cache_one(stem, out):
    from plan_arena_fill import model_index
    from recover_party_columns import simplified
    sections, slots, skins = load(model_index()[stem], 0, True)
    np.savez(out, **{str(k): simplified(np.asarray(s, 'f4').reshape(-1, 3, 12).copy(), SIMPLIFY[stem]) for k, s in enumerate(sections) if len(s)})


def names_of(l):
    out = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        out.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/'))
    return out


def apply():
    from plan_arena_fill import model_index
    from apply_baked_lighting import tangents
    from spatial_preview_meshes import partition
    from repair_camera_visibility import build_camera_visibility
    from repair_native_render_partitions import reorder
    from audit_world_draw_budget import audit
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from scipy.spatial import cKDTree
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; rebuild from phase_runner_blend.py patch')
    props = {p['index']: p for p in json.loads(STATIC.read_text())}; index = model_index()
    l = read_lumps(BSP, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    names = names_of(l); tex_index = {n: i for i, n in enumerate(names)}
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); meshes = list(struct.iter_unpack('<I3H6b2h2BHI', l[0x50]))
    rec = np.frombuffer(l[0x49], DT); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8')
    # 1. Source geometry and the local boxes of every console placement.
    pieces, boxes, materials, added = [], [], set(), []
    for i in CONSOLES:
        p = props[i]; stem = Path(p['model']).stem.lower(); m = np.asarray(rotation(p['angles'])); s_ = p.get('scale', 1)
        raw, slots, skins = load(index[stem], 0, True); skin = skins[min(p.get('skin', 0), len(skins)-1)]
        simple = np.load(PROJECT/f'{stem}.npz') if stem in SIMPLIFY else None
        allp = np.concatenate([np.asarray(s, 'f8').reshape(-1, 12)[:, :3] for s in raw if len(s)])
        boxes.append((m, np.asarray(p['origin'], 'f8'), s_, allp.min(0)-MARGIN, allp.max(0)+MARGIN)); n = 0
        for k, (s, sl) in enumerate(zip(raw, slots)):
            if not len(s):
                continue
            a = simple[str(k)] if simple is not None else np.asarray(s, 'f4').reshape(-1, 3, 12)
            native = PREFIX+skin[sl]
            if native not in tex_index and native+'_transparent' in tex_index:
                native += '_transparent'  # build_glass_console.py glass rebinding
            if native not in tex_index:
                raise ValueError('Console material not in the map: '+native)
            t = a.copy(); t[:, :, :3] = a[:, :, :3]@m.T*s_+p['origin']; t[:, :, 3:6] = a[:, :, 3:6]@m.T; t[:, :, 7] = 1-a[:, :, 7]
            pieces.append((native, t)); materials.add(tex_index[native]); n += len(t)
        added.append(dict(index=i, model=p['model'], triangles=n, simplified=stem in SIMPLIFY))
    def inside(points):
        hit = np.zeros(len(points), bool)
        for m, o, s_, lo, hi in boxes:
            q = (points-o)@m/s_; hit |= np.all((q >= lo) & (q <= hi), 1)
        return hit
    # 2. Remove the drawn (simplified) console triangles; keep their light UVs for transfer.
    keep, bounds, indices = [], bytearray(), bytearray(); removed = 0; old_tri, old_light, old_page = [], [], []
    for mesh in meshes:
        srt = sorts[mesh[-2]]; local = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).reshape(-1, 3)
        if srt[0] in materials:
            ids = local.astype('u4')+srt[-1]; c = pos[rec['pi'][ids]].mean(1); drop = inside(c)
            if drop.any():
                old_tri.append(pos[rec['pi'][ids[drop]]]); old_light.append(rec['light'][ids[drop]][:, :, :2].astype('f8'))
                old_page.append(np.full(int(drop.sum()), srt[1])); removed += int(drop.sum()); local = local[~drop]
        if not len(local):
            continue
        record = list(mesh); record[0] = len(indices)//2; record[1] = len(local); indices.extend(local.tobytes())
        if len(local) & 1:
            indices.extend(struct.pack('<3H', *[int(local[-1, -1])]*3))
        q = pos[rec['pi'][local.reshape(-1).astype('u4')+srt[-1]]]; lo = q.min(0)-.02; hi = q.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
        keep.append(struct.pack('<I3H6b2h2BHI', *record)); bounds.extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
    if not removed:
        raise ValueError('No drawn console triangles found')
    buf[0x4f] = indices; buf[0x50] = bytearray(b''.join(keep)); buf[0x51] = bounds
    old_tri = np.concatenate(old_tri); old_light = np.concatenate(old_light); old_page = np.concatenate(old_page)
    on = np.cross(old_tri[:, 1]-old_tri[:, 0], old_tri[:, 2]-old_tri[:, 0]); on /= np.maximum(np.linalg.norm(on, axis=1, keepdims=True), 1e-12)
    tree = cKDTree(old_tri.mean(1))
    def light_of(t):
        # Nearest old triangle on the same-facing surface, then clamped barycentrics inside it.
        c = t[:, :, :3].mean(1); nn = np.cross(t[:, 1, :3]-t[:, 0, :3], t[:, 2, :3]-t[:, 0, :3])
        nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12)
        _, cand = tree.query(c, k=min(16, len(old_tri))); best = cand[:, 0].copy()
        for row in range(len(c)):
            ok = [j for j in cand[row] if abs(on[j]@nn[row]) > .7]
            if ok:
                best[row] = ok[0]
        a, b_, cc = old_tri[best, 0], old_tri[best, 1], old_tri[best, 2]; light = np.empty((len(t), 3, 2))
        for v in range(3):
            p = t[:, v, :3]; v0, v1, v2 = b_-a, cc-a, p-a
            d00 = (v0*v0).sum(1); d01 = (v0*v1).sum(1); d11 = (v1*v1).sum(1); d20 = (v2*v0).sum(1); d21 = (v2*v1).sum(1)
            den = np.maximum(d00*d11-d01*d01, 1e-12); w1 = (d11*d20-d01*d21)/den; w2 = (d00*d21-d01*d20)/den
            w = np.clip(np.stack([1-w1-w2, w1, w2], 1), 0, None); w /= np.maximum(w.sum(1, keepdims=True), 1e-12)
            light[:, v] = (w[:, :, None]*old_light[best]).sum(1)
        return light, old_page[best]
    # 3. Append the source consoles, one material sort per (material, page).
    groups = {}
    for native, t in pieces:
        light, page = light_of(t)
        for pg in np.unique(page):
            sel = page == pg
            groups.setdefault((native, int(pg)), []).append((t[sel], light[sel].reshape(-1, 2)))
    added_tris = 0
    for (native, pg), parts in groups.items():
        src = np.concatenate([a for a, _ in parts]); light = np.concatenate([b for _, b in parts]); n = len(src)
        pp = src[:, :, :3]; normal = src[:, :, 3:6]; uv = src[:, :, 6:8]; tan, mirror = tangents(pp, normal, uv)
        normal = normal/np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-12)
        pi = len(buf[3])//12; ni = len(buf[0x1e])//12; base = len(buf[0x49])//44
        buf[3].extend(pp.astype('<f4').tobytes()); nb = np.empty((n*6, 3), '<f4'); nb[::2] = normal.reshape(-1, 3); nb[1::2] = tan.reshape(-1, 3)
        buf[0x1e].extend(nb.tobytes())
        r = np.zeros(n*3, DT); r['pi'] = np.arange(pi, pi+n*3); r['ni'] = np.arange(ni, ni+n*6, 2); r['uv'] = uv.reshape(-1, 2)
        r['color'] = 255; r['light'][:, :2] = light
        r['tangent'] = np.arange(ni+1, ni+n*6, 2, dtype=np.uint32) | (mirror.reshape(-1).astype('u4') << 31)
        buf[0x49].extend(r.tobytes())
        local = np.arange(n*3, dtype='<u2').reshape(-1, 3)
        front = np.sum(np.cross(pp[:, 1]-pp[:, 0], pp[:, 2]-pp[:, 0])*normal.sum(1), axis=1) > 0; local[front] = local[front][:, [0, 2, 1]]
        si = len(buf[0x52])//12; buf[0x52].extend(struct.pack('<3hHI', tex_index[native], pg, -1, n*3-1, base))
        for ids in partition(pp.mean(1), np.arange(n), limit=512):
            ix = local[ids]; q = pp[ids].reshape(-1, 3); lo = q.min(0)-.02; hi = q.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
            buf[0x50].extend(struct.pack('<I3H6b2h2BHI', len(buf[0x4f])//2, len(ix), int(ix.min()), int(ix.max()-ix.min()), 2, -1, -1, -1, -1, -1, -1, -1,
                                         255, 255, si, 0x100a00 | (0x10 if native.endswith('_transparent') else 0)))
            buf[0x4f].extend(ix.tobytes())
            if len(ix) & 1:
                buf[0x4f].extend(struct.pack('<3H', *[int(ix[-1, -1])]*3))
            buf[0x51].extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
        added_tris += n
    count = len(buf[0x50])//28; struct.pack_into('<2I', buf[0xe], 24, 0, count)
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    buf.update(reorder(buf)[0]); validate_index_padding(buf[0x50], buf[0x4f], buf[0x52])
    temp = BSP.with_suffix('.console.bsp'); compact(BSP, temp, buf); budget = audit(temp)
    if budget['native_padded_indices'] >= 3145728*.98 or budget['static_batch_runs'] >= 512:
        os.remove(temp); raise ValueError('Budget exceeded: '+json.dumps({k: budget[k] for k in ('native_padded_indices', 'static_batch_runs')}))
    os.replace(temp, BSP)
    report = dict(consoles=added, removed_triangles=removed, added_triangles=added_tris, material_sorts=len(groups), budget=budget)
    write(PROJECT/'result.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('budget', 'consoles')}),
          'occupancy', round(budget['native_padded_indices']/3145728*100, 3), 'batches', budget['static_batch_runs'], flush=True)


if __name__ == '__main__':
    if sys.argv[1:2] == ['cache-one']:
        cache_one(sys.argv[2], sys.argv[3]); sys.exit()
    {'cache': cache, 'apply': apply}[sys.argv[1]]()
