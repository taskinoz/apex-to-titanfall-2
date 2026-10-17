"""Make collision match what is drawn for coarse-LOD source placements.

The previews draw many props at a coarse authored LOD (budget), while their
collision is the full source PHY/BVH. The result is invisible rock to bump
into, and visible rock to fall into. For every placement whose collider was
built by build_composite_map (deterministic order: brush 0 sentinel, then each
owner's brushes; world triangle groups, then each owner's groups), this:

* measures both directions per placement: collider surface farther than GAP
  from the drawn LOD (invisible collision), and drawn surface farther than GAP
  from the collider (walk-through);
* for placements over THRESHOLD, removes the source collider from the
  collision grid (data stays serialized) and appends triangle collision made
  from the exact drawn LOD triangles.

Render data, entities, lighting and every other collider are unchanged.
"""
import argparse
import collections
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree, ConvexHull, HalfspaceIntersection
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from native_triangle_collision import encode
from build_center_detail import active

GAP = 20.0
THRESHOLD = .15
SPAWN_MARGIN = 96
SKIP = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier', 'shimmer', 'decal', 'glass', 'grass', 'leaf', 'leaves')


def sample(tris, spacing):
    out = []
    for t in tris:
        e = max(np.linalg.norm(t[1]-t[0]), np.linalg.norm(t[2]-t[0]), np.linalg.norm(t[2]-t[1]))
        k = max(1, min(int(e//spacing), 64))
        a, b = np.meshgrid(np.arange(k+1), np.arange(k+1)); m = (a+b) <= k
        out.append(np.stack([k-a[m]-b[m], a[m], b[m]], 1)/k@t)
    return np.concatenate(out) if out else np.empty((0, 3))


def brush_triangles(rec, planes):
    c = np.asarray(rec[:3]); e = np.asarray(rec[6:9]); count = rec[4]; off = rec[9]
    hs = [[1, 0, 0, -(c[0]+e[0])], [-1, 0, 0, c[0]-e[0]], [0, 1, 0, -(c[1]+e[1])], [0, -1, 0, c[1]-e[1]],
          [0, 0, 1, -(c[2]+e[2])], [0, 0, -1, c[2]-e[2]]]
    hs += [[n[0], n[1], n[2], -n[3]] for n in planes[1+off:1+off+count]]
    try:
        pts = HalfspaceIntersection(np.asarray(hs, 'f8'), c).intersections
        return pts[ConvexHull(pts).simplices]
    except Exception:
        return np.empty((0, 3, 3))


def owner_ranges(out):
    """Brush and header index ranges per owner of the original build."""
    base = json.loads((out/'before-0.2.0/physics.json').read_text())
    owners = base['owners']; headers = base['triangle_headers']
    world_groups = headers-sum(o['headers'] for o in owners)
    b, h, rows = 1, world_groups, {}
    for o in owners:
        rows[o['index']] = (range(b, b+o['brushes']), range(h, h+o['headers']), o)
        b += o['brushes']; h += o['headers']
    if h != headers:
        raise ValueError('Owner header ranges do not cover the original build')
    return rows


def render_geometry(p, cache):
    f = p['folder']
    if (f, p['lod']) not in cache:
        cache[f, p['lod']] = load(f, p['lod'], False)
    sections, slots, skins = cache[f, p['lod']]
    skin = skins[min(p['skin'], len(skins)-1)]; matrix = np.asarray(rotation(p['angles'])); out = []
    for s, slot in zip(sections, slots):
        if len(s) and not any(w in skin[slot].lower() for w in SKIP):
            out.append(np.asarray(s, 'f8')[:, :, :3]@matrix.T*p['scale']+p['origin'])
    return np.concatenate(out) if out else np.empty((0, 3, 3))


def measure(ident):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp')
    l = read_lumps(bsp, (1, 3, 0x42, 0x45, 0x57, 0x59, 0x5c)); act = active(l)
    planes = np.frombuffer(l[1], '<f4').reshape(-1, 4).astype('f8')
    brushes = list(struct.iter_unpack('<3f2BH3fI', l[0x5c])); heads = list(struct.iter_unpack('<6h4i4f', l[0x45]))
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8'); words = np.frombuffer(l[0x42], '<u4')
    ranges = owner_ranges(out); scene = json.loads((out/'scene.json').read_text())
    placements = {p['index']: p for p in scene['placements']}; cache = {}; rows = []
    for index, (br, hr, o) in ranges.items():
        p = placements.get(index)
        if not p or 'folder' not in p or not (Path(p['folder'])/(Path(p['folder']).name+'.vg')).exists():
            continue
        coll = [brush_triangles(brushes[i], planes) for i in br if (0, i) in act]
        for i in hr:
            if (0x40, i) not in act:
                continue
            h = heads[i]; w = words[h[7]:h[7]+h[4]]; ix = w & 1023
            coll.append(pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)])
        coll = np.concatenate(coll) if coll else np.empty((0, 3, 3))
        drawn = render_geometry(p, cache)
        if not len(coll) or not len(drawn):
            continue
        cs, ds = sample(coll, 8), sample(drawn, 8)
        c2r = float((cKDTree(ds).query(cs)[0] > GAP).mean()); r2c = float((cKDTree(cs).query(ds)[0] > GAP).mean())
        rows.append(dict(index=index, model=Path(p['model']).stem, lod=p['lod'], invisible=round(c2r, 3), walk_through=round(r2c, 3),
                         brushes=list(br), headers=list(hr), extent=float(np.ptp(drawn.reshape(-1, 3), 0).max())))
    (out/'collision-match.json').write_text(json.dumps(rows))
    bad = [r for r in rows if max(r['invisible'], r['walk_through']) > THRESHOLD]
    print(ident, 'placements measured', len(rows), 'mismatched', len(bad))
    by = collections.Counter((r['model'], r['lod']) for r in bad)
    for (m, lod), n in by.most_common(25):
        sel = [r for r in bad if r['model'] == m and r['lod'] == lod]
        print(f"  {n:4d} {m:45s} LOD{lod} invisible {np.mean([r['invisible'] for r in sel]):.2f} walk-through {np.mean([r['walk_through'] for r in sel]):.2f}")
    return rows


def replace_collision(l, buf, drop_b, drop_h, col):
    """Disable source primitives (grid only) and append triangle collision; returns the encoding."""
    # Append the drawn-shape triangle collision (relocatable headers); none when only disabling.
    encoded = None
    if len(col):
        centers = col.mean(1); q = np.floor(centers/128).astype(np.int32); col = col[np.lexsort((centers[:, 2], q[:, 1], q[:, 0]))]
        encoded, _ = encode([col[i:i+96] for i in range(0, len(col), 96)])
        vb = len(buf[3])//12; wb = len(buf[0x42])//4; nb = len(buf[0x44])//16
        for at in range(0, len(encoded[0x45]), 44):
            h = list(struct.unpack_from('<6h4i4f', encoded[0x45], at)); h[6] += vb; h[7] += wb; h[8] += nb
            buf[0x45].extend(struct.pack('<6h4i4f', *h))
        for k in (3, 0x42, 0x44, 0x60):
            buf[k].extend(encoded[k])
    # New headers must be active: mark them by giving them grid membership.
    first_new = len(l[0x45])//44
    tmp = {k: bytes(v) for k, v in buf.items()}
    # active() reads the old grid, so extend the active set explicitly.
    old_active = active(l)
    def grid():
        from extend_prop_collision import pack_grid
        brushes = list(struct.iter_unpack('<3f2BH3fI', tmp[0x5c]))
        bb = [((np.asarray(r[:3])-r[6:9]).tolist(), (np.asarray(r[:3])+r[6:9]).tolist()) for r in brushes]
        pos = np.frombuffer(tmp[3], '<f4').reshape(-1, 3); words = np.frombuffer(tmp[0x42], '<u4'); tb = []
        for h in struct.iter_unpack('<6h4i4f', tmp[0x45]):
            w = words[h[7]:h[7]+h[4]]; ix = w & 1023
            f = pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)]
            tb.append((f.min((0, 1)).tolist(), f.max((0, 1)).tolist()))
        keep_b = [i for i in range(len(bb)) if (0, i) in old_active and i not in drop_b]
        keep_t = [i for i in range(len(tb)) if ((0x40, i) in old_active and i not in drop_h) or i >= first_new]
        g = pack_grid([bb[i] for i in keep_b]+[tb[i] for i in keep_t]); off = len(keep_b)
        p = bytearray(g[0x59]); sets = bytearray(g[0x57])
        def remap(word):
            k = (word >> 8) & 65535
            return (keep_b[k] << 8) | (word & 255) if k < off else (0x40 << 24) | (keep_t[k-off] << 8) | (word & 255)
        for at in range(0, len(p), 4):
            struct.pack_into('<I', p, at, remap(struct.unpack_from('<I', p, at)[0]))
        for at in range(0, len(sets), 8):
            if struct.unpack_from('<H', sets, at+2)[0] == 1:
                struct.pack_into('<I', sets, at+4, remap(struct.unpack_from('<I', sets, at+4)[0]))
        g[0x59] = p; g[0x57] = sets
        return g
    buf.update({k: bytearray(v) for k, v in grid().items()})
    return encoded


