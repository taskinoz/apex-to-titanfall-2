"""Find render meshes no player can ever see, conservatively.

Viewpoints come from a reachability flood over walkable render surfaces,
starting at the native spawn probes: a pilot may climb up to CLIMB units to an
adjacent 64-unit cell (double jump and wallrun) and drop any height. Points
inside decoded out-of-bounds or hurt triggers, and below the kill floor, are
excluded. Invisible clip walls are ignored, so the reachable set is larger
than the real one: this can only keep more geometry, never less.

From each viewpoint (eye, jump and wallrun heights) RAYS directions are cast
with tools/visibility_rays.exe; every first-hit triangle counts as seen. A
whole native mesh is cullable only if none of its triangles was ever hit.
"""
import argparse
import json
import struct
import subprocess
import sys
from collections import deque
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from repair_preview_index_padding import read_lumps
from build_composite_map import DT

CELL = 64
CLIMB = 400
HEIGHTS = (64, 400)
VIEW_GRID = 256
OOB_MARGIN = 600
MENU_RADIUS = 3000
MIN_CULL_TRIANGLES = 32
LOS_RADIUS = 8000
LOS_PER_TRIANGLE = 300
RAYS = 4000


def render_triangles(bsp):
    l = read_lumps(bsp, (2, 3, 0x1e, 0x2b, 0x2c, 0x49, 0x4f, 0x50, 0x52))
    native = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        native.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); rec = np.frombuffer(l[0x49], DT)
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3); nrm = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3)
    tris, mesh_of, names, normals = [], [], [], []
    for i, mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI', l[0x50])):
        sort = sorts[mesh[-2]]
        ix = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('u4')+sort[-1]
        tris.append(pos[rec['pi'][ix]].reshape(-1, 3, 3)); mesh_of.append(np.full(mesh[1], i, 'i4'))
        normals.append(nrm[rec['ni'][ix]].reshape(-1, 3, 3).mean(1))
        names.append(native[sort[0]])
    render_triangles.normals = np.concatenate(normals)
    return np.concatenate(tris), np.concatenate(mesh_of), names


def triggers(ident):
    from decode_source_trigger_volumes import pieces
    scene = json.loads((folder(ident)/'scene.json').read_text()); planes = []
    for e in scene['source_entities']:
        if e.get('classname') in ('trigger_out_of_bounds', 'trigger_hurt'):
            try:
                decoded = pieces(e)
            except ValueError:
                # Unsupported descriptor variant (Overflow): omitting the volume only
                # enlarges reach, which keeps more meshes and audits more collision.
                triggers.skipped = getattr(triggers, 'skipped', 0)+1
                continue
            for p in decoded:
                # Trigger pieces are in source coordinates: n.x <= d becomes n.x' <= d + n.offset.
                # Pieces are relative to the entity origin, in source coordinates.
                origin = np.asarray([float(v) for v in e.get('origin', '0 0 0').split()])
                P = np.asarray(p['planes'], 'f8'); P[:, 3] += P[:, :3]@(origin+np.asarray(CONFIG[ident]['offset'], 'f8'))
                planes.append(P)
    return planes


def inside(points, planes):
    out = np.zeros(len(points), bool)
    for P in planes:
        out |= np.all(points@P[:, :3].T <= P[:, 3]+1, axis=1)
    return out


