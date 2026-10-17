"""Phase Runner 1.7.0: rock collision matched to the drawn LOD (Firing Range 0.5.1 method).

Phase Runner's boundary cliffs and rocks are drawn at coarse authored LODs but
collide with their full source BVH: invisible rock to bump into and visible rock
to sink into (18% of reachable collision had no drawn surface within 24 units).

* measure: for each rock owner in collision-ownership.json whose primitives
  are all active, find the drawn authored LOD by matching its transformed
  vertices against the BSP vertex positions, then measure both directions
  (collider farther than GAP from the drawn surface, drawn surface farther
  than GAP from the collider).
* apply: owners over THRESHOLD drawn at LOD > 0 have their source primitives
  removed from the collision grid (data stays serialized) and get triangle
  collision made from the drawn triangles. Spawns are not moved (see apply). Owners with any disabled primitive
  (tunnel caps, catwalk clips) are never touched.

Operates on the blend work copy (phase_runner_blend.py patch/materials first).
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from phase_runner_blend import ROOT, WORK, PACKAGE, write
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_center_detail import active
from match_collision_to_render import sample, brush_triangles, replace_collision

GAP = 20.0
THRESHOLD = .15
MATCH = .5
PROJECT = WORK/'collision'
BSP = WORK/'mp_phase_runner.bsp'
STATIC = Path('D:/Games/ApexToTitanfallWork/project-storage/output/phase-runner/static-props.json')


def lods(stem, index, cache):
    if stem not in cache:
        cache[stem] = []
        try:
            levels = struct.unpack_from('<18Q', (index[stem]/(index[stem].name+'.vg')).read_bytes(), 16)[13]
            for lod in range(levels):
                sections, slots, skins = load(index[stem], lod, True)
                keep = [np.asarray(s, 'f8').reshape(-1, 3, 12)[:, :, :3] for s, slot in zip(sections, slots)
                        if len(s) and not any(w in skins[0][slot].lower() for w in ('godray', 'decal', 'glass', 'leaf'))]
                cache[stem].append(np.concatenate(keep) if keep else np.empty((0, 3, 3)))
        except Exception:
            pass
    return cache[stem]


def collider(l, act, owner, planes, pos, words, heads):
    tris = []; inactive = 0
    for i in range(owner['first_brush'], owner['first_brush']+owner['brushes']):
        if (0, i) not in act:
            inactive += 1; continue
        tris.append(brush_triangles(struct.unpack_from('<3f2BH3fI', l[0x5c], i*32), planes))
    for i in range(owner['first_header'], owner['first_header']+owner['headers']):
        if (0x40, i) not in act:
            inactive += 1; continue
        h = heads[i]; w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        tris.append(pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)])
    return (np.concatenate(tris) if tris else np.empty((0, 3, 3))), inactive


def measure():
    from plan_arena_fill import model_index
    PROJECT.mkdir(parents=True, exist_ok=True)
    owners = json.loads((PACKAGE/'collision-ownership.json').read_text())['owners']
    props = {p['index']: p for p in json.loads(STATIC.read_text())}
    l = read_lumps(BSP, (1, 3, 0x42, 0x45, 0x57, 0x59, 0x5c)); act = active(l)
    planes = np.frombuffer(l[1], '<f4').reshape(-1, 4).astype('f8'); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8')
    words = np.frombuffer(l[0x42], '<u4'); heads = list(struct.iter_unpack('<6h4i4f', l[0x45]))
    import analyse_visibility as vis
    drawn_pos = cKDTree(np.unique(vis.render_triangles(BSP)[0].reshape(-1, 3).astype('f8'), axis=0))
    index = model_index(); cache = {}; rows = []
    for o in owners:
        p = props.get(o['index'])
        if p is None or 'rock' not in o['model'] or not (o['brushes'] or o['headers']):
            continue
        stem = Path(o['model']).stem.lower()
        if stem not in index:
            continue
        m = np.asarray(rotation(p['angles'])); best = None
        for lod, t in enumerate(lods(stem, index, cache)):
            if not len(t):
                continue
            w = t@m.T*p.get('scale', 1)+np.asarray(p['origin'])
            d, _ = drawn_pos.query(w.reshape(-1, 3)[::7]); f = float(np.mean(d < MATCH))
            if best is None or f > best[0]:
                best = (f, lod, w)
        if best is None or best[0] < .9:
            continue
        col, inactive = collider(l, act, o, planes, pos, words, heads)
        if inactive or not len(col):
            continue
        drawn = best[2]
        dc, _ = cKDTree(sample(drawn, 16)).query(sample(col, 16)); dd, _ = cKDTree(sample(col, 16)).query(sample(drawn, 16))
        rows.append(dict(index=o['index'], model=o['model'], lod=best[1], lod_match=round(best[0], 3),
                         invisible=round(float(np.mean(dc > GAP)), 4), walk_through=round(float(np.mean(dd > GAP)), 4),
                         brushes=list(range(o['first_brush'], o['first_brush']+o['brushes'])),
                         headers=list(range(o['first_header'], o['first_header']+o['headers']))))
    write(PROJECT/'measure.json', rows)
    bad = [r for r in rows if max(r['invisible'], r['walk_through']) > THRESHOLD and r['lod'] > 0]
    print('rock owners measured', len(rows), 'over threshold at LOD>0', len(bad), flush=True)
    for r in sorted(bad, key=lambda r: -r['invisible'])[:15]:
        print(f"  {r['index']:5d} {Path(r['model']).stem:40s} LOD{r['lod']} invisible {r['invisible']:.2f} walk-through {r['walk_through']:.2f}")


def apply():
    from plan_arena_fill import model_index
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; rerun phase_runner_blend.py patch/materials to rebuild')
    rows = json.loads((PROJECT/'measure.json').read_text())
    chosen = [r for r in rows if max(r['invisible'], r['walk_through']) > THRESHOLD and r['lod'] > 0]
    props = {p['index']: p for p in json.loads(STATIC.read_text())}; index = model_index(); cache = {}; new = []
    for r in chosen:
        p = props[r['index']]; t = lods(Path(r['model']).stem.lower(), index, cache)[r['lod']]
        new.append(t@np.asarray(rotation(p['angles'])).T*p.get('scale', 1)+np.asarray(p['origin']))
    col = np.concatenate(new).astype('<f4')
    col = col[np.linalg.norm(np.cross(col[:, 1]-col[:, 0], col[:, 2]-col[:, 0]), axis=1) > 1e-3]
    l = read_lumps(BSP, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    drop_b = {i for r in chosen for i in r['brushes']}; drop_h = {i for r in chosen for i in r['headers']}
    encoded = replace_collision(l, buf, drop_b, drop_h, col)
    if len(buf[0x45])//44 >= 65535:
        raise ValueError('Native triangle header capacity exceeded')
    # No spawn snapping: Phase Runner's arena floor covers buried cliff rock, so the
    # Firing Range 'highest drawn rock below' rule would pull floor spawns underground.
    # The native spawn check (clear and supported) validates every spawn instead.
    moved = []
    temp = BSP.with_suffix('.collision.bsp'); compact(BSP, temp, buf); os.replace(temp, BSP)
    report = dict(replaced=len(chosen), spawns_moved=moved, source_brushes_disabled=len(drop_b), source_headers_disabled=len(drop_h),
                  drawn_collision_triangles=int(len(col)), new_headers=len(encoded[0x45])//44, threshold=THRESHOLD, gap=GAP,
                  placements=[{k: r[k] for k in ('index', 'model', 'lod', 'invisible', 'walk_through')} for r in chosen])
    write(PROJECT/'result.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'placements'}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['measure', 'apply'])
    dict(measure=measure, apply=apply)[p.parse_args().action]()