def snap_spawns(buf, rock_tris, bsp):
    """Move spawn markers near replaced rocks onto the highest drawn surface below them."""
    from repair_environment_lighting import text_entities
    from verify_collision_match import visual_top
    if not rock_tris:
        return []
    import repair_environment_lighting as rel
    from analyse_visibility import render_triangles
    rocks = np.concatenate(rock_tris); lo = rocks.reshape(-1, 3).min(0)-SPAWN_MARGIN; hi = rocks.reshape(-1, 3).max(0)+SPAWN_MARGIN
    allt, mesh_of, names = render_triangles(bsp)
    solid = np.asarray([not any(w in n.lower() for w in ('sky', 'water', 'glass', 'decal', 'grass', 'bush', 'leaf')) for n in names])[mesh_of]
    tris = allt[solid].astype('f8'); data = bytes(buf[0])
    rows = list(rel.shared.Entities.from_bytes(data[data.index(b'{'):]))
    moved = []
    for e in rows:
        if not (e.get('classname', '').startswith('info_spawnpoint') or e.get('classname') == 'info_player_start'):
            continue
        x, y, z = (float(v) for v in e['origin'].split())
        # Any spawn not standing on a drawn surface was supported by a mismatched collider.
        top = visual_top(tris, x, y, z+96)
        if top is not None and abs(top-z) > 2 and abs(top-z) < 400:
            e['origin'] = f'{x} {y} {top+1:.3f}'; moved.append(dict(classname=e['classname'], old_z=z, new_z=top+1))
    if moved:
        buf[0] = bytearray(text_entities(rows))
    return moved


