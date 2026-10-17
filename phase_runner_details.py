"""Phase Runner 1.7.1: container frames and catwalk profile (user report, 17 October 2026).

* Container frames: `industrial_cargo_container_320_01` (and other container
  models) are drawn at an authored LOD that keeps only the box; the metal frame
  (trim sections, z 0-144 around the z 8-136 box) exists only at finer LODs, so
  stacked containers show an empty gap. For each drawn container whose drawn
  LOD lacks frame sections, the frame sections of the finest LOD that the port
  can afford (LOD2) are appended as new meshes. Their lightmap coordinates and
  page are copied from the nearest vertex of the same container (the frame
  wraps the box, so lighting matches without a new bake). Collision is
  unchanged (the source collider already covers the frame).
* Catwalk profile: the 0.1.37 tunnel catwalks follow the exact old Apex path
  elevations, which bob +-14 units every few points ("weird dips"), and their
  arena ends stop about 18 units above the floor. Every catwalk vertex (render,
  collision, shadow) is moved vertically by dz(s) = smoothed(z)(s) - z(s) along
  the route, with the arena end ramped down onto the floor over RAMP units.
  Catwalk collision is rebuilt from the displaced triangles; the old catwalk
  headers leave the grid.

Run after phase_runner_blend.py patch/materials and phase_runner_collision.py apply.
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from phase_runner_blend import ROOT, WORK, PACKAGE, write
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter1d
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps, validate_index_padding
from compact_preview_bsp import compact
from build_composite_map import DT
from build_center_detail import active

BSP = WORK/'mp_phase_runner.bsp'
PROJECT = WORK/'details'
STATIC = Path('D:/Games/ApexToTitanfallWork/project-storage/output/phase-runner/static-props.json')
CONTAINER = ('container',)
FRAME_LOD = 2
CATWALK_TEX = ('world/phase_runner_preview/trim_metal_01', 'world/phase_runner_preview/trim_metal_01_yellow',
               'world/phase_runner_preview/boomtown_solid_grate_01')
CORRIDOR = 62.0      # catwalk half-width incl. rails/frames
SIGMA = 60.0         # profile smoothing (units of arc length)
RAMP = 160.0         # arena-end ramp onto the floor
STEP = 10.0
DECK_ABOVE_ROUTE = 2.0


def names_of(l):
    out = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        out.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace(chr(92), '/'))
    return out


# --- catwalk profile -------------------------------------------------------

def profiles(floor_tris):
    """Per route: dense xy path, original z0(s) and target z1(s)."""
    routes = json.loads((PACKAGE/'catwalks.json').read_text())['routes']; out = []
    for route in routes:
        P = np.asarray(route['points'], 'f8'); s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1))]
        u = np.arange(0, s[-1]+STEP, STEP); xy = np.stack([np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])], 1)
        z0 = np.interp(u, s, P[:, 2]); z1 = gaussian_filter1d(z0, SIGMA/STEP, mode='nearest')
        floor = floor_height(floor_tris, P[0], P[0][2]+5)
        if floor is not None and P[0][2]-floor < 60:
            target = floor-DECK_ABOVE_ROUTE; w = np.clip(u/RAMP, 0, 1)
            z1 = np.where(u < RAMP, target*(1-w)+np.interp(RAMP, u, z1)*w, z1)
        out.append(dict(xy=xy, z0=z0, z1=z1, tree=cKDTree(xy), floor=floor, start=P[0].tolist()))
    return out


def floor_height(tris, p, below):
    lo = tris[:, :, :2].min(1); hi = tris[:, :, :2].max(1)
    sel = np.flatnonzero((lo[:, 0] <= p[0]) & (hi[:, 0] >= p[0]) & (lo[:, 1] <= p[1]) & (hi[:, 1] >= p[1]))
    best = None
    for i in sel:
        a, b, c = tris[i]; d = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(d) < 1e-9:
            continue
        w1 = ((b[1]-c[1])*(p[0]-c[0])+(c[0]-b[0])*(p[1]-c[1]))/d; w2 = ((c[1]-a[1])*(p[0]-c[0])+(a[0]-c[0])*(p[1]-c[1]))/d
        if min(w1, w2, 1-w1-w2) < 0:
            continue
        z = w1*a[2]+w2*b[2]+(1-w1-w2)*c[2]
        if z < below and (best is None or z > best):
            best = z
    return best


def displacement(points, routes):
    """dz for points inside a catwalk corridor (0 elsewhere) and the corridor mask."""
    dz = np.zeros(len(points)); inside = np.zeros(len(points), bool)
    for r in routes:
        d, j = r['tree'].query(points[:, :2])
        ok = (d < CORRIDOR) & (points[:, 2] > r['z0'][j]-150) & (points[:, 2] < r['z0'][j]+80) & ~inside
        dz[ok] = (r['z1']-r['z0'])[j[ok]]; inside |= ok
    return dz, inside


def apply():
    from plan_arena_fill import model_index
    from apply_baked_lighting import tangents
    from spatial_preview_meshes import partition
    from repair_camera_visibility import build_camera_visibility
    from repair_native_render_partitions import reorder
    from match_collision_to_render import replace_collision
    from audit_world_draw_budget import audit
    import analyse_visibility as vis
    PROJECT.mkdir(parents=True, exist_ok=True)
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; rebuild from phase_runner_blend.py patch')
    l = read_lumps(BSP, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    names = names_of(l); sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    rec = np.frombuffer(l[0x49], DT).copy(); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8')
    meshes = list(struct.iter_unpack('<I3H6b2h2BHI', l[0x50]))
    tris, mesh_of, _ = vis.render_triangles(BSP); tris = tris.astype('f8'); nrm = vis.render_triangles.normals
    cat_tex = {i for i, n in enumerate(names) if n in CATWALK_TEX}
    mesh_tex = np.asarray([sorts[m[-2]][0] for m in meshes])
    up = nrm[:, 2] > .7*np.linalg.norm(nrm, axis=1)
    floor = tris[up & ~np.isin(mesh_tex[mesh_of], list(cat_tex))]
    routes = profiles(floor)
    # 1. Catwalk meshes: catwalk materials with (almost) every triangle in a corridor.
    cat_meshes = []
    for mi, m in enumerate(meshes):
        if mesh_tex[mi] not in cat_tex:
            continue
        c = tris[mesh_of == mi].mean(1)
        if len(c) and displacement(c, routes)[1].mean() > .9:
            cat_meshes.append(mi)
    moved_records = {}
    old_keys = {}
    for mi in cat_meshes:
        m = meshes[mi]; base = sorts[m[-2]][-1]
        ix = np.unique(np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('u4')+base)
        for r_ in ix:
            moved_records[int(r_)] = None
    recs = np.fromiter(moved_records, 'i8'); p_old = pos[rec['pi'][recs]]
    dz, inside = displacement(p_old, routes)
    p_new = p_old.copy(); p_new[:, 2] += dz
    for a, b in zip(p_old, p_new):
        old_keys[tuple(np.round(a, 3))] = b
    first = len(buf[3])//12; buf[3].extend(p_new.astype('<f4').tobytes()); rec['pi'][recs] = np.arange(first, first+len(recs))
    # Mesh bounds of moved meshes.
    newpos = np.frombuffer(bytes(buf[3]), '<f4').reshape(-1, 3)
    for mi in cat_meshes:
        m = meshes[mi]; base = sorts[m[-2]][-1]
        ix = np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('u4')+base; p = newpos[rec['pi'][ix]]
        lo = p.min(0)-.02; hi = p.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
        struct.pack_into('<8f', buf[0x51], mi*32, *c, float(np.linalg.norm(e))+.02, *e, 0)
    # Shadow vertices of catwalk faces.
    shv = np.frombuffer(l[0x7c], '<f4').reshape(-1, 3).astype('f8').copy(); moved_shadow = 0
    sdz, sin_ = displacement(shv, routes)
    for i in np.flatnonzero(sin_):
        if tuple(np.round(shv[i], 3)) in old_keys:
            shv[i, 2] += sdz[i]; moved_shadow += 1
    buf[0x7c] = bytearray(shv.astype('<f4').tobytes())
    # Catwalk collision: replace the 0.1.37 headers with displaced triangles.
    info = json.loads((PACKAGE/'catwalks.json').read_text())['collision']; act = active(l)
    heads = list(struct.iter_unpack('<6h4i4f', l[0x45])); words = np.frombuffer(l[0x42], '<u4')
    drop_h = {i for i in range(info['new_first_header'], info['new_first_header']+info['new_headers']) if (0x40, i) in act}
    col = []
    for i in sorted(drop_h):
        h = heads[i]; w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        col.append(pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)])
    col = np.concatenate(col); flat = col.reshape(-1, 3); cdz, _ = displacement(flat, routes); flat[:, 2] += cdz
    col = flat.reshape(-1, 3, 3).astype('<f4')
    buf[0x49] = bytearray(rec.tobytes())
    replace_collision(l, buf, set(), drop_h, col)
    # 2. Container frames.
    props = {p['index']: p for p in json.loads(STATIC.read_text())}
    status = {p['source_index']: p['status'] for p in json.loads((ROOT/'docs/conversion/static-placement-inventory.json').read_text())['placements']}
    index = model_index(); drawn = cKDTree(np.unique(tris.reshape(-1, 3), axis=0))
    rec_tree_cache = {}; pieces = []; added = []
    # Container vertices (any material) with their record, for light-UV transfer.
    allrec_pos = newpos[rec['pi']]
    for i, p in props.items():
        stem = Path(p['model']).stem.lower()
        if status.get(i) != 'rendered' or not any(w in stem for w in CONTAINER) or stem not in index:
            continue
        try:
            levels = struct.unpack_from('<18Q', (index[stem]/(index[stem].name+'.vg')).read_bytes(), 16)[13]
        except OSError:
            continue
        m = np.asarray(rotation(p['angles'])); best = None
        for lod in range(levels):
            raw, slots, skins = load(index[stem], lod, True)
            pts = np.concatenate([np.asarray(s, 'f8').reshape(-1, 12)[:, :3] for s in raw if len(s)])@m.T*p.get('scale', 1)+p['origin']
            f = float(np.mean(drawn.query(pts[::5])[0] < .5))
            if best is None or f > best[0]:
                best = (f, lod, {skins[0][sl] for s, sl in zip(raw, slots) if len(s)})
        if best is None or best[0] < .9:
            continue
        lod = min(FRAME_LOD, levels-1)
        if best[1] <= lod:
            continue
        raw, slots, skins = load(index[stem], lod, True); skin = skins[min(p.get('skin', 0), len(skins)-1)]
        for s, sl in zip(raw, slots):
            if not len(s) or skins[0][sl] in best[2]:
                continue  # only sections missing from the drawn LOD (the frame)
            a = np.asarray(s, 'f4').reshape(-1, 3, 12); t = a.copy()
            t[:, :, :3] = a[:, :, :3]@m.T*p.get('scale', 1)+p['origin']; t[:, :, 3:6] = a[:, :, 3:6]@m.T; t[:, :, 7] = 1-a[:, :, 7]
            pieces.append((skin[sl], t, np.asarray(p['origin'], 'f8')))
        added.append(dict(index=i, model=p['model'], drawn_lod=best[1], frame_lod=lod))
    # Append frame meshes, light UV/page from the nearest drawn vertex.
    rec_light = rec['light']; vtree = cKDTree(allrec_pos)
    tex_index = {n: i for i, n in enumerate(names)}; frame_tris = 0
    sort_of_record = np.zeros(len(rec), 'i4')
    order = sorted(range(len(sorts)), key=lambda k: sorts[k][-1])
    bases = [sorts[k][-1] for k in order]
    # Group every frame triangle by (material, lightmap page): one material sort each,
    # so the native static batch count (490/512 before this round) barely grows.
    groups = {}
    for name, t, origin in pieces:
        native = 'world/phase_runner_preview/'+name
        if native not in tex_index:
            continue
        p = t[:, :, :3].reshape(-1, 3); _, near = vtree.query(p)
        sidx = np.searchsorted(bases, near, side='right')-1; page = np.asarray([sorts[order[k]][1] for k in sidx]).reshape(-1, 3)
        for pg in np.unique(page[:, 0]):
            sel = page[:, 0] == pg
            groups.setdefault((native, int(pg)), []).append((t[sel], rec_light[near.reshape(-1, 3)[sel].reshape(-1)][:, :2]))
    for (native, pg), parts in groups.items():
        if True:
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
            si = len(buf[0x52])//12; buf[0x52].extend(struct.pack('<3hHI', tex_index[native], int(pg), -1, n*3-1, base))
            for ids in partition(pp.mean(1), np.arange(n), limit=512):
                ix = local[ids]; q = pp[ids].reshape(-1, 3); lo = q.min(0)-.02; hi = q.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
                buf[0x50].extend(struct.pack('<I3H6b2h2BHI', len(buf[0x4f])//2, len(ix), int(ix.min()), int(ix.max()-ix.min()), 2, -1, -1, -1, -1, -1, -1, -1,
                                             255, 255, si, 0x100a00))
                buf[0x4f].extend(ix.tobytes())
                if len(ix) & 1:
                    buf[0x4f].extend(struct.pack('<3H', *[int(ix[-1, -1])]*3))
                buf[0x51].extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
            frame_tris += n
    count = len(buf[0x50])//28; struct.pack_into('<2I', buf[0xe], 24, 0, count)
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    buf.update(reorder(buf)[0]); validate_index_padding(buf[0x50], buf[0x4f], buf[0x52])
    temp = BSP.with_suffix('.details.bsp'); compact(BSP, temp, buf)
    budget = audit(temp)
    if budget['native_padded_indices'] >= 3145728*.98 or budget['static_batch_runs'] >= 512:
        os.remove(temp); raise ValueError('Budget exceeded')
    os.replace(temp, BSP)
    report = dict(catwalk_meshes=len(cat_meshes), catwalk_records_moved=len(recs), max_abs_dz=round(float(np.abs(dz).max()), 2),
                  catwalk_shadow_vertices_moved=moved_shadow, catwalk_collision_headers_replaced=len(drop_h),
                  catwalk_collision_triangles=int(len(col)),
                  route_ends=[dict(start=r['start'], floor=r['floor']) for r in routes],
                  container_frames=added, frame_triangles=frame_tris, budget=budget)
    write(PROJECT/'result.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('container_frames', 'budget')}), 'frames', len(added), flush=True)


if __name__ == '__main__':
    apply()
