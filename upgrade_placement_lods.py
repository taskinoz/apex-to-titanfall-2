"""Raise the authored LOD of chosen source placements, preserving collision.

Low authored LODs shrink rocks inside their full-detail source collision: the
player bumps into invisible rock, and adjoining rocks open gaps (Firing Range
reports f15, f16, f18, f20, f21). For each chosen placement the old LOD's
triangles are retired from the native draw streams by exact transformed
position, and the higher authored LOD is appended through append_free_charts,
which reuses the released lightmap tiles. Existing colliders are kept; no
collision is added or removed.

Selection: rock placements within RADIUS of the reported camera positions,
stepped up STEP levels (never below LOD 0), nearest first, until the 98%
world-index ceiling.
"""
import argparse
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
import recover_composite_details as recovery
from new_arena_ports import CONFIG, ROOT, WORK, folder
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from audit_world_draw_budget import audit

RADIUS = 1200
# Placements this far from any reachable point drop to their lowest authored
# LOD first, paying for the upgrades near the reports.
FAR = 1500
STEP = 1
INDEX_FRACTION = .98
PLAN_FRACTION = .975  # margin for per-mesh index padding of new geometry
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier', 'shimmer')


def paths(ident):
    out = folder(ident)
    return out, out/'lod-upgrade', out/'before-lod-upgrade', out/(CONFIG[ident]['target']+'.bsp')


def keys(t):
    return np.sort(np.asarray(t, '<f4'), axis=1).reshape(-1, 9).copy().view('V36').reshape(-1)


def geometry(p, lod, cache):
    f = p['folder']
    if (f, lod) not in cache:
        cache[f, lod] = load(f, lod, True)
    sections, slots, skins = cache[f, lod]
    skin = skins[min(p['skin'], len(skins)-1)]; matrix = np.asarray(rotation(p['angles'])); out = []
    for s, slot in zip(sections, slots):
        if not len(s) or any(w in skin[slot].lower() for w in SKIP_SECTIONS):
            continue
        s = np.asarray(s, 'f4'); t = s.copy()
        t[:, :, :3] = s[:, :, :3]@matrix.T*p['scale']+p['origin']; t[:, :, 3:6] = s[:, :, 3:6]@matrix.T
        t[:, :, 7] = 1-s[:, :, 7]; t[:, :, 11] = 255
        out.append((skin[slot], t))
    return out


def plan(ident, routes):
    out, project, backup, bsp = paths(ident)
    if (project/'result.json').exists():
        raise ValueError('Already applied')
    project.mkdir(exist_ok=True)
    reports = np.asarray([s['origin'] for r in routes for s in json.loads(Path(r).read_text())['shots'] if s['name'] != 'warmup']).reshape(-1, 3)
    scene = json.loads((out/'scene.json').read_text()); cache = {}
    current = audit(bsp)["native_padded_indices"]; room = 3145728*PLAN_FRACTION-current
    from append_free_charts import free_tiles
    chart_room = len(free_tiles(bsp))
    cands = []
    for p in scene['placements']:
        if 'rock' not in p['model'] or 'folder' not in p or p.get('lod', 0) < STEP:
            continue
        if not len(reports):
            continue  # downgrade-only mode
        d = float(np.min(np.linalg.norm(reports-np.asarray(p['origin']), axis=1)))
        if d <= RADIUS:
            cands.append((d, p))
    cands.sort(key=lambda c: c[0])
    pieces, retire, chosen, skipped = [], [], [], []
    used = net = 0
    reach = out/'visibility/reachable.npy'
    if reach.exists():
        sys.path.insert(0, str(ROOT/'tools/lighting-python'))
        from scipy.spatial import cKDTree
        tree = cKDTree(np.load(reach)); import struct as _s
        for p in scene['placements']:
            f = p.get('folder')
            if not f or not (Path(f)/(Path(f).name+'.vg')).exists():
                continue
            last = _s.unpack_from('<18Q', (Path(f)/(Path(f).name+'.vg')).read_bytes(), 16)[13]-1
            if p.get('lod', 0) >= last or tree.query(p['origin'])[0] <= FAR:
                continue
            old = geometry(p, p['lod'], cache); new = geometry(p, last, cache)
            oldn = sum(len(t) for _, t in old); newn = sum(len(t) for _, t in new)
            pieces.extend(new); retire.append(np.concatenate([t[:, :, :3] for _, t in old]))
            used += newn; net += newn-oldn
            chosen.append(dict(p, lod=last, previous_lod=p['lod'], triangles=newn, retired_triangles=oldn, replacement=True,
                               recovery='Lowest authored LOD for unreachable distance', collision_triangles=0,
                               collision_recovery='Existing source collider retained; visual LOD only'))
    for d, p in cands:
        old = geometry(p, p['lod'], cache); new = geometry(p, p['lod']-STEP, cache)
        oldn = sum(len(t) for _, t in old); newn = sum(len(t) for _, t in new)
        cost = 3*(net+newn-oldn)+3*(len(chosen)+1)*2
        if cost > room or used+newn > chart_room+sum(len(r) for r in retire)+oldn:
            skipped.append(dict(index=p['index'], model=p['model'], reason='Exceeds the world-index ceiling')); continue
        pieces.extend(new); retire.append(np.concatenate([t[:, :, :3] for _, t in old]))
        used += newn; net += newn-oldn
        chosen.append(dict(p, lod=p['lod']-STEP, previous_lod=p['lod'], triangles=newn, retired_triangles=oldn, distance=round(d),
                           replacement=True, recovery='Source authored LOD upgrade', collision_triangles=0,
                           collision_recovery='Existing source collider retained; visual LOD only'))
    names = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(project/'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names.index(n), 'i4') for n, t in pieces]),
             names=names, collision=np.empty((0, 3, 3), 'f4'))
    np.save(project/'retire-points.npy', np.concatenate(retire))
    report = dict(version='lod-upgrade', downgraded=sum(p['lod'] > p['previous_lod'] for p in chosen),
                  upgraded=sum(p['lod'] < p['previous_lod'] for p in chosen), added_props=len(chosen), added_triangles=used, net_triangles=net,
                  placements=chosen, skipped=skipped, radius=RADIUS, step=STEP)
    (project/'plan.json').write_text(json.dumps(report, indent=2))
    print('Upgrade', len(chosen), 'placements; +', used, 'triangles, net', net, '; skipped', len(skipped), flush=True)