def viewpoints(ident, tris, walkable=None):
    # Native winding is reversed: orientation comes from the stored vertex normals.
    area = np.linalg.norm(np.cross(tris[:, 1]-tris[:, 0], tris[:, 2]-tris[:, 0]), axis=1)
    n = render_triangles.normals; n = n/np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    up = (area > 1e-3) & (n[:, 2] > .7)
    if walkable is not None:
        up &= walkable
    samples = []
    for t in tris[up]:
        edge = max(np.linalg.norm(t[1]-t[0]), np.linalg.norm(t[2]-t[0]), np.linalg.norm(t[2]-t[1]))
        k = max(1, int(edge//CELL)+1)
        a, b = np.meshgrid(np.arange(k+1), np.arange(k+1)); keep = (a+b) <= k
        w = np.stack([k-a[keep]-b[keep], a[keep], b[keep]], 1)/k
        samples.append(w@t)
    s = np.concatenate(samples)
    cell = np.floor(s[:, :2]/CELL).astype('i8'); zb = np.floor(s[:, 2]/32).astype('i8')
    key = np.unique(np.stack([cell[:, 0], cell[:, 1], zb], 1), axis=0)
    floor = CONFIG[ident]['bounds'][0][2]-512
    key = key[key[:, 2]*32 > floor]
    pts = np.c_[(key[:, :2]+.5)*CELL, key[:, 2]*32+16]
    planes = triggers(ident)
    oob = inside(pts+[0, 0, 40], planes) if planes else np.zeros(len(pts), bool)
    nodes = {}
    for i, (x, y, z) in enumerate(key):
        nodes.setdefault((x, y), []).append((z, i))
    spawns = json.loads((folder(ident)/'native-spawn-candidates.json').read_text())['regions']
    seen = np.zeros(len(key), bool); queue = deque()
    for region in spawns:
        for probe in region['probes']:
            x, y, z = probe['origin']
            cands = nodes.get((int(np.floor(x/CELL)), int(np.floor(y/CELL))), [])
            if cands:
                zz, i = min(cands, key=lambda c: abs(c[0]*32-z))
                if not seen[i] and not oob[i]:
                    seen[i] = True; queue.append(i)
    while queue:
        i = queue.popleft(); x, y, z = key[i]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = nodes.get((x+dx, y+dy), ())
                # A fall lands on the first surface below, never through a floor.
                below = [c for c in cell if c[0] <= z]
                targets = [max(below)] if below else []
                targets += [c for c in cell if z < c[0] and c[0]*32 <= z*32+CLIMB]
                for zz, j in targets:
                    if not seen[j] and not oob[j]:
                        seen[j] = True; queue.append(j)
    reach = pts[seen]
    # Players can step into out-of-bounds volumes before the countdown kills
    # them: keep viewpoints in those volumes near reachable ground.
    if planes and len(reach):
        sys.path.insert(0, str(ROOT/'tools/lighting-python'))
        from scipy.spatial import cKDTree
        d, _ = cKDTree(reach).query(pts[oob])
        reach = np.concatenate([reach, pts[oob][d <= OOB_MARGIN]])
    g = np.unique(np.c_[np.floor(reach[:, :2]/VIEW_GRID), np.floor(reach[:, 2]/192)], axis=0, return_index=True)[1]
    base = reach[g]
    views = np.concatenate([base+[0, 0, h] for h in HEIGHTS])
    return views.astype('f4'), reach


def see_through(ident, names):
    out = folder(ident); mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    by_native = {r['name'].rsplit('/', 1)[-1]: r for r in mapping.values()}
    result = {}
    for n in set(names):
        r = mapping.get(n) or by_native.get(n) or {}
        spec = out/'materials/assets'/('material/'+r['name']+'_wld.json') if r else None
        shader = json.loads(spec.read_text()).get('shaderSet', '') if spec and spec.exists() else ''
        result[n] = bool(r.get('transparent')) or 'cutout' in shader or 'alpha' in shader or 'glass' in shader             or any(w in n.lower() for w in ('glass', 'fence', 'grate', 'holes', 'decal', 'sky'))
    return result


def analyse(ident, bsp=None, work_name='visibility'):
    out = folder(ident); work = out/work_name; work.mkdir(exist_ok=True)
    bsp = Path(bsp) if bsp else out/(CONFIG[ident]['target']+'.bsp')
    tris, mesh_of, names = render_triangles(bsp)
    # Non-solid water and sky surfaces are not ground a pilot can stand on.
    solid = np.asarray([not any(w in n.lower() for w in ('water', 'sky')) for n in names])[mesh_of]
    views, reach = viewpoints(ident, tris.astype('f8'), solid)
    tris.astype('<f4').tofile(work/'triangles.bin'); views.tofile(work/'points.bin')
    # See-through materials never block a ray, and are never culled themselves.
    see = see_through(ident, names)
    occluder = np.asarray([not see[names[m]] for m in mesh_of], 'u1'); occluder.tofile(work/'occluders.bin')
    print(ident, 'reachable cells', len(reach), 'viewpoints', len(views), flush=True)
    subprocess.run([str(ROOT/'tools/visibility_rays.exe'), str(work/'triangles.bin'), str(work/'points.bin'), str(RAYS),
                    str(work/'hits.bin'), str(work/'occluders.bin')], check=True)
    hits = np.fromfile(work/'hits.bin', '<u4')
    meshes = len(names); mesh_hits = np.bincount(mesh_of, weights=hits, minlength=meshes)
    counts = np.bincount(mesh_of, minlength=meshes)
    # Never cull the relocated menu stage, or tiny meshes rays could miss.
    from repair_environment_lighting import entities
    menu = [np.asarray([float(v) for v in e['origin'].split()]) for e in entities(bsp)
            if e.get('script_name') in ('menu_scene_ref', 'menu_camera_target')]
    centres = np.asarray([tris[mesh_of == i].reshape(-1, 3).mean(0) for i in range(meshes)])
    protected = np.zeros(meshes, bool)
    for m in menu:
        protected |= np.linalg.norm(centres-m, axis=1) < MENU_RADIUS
    clear = np.asarray([see[n] for n in names])
    hidden = np.flatnonzero((mesh_hits == 0) & ~protected & ~clear & (counts >= MIN_CULL_TRIANGLES))
    # Exact second pass: rays miss thin geometry (wires, frames). Every triangle
    # of a candidate mesh is tested for an unblocked line of sight to nearby
    # viewpoints; one visible triangle keeps the whole mesh.
    cand = np.flatnonzero(np.isin(mesh_of, hidden)).astype('<i4'); cand.tofile(work/'candidates.bin')
    subprocess.run([str(ROOT/'tools/visibility_rays.exe'), 'segments', str(work/'triangles.bin'), str(work/'occluders.bin'),
                    str(work/'points.bin'), str(work/'candidates.bin'), str(LOS_RADIUS), str(LOS_PER_TRIANGLE),
                    str(work/'los.bin')], check=True)
    seen = np.fromfile(work/'los.bin', 'u1').astype(bool)
    rescued = np.unique(mesh_of[cand[seen]])
    hidden = np.setdiff1d(hidden, rescued)
    hidden_tris = int(counts[hidden].sum())
    np.save(work/'hidden-meshes.npy', hidden); np.save(work/'reachable.npy', reach)
    report = dict(los_rescued_meshes=int(len(rescued)), menu_protected_meshes=int(protected.sum()), viewpoints=len(views), reachable_cells=len(reach), rays_per_point=RAYS, meshes=meshes,
                  hidden_meshes=len(hidden), hidden_triangles=hidden_tris, total_triangles=int(len(tris)),
                  estimated_index_saving=int(3*hidden_tris+3*len(hidden)),
                  hidden_by_material=dict(sorted(((names[i], 0) for i in hidden), key=lambda kv: kv[0])))
    by = {}
    for i in hidden:
        by[names[i]] = by.get(names[i], 0)+int(counts[i])
    report['hidden_by_material'] = dict(sorted(by.items(), key=lambda kv: -kv[1]))
    (work/'analysis.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'hidden_by_material'}), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('ident', choices=sorted(CONFIG))
    p.add_argument('--bsp'); p.add_argument('--work', default='visibility')
    a = p.parse_args(); analyse(a.ident, a.bsp, a.work)
