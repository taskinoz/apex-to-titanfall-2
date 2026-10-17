"""Party Crasher fifth user report (q41-q50): locate the cause at each reported position.

For each point: undrawn collision nearby (collision samples farther than GAP from
any drawn triangle), attributed to omitted source placements whose LOD0 surface
lies on it, and the drawn materials around the point (for texture reports).

  python survey_party_report5.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from new_arena_ports import ROOT, folder
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree

OUT = folder('party-crasher')
BSP = OUT/'mp_party_crasher.bsp'
POINTS = {
    'q41 invisible object': (2435.1, 1904.1, 980.0),
    'q42 invisible geo': (451.8, 1214.1, 603.6),
    'q43 invisible geo': (844.4, 521.0, 603.6),
    'q44 missing table': (2842.6, 71.3, 991.9),
    'q45 missing table': (545.5, 2921.5, 981.5),
    'q46 missing 2 tables': (2608.0, 6.9, 1031.0),
    'q47 unnecessary details': (2894.4, -89.8, 986.4),
    'q48 unnecessary details': (-4256.1, 2248.2, 3371.8),
    'q49 glowing number': (3765.7, -2248.7, 951.4),
    'q50 black water': (-455.8, -1260.9, 1033.2),
}
RADIUS = 420
GAP = 10.0


def main():
    from analyse_visibility import render_triangles
    from audit_collision_visibility import native_collision, sample
    scene = json.loads((OUT/'scene.json').read_text()); index = asset_index('party-crasher')
    tris, mesh_of, names = render_triangles(BSP); tris = tris.astype('f8')
    centre = tris.mean(1); coll = native_collision(BSP); ccentre = coll.mean(1)
    report = {}; cache = {}
    def surface(p):
        stem = Path(p['model']).stem.lower()
        if stem not in index:
            return None
        if stem not in cache:
            try:
                cache[stem] = [np.asarray(s, 'f8').reshape(-1, 3, 12)[:, :, :3] for s in load(index[stem], 0, True)[0] if len(s)]
            except Exception:
                cache[stem] = []
        if not cache[stem]:
            return None
        return np.concatenate(cache[stem])@np.asarray(rotation(p['angles'])).T*p['scale']+np.asarray(p['origin'])
    for label, pt in POINTS.items():
        pt = np.asarray(pt)
        near = np.linalg.norm(centre-pt, axis=1) < RADIUS
        mats = Counter(names[m] for m in mesh_of[near])
        cnear = np.linalg.norm(ccentre-pt, axis=1) < RADIUS
        row = dict(point=pt.tolist(), drawn_materials=mats.most_common(25))
        if cnear.any():
            cs = sample(coll[cnear], 6.); ds = cKDTree(sample(tris[near], 6.)) if near.any() else None
            gap = ds.query(cs)[0] if ds else np.full(len(cs), 1e9)
            hidden = cs[gap > GAP]
            row['collision_samples'] = len(cs); row['undrawn_samples'] = len(hidden)
            if len(hidden):
                ht = cKDTree(hidden); owners = []
                for p in scene['omitted']:
                    if np.linalg.norm(np.asarray(p.get('origin', (1e9,)*3))-pt) > RADIUS+300:
                        continue
                    s = surface(p)
                    if s is None:
                        continue
                    on = ht.query(sample(s, 6.))[0] < 6
                    if on.sum() >= 10:
                        owners.append(dict(index=p['index'], model=Path(p['model']).stem, origin=p['origin'],
                                           samples=int(on.sum()), reason=p.get('reason')))
                owners.sort(key=lambda o: -o['samples'])
                row['undrawn_owners'] = owners[:20]
                lo, hi = hidden.min(0), hidden.max(0); row['undrawn_bounds'] = [lo.tolist(), hi.tolist()]
        report[label] = row
        print('==', label, row.get('undrawn_samples'), '/', row.get('collision_samples'))
        for o in row.get('undrawn_owners', [])[:8]:
            print('   ', o['index'], o['model'], o['samples'], [round(v) for v in o['origin']], (o['reason'] or '')[:50])
        print('   drawn:', [(n, c) for n, c in mats.most_common(8)])
    (OUT/'report5-survey.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