def snapshot(ident):
    out, project, backup, bsp = paths(ident)
    if backup.exists():
        raise ValueError('Snapshot exists')
    backup.mkdir()
    for name in (bsp.name, bsp.with_suffix('.stbsp').name, 'scene.npz', 'scene.json', 'physics.npz', 'physics.json', 'source-build.json'):
        shutil.copy2(out/name, backup/name)


def retire(ident, project=None):
    """Drop the old-LOD triangles from the draw and shadow streams."""
    out, default, backup, bsp = paths(ident); project = Path(project or default)
    pts = np.load(project/'retire-points.npy'); want = set(keys(pts).tolist())
    l = read_lumps(bsp, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); rec = np.frombuffer(l[0x49], DT); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3)
    keep, bounds, newindices = [], bytearray(), bytearray(); removed = 0
    for i, mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI', l[0x50])):
        sort = sorts[mesh[-2]]
        local = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).reshape(-1, 3)
        k = keys(pos[rec['pi'][local.astype('u4')+sort[-1]]])
        drop = np.fromiter((x in want for x in k.tolist()), bool, len(k)); removed += int(drop.sum())
        local = local[~drop]
        if not len(local):
            continue
        record = list(mesh); record[0] = len(newindices)//2; record[1] = len(local)
        newindices.extend(local.tobytes())
        if len(local) & 1:
            newindices.extend(struct.pack('<3H', *[int(local[-1, -1])]*3))
        p = pos[rec['pi'][local.reshape(-1).astype('u4')+sort[-1]]]; lo = p.min(0)-.02; hi = p.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
        keep.append(struct.pack('<I3H6b2h2BHI', *record)); bounds.extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
    # Old-LOD triangles absent from the draw were already retired as hidden meshes.
    already = 0
    if (out/'before-retire').exists():
        lr = read_lumps(out/'before-retire'/bsp.name, (3, 0x49, 0x4f, 0x50, 0x52)); rr = np.frombuffer(lr[0x49], DT)
        pr = np.frombuffer(lr[3], '<f4').reshape(-1, 3); sr = list(struct.iter_unpack('<3hHI', lr[0x52]))
        hidden = set(json.loads((out/'visibility/analysis.json').read_text()) and np.load(out/'visibility/hidden-meshes.npy').tolist())
        for i, m in enumerate(struct.iter_unpack('<I3H6b2h2BHI', lr[0x50])):
            if i in hidden:
                ix = np.frombuffer(lr[0x4f], '<u2', m[1]*3, m[0]*2).astype('u4')+sr[m[-2]][-1]
                already += sum(x in want for x in keys(pr[rr['pi'][ix]].reshape(-1, 3, 3)).tolist())
    if removed+already != len(pts):
        raise ValueError(f'Matched {removed} drawn + {already} already retired of {len(pts)} old-LOD triangles')
    buf[0x4f] = newindices; buf[0x50] = bytearray(b''.join(keep)); buf[0x51] = bounds
    count = len(keep); struct.pack_into('<2I', buf[0xe], 24, 0, count)
    shv = np.frombuffer(l[0x7c], '<f4').reshape(-1, 3); newv, newix, newrec = bytearray(), bytearray(), bytearray()
    excluded = keys(pts)
    for first, n, page, unused in struct.iter_unpack('<2I2h', l[0x7f]):
        s = shv[first:first+n*3].reshape(-1, 3, 3); s = s[~np.isin(keys(s), excluded)]
        if not len(s):
            continue
        newrec.extend(struct.pack('<2I2h', len(newv)//12, len(s), page, unused)); newv.extend(s.tobytes())
        newix.extend(np.arange(len(s)*3, dtype='<u2').tobytes())
    buf[0x7c], buf[0x7e], buf[0x7f] = newv, newix, newrec
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    for at in (0, 36):
        struct.pack_into('<i', buf[5], at+20, len(newrec)//12)
    struct.pack_into('<i', buf[5], 44, len(newrec)//12)
    buf.update(reorder(buf)[0])
    temp = bsp.with_suffix('.lodretire.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    print('Retired', removed, 'old-LOD triangles', flush=True)


def apply(ident, bake_base):
    out, project, backup, bsp = paths(ident)
    if not backup.exists():
        snapshot(ident)
    retire(ident)
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = out, project, bsp, backup
    direction = -np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
    from append_free_charts import append
    append(out/bake_base, INDEX_FRACTION, str(WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    scene = json.loads((out/'scene.json').read_text())
    scene['placements'] = list({p['index']: p for p in scene['placements']}.values()); scene['props'] = len(scene['placements'])
    (out/'scene.json').write_text(json.dumps(scene, indent=2))
    from build_preview_stbsp import build
    build(out, out/'materials', CONFIG[ident]['target'], ident.replace('-', '_')+'_world')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'apply']); p.add_argument('ident', choices=sorted(CONFIG))
    p.add_argument('--route', action='append', default=[]); p.add_argument('--bake-base', default='surface-repair')
    a = p.parse_args()
    plan(a.ident, a.route) if a.action == 'plan' else apply(a.ident, a.bake_base)