def apply(ident):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp'); work = out/'collision-match'
    backup = out/'before-collision-match'
    if (work/'result.json').exists():
        raise ValueError('Already applied; restore before-collision-match first')
    work.mkdir(exist_ok=True)
    if not backup.exists():
        backup.mkdir()
        for n in (bsp.name, 'physics.json', 'physics.npz'):
            shutil.copy2(out/n, backup/n)
    rows = json.loads((out/'collision-match.json').read_text())
    scene = {p['index']: p for p in json.loads((out/'scene.json').read_text())['placements']}; cache = {}
    # Spawn markers were validated on the source colliders: keep those under or near them.
    from repair_environment_lighting import entities
    spawns = np.asarray([[float(v) for v in e['origin'].split()] for e in entities(bsp)
                         if e.get('classname', '').startswith('info_spawnpoint') or e.get('classname') == 'info_player_start'])
    def near_spawn(r):
        g = render_geometry(scene[r['index']], cache).reshape(-1, 3)
        lo, hi = g.min(0)-[SPAWN_MARGIN, SPAWN_MARGIN, SPAWN_MARGIN], g.max(0)+[SPAWN_MARGIN, SPAWN_MARGIN, SPAWN_MARGIN]
        return bool(len(spawns) and np.any(np.all((spawns >= lo) & (spawns <= hi), axis=1)))
    candidates = [r for r in rows if max(r['invisible'], r['walk_through']) > THRESHOLD and r['lod'] > 0]
    # Spawns standing on replaced rocks are moved onto the drawn surface instead
    # of keeping the mismatched collider; native spawn checks then re-validate them.
    chosen = candidates; kept_for_spawns = 0
    spawn_rocks = [r for r in candidates if near_spawn(r)]
    new = [render_geometry(scene[r['index']], cache) for r in chosen]
    col = np.concatenate(new).astype('<f4')
    good = np.linalg.norm(np.cross(col[:, 1]-col[:, 0], col[:, 2]-col[:, 0]), axis=1) > 1e-3; col = col[good]
    l = read_lumps(bsp, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    drop_b = {i for r in chosen for i in r['brushes']}; drop_h = {i for r in chosen for i in r['headers']}
    encoded = replace_collision(l, buf, drop_b, drop_h, col)
    if len(buf[0x45])//44 >= 65535:
        raise ValueError('Native triangle header capacity exceeded')
    moved = snap_spawns(buf, [render_geometry(scene[r['index']], cache) for r in spawn_rocks], bsp)
    temp = bsp.with_suffix('.collision.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    report = dict(replaced=len(chosen), kept_for_spawns=kept_for_spawns, spawns_moved=moved, source_brushes_disabled=len(drop_b), source_headers_disabled=len(drop_h),
                  drawn_collision_triangles=int(len(col)), new_headers=len(encoded[0x45])//44, threshold=THRESHOLD, gap=GAP,
                  placements=[dict(index=r['index'], model=r['model'], lod=r['lod'], invisible=r['invisible'],
                                   walk_through=r['walk_through']) for r in chosen])
    (work/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'placements'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['measure', 'apply']); p.add_argument('ident', choices=sorted(CONFIG))
    a = p.parse_args(); measure(a.ident) if a.action == 'measure' else apply(a.ident)
