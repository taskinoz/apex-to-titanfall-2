"""Find collision with no visible surface nearby ("invisible collision").

Samples the decoded source world collision (which also contains static-prop
colliders baked into the world BVH) and every appended prop collider, then
measures the distance from each sample to the nearest rendered triangle of
the native BSP. Samples farther than GAP units are invisible collision. They
are clustered and attributed to the source placement whose transformed
bounds contain them, with its current render LOD or omission reason.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree
from analyse_visibility import render_triangles

GAP = 24.0
SPACING = 16.0


def sample(tris, spacing):
    out = []
    for t in tris:
        e = max(np.linalg.norm(t[1]-t[0]), np.linalg.norm(t[2]-t[0]), np.linalg.norm(t[2]-t[1]))
        if e > 3000:
            continue  # distant backdrop shells, not player-scale collision
        k = max(1, min(int(e//spacing), 128))
        a, b = np.meshgrid(np.arange(k+1), np.arange(k+1)); m = (a+b) <= k
        w = np.stack([k-a[m]-b[m], a[m], b[m]], 1)/k
        out.append(w@t)
    return np.concatenate(out)


def native_collision(bsp):
    """Surface triangles of the active native collision: brushes and triangle headers."""
    import struct
    from scipy.spatial import ConvexHull, HalfspaceIntersection
    from repair_preview_index_padding import read_lumps
    from build_center_detail import active
    l = read_lumps(bsp, (1, 3, 0x42, 0x45, 0x57, 0x59, 0x5c))
    act = active(l)
    planes = np.frombuffer(l[1], '<f4').reshape(-1, 4).astype('f8')
    out = []
    for i, r in enumerate(struct.iter_unpack('<3f2BH3fI', l[0x5c])):
        if (0, i) not in act:
            continue
        c = np.asarray(r[:3]); e = np.asarray(r[6:9]); count = r[4]; off = r[9]
        hs = [[1, 0, 0, -(c[0]+e[0])], [-1, 0, 0, c[0]-e[0]], [0, 1, 0, -(c[1]+e[1])], [0, -1, 0, c[1]-e[1]],
              [0, 0, 1, -(c[2]+e[2])], [0, 0, -1, c[2]-e[2]]]
        for n in planes[1+off:1+off+count]:
            hs.append([n[0], n[1], n[2], -n[3]])
        try:
            pts = HalfspaceIntersection(np.asarray(hs), c).intersections
            hull = ConvexHull(pts)
            out.append(pts[hull.simplices])
        except Exception:
            lo, hi = c-e, c+e  # fall back to the bounding box
            corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            out.append(corners[ConvexHull(corners).simplices])
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8'); words = np.frombuffer(l[0x42], '<u4')
    for i, h in enumerate(struct.iter_unpack('<6h4i4f', l[0x45])):
        if (0x40, i) not in act:
            continue
        w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        out.append(pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)])
    return np.concatenate(out)


def audit(ident):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp')
    tris, mesh_of, names = render_triangles(bsp)
    see = np.asarray([not any(w in n.lower() for w in ('sky', 'water')) for n in names])[mesh_of]
    render = sample(tris[see].astype('f8'), SPACING/2)
    tree = cKDTree(render)
    coll = native_collision(bsp)
    # Only collision a player can reach matters.
    reach = out/'visibility/reachable.npy'
    if reach.exists():
        rd, _ = cKDTree(np.load(reach)).query(coll.mean(1))
        coll = coll[rd < 400]
    pts = sample(coll, SPACING)
    d, _ = tree.query(pts, distance_upper_bound=GAP*4)
    bad = pts[d > GAP]
    scene = json.loads((out/'scene.json').read_text())
    inv = json.loads((out/'source-inventory.json').read_text())['props']
    rows = {p['index']: ('rendered', p.get('lod')) for p in scene['placements']}
    rows.update({p['index']: ('omitted', p.get('reason')) for p in scene['omitted']})
    centres = np.asarray([p['origin'] for p in inv])
    ctree = cKDTree(centres)
    owner = Counter(); examples = defaultdict(list)
    _, near = ctree.query(bad)
    for p, j in zip(bad, near):
        key = (Path(inv[j]['model']).stem,)+rows.get(inv[j]['index'], ('outside', None))
        owner[key] += 1
        if len(examples[key]) < 3:
            examples[key].append([round(float(x)) for x in p])
    # cluster bad samples into 256-unit cells for location reporting
    cells = Counter(map(tuple, np.floor(bad/256).astype(int)))
    report = dict(collision_samples=len(pts), invisible_samples=int(len(bad)), fraction=round(len(bad)/len(pts), 4),
                  by_nearest_placement=[dict(model=k[0], status=k[1], detail=k[2], samples=v, examples=examples[k])
                                        for k, v in owner.most_common(60)],
                  worst_cells=[dict(centre=[int(c)*256+128 for c in k], samples=int(v)) for k, v in cells.most_common(40)])
    (out/'collision-visibility.json').write_text(json.dumps(report, indent=2))
    print(ident, 'samples', len(pts), 'invisible', len(bad), report['fraction'])
    for r in report['by_nearest_placement'][:25]:
        print(f"  {r['samples']:6d} {r['model']:45s} {r['status']:9s} {r['detail']}")
    return report


if __name__ == '__main__':
    for ident in sys.argv[1:]:
        audit(ident)
