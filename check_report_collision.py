"""Compare native collision with the drawn surface along the user's report views.

For each reported camera, traces several rays along the view (centre and
offsets). A native hit nearer than the first drawn surface by more than SLACK
means invisible collision; a drawn surface with no native hit behind it means
a walk-through. Needs a running harness on the build under test.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
sys.path.insert(0, str(ROOT/'test-harness'))

SLACK = 24.0
REACH = 600.0
OFFSETS = [(0, 0), (-.3, 0), (.3, 0), (0, -.25), (0, .25)]


def first_hit(tris, origin, d):
    v0 = tris[:, 0]; e1 = tris[:, 1]-v0; e2 = tris[:, 2]-v0
    h = np.cross(d, e2); a = np.einsum('ij,ij->i', e1, h); ok = np.abs(a) > 1e-9; f = np.where(ok, 1/np.where(ok, a, 1), 0)
    s = origin-v0; u = f*np.einsum('ij,ij->i', s, h); q = np.cross(s, e1); v = f*(q@d); t = f*np.einsum('ij,ij->i', e2, q)
    m = ok & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > .5) & (t < REACH)
    return float(t[m].min()) if m.any() else None


def check(ident, routes):
    from harness import Controller
    from analyse_visibility import render_triangles
    out = folder(ident); tris, mesh_of, names = render_triangles(out/(CONFIG[ident]['target']+'.bsp'))
    see = np.asarray([not any(w in n.lower() for w in ('sky', 'water', 'glass', 'decal', 'grass', 'leaf', 'leaves', 'bush', 'foliage')) for n in names])[mesh_of]
    tris = tris[see].astype('f8'); c = Controller(); rows = []
    for route in routes:
        for sh in json.loads(Path(route).read_text())['shots'][1:]:
            cam = np.asarray(sh['origin']); p, y = map(math.radians, sh['angles'][:2])
            f = np.array([math.cos(p)*math.cos(y), math.cos(p)*math.sin(y), -math.sin(p)]); r = np.array([math.sin(y), -math.cos(y), 0.]); u = np.cross(r, f)
            res = []
            for dx, dy in OFFSETS:
                d = f+dx*r+dy*u; d /= np.linalg.norm(d); end = cam+d*REACH
                t = c.command('server', 'trace', px=float(cam[0]), py=float(cam[1]), pz=float(cam[2]), ex=float(end[0]), ey=float(end[1]), ez=float(end[2]))['data']
                native = None if t['fraction'] >= 1 or t['startSolid'] else t['fraction']*REACH
                drawn = first_hit(tris, cam, d)
                kind = 'start-solid' if t['startSolid'] else 'ok'
                if not t['startSolid']:
                    if native is not None and (drawn is None or native < drawn-SLACK):
                        kind = 'invisible collision'
                    elif drawn is not None and (native is None or native > drawn+SLACK):
                        kind = 'walk-through'
                res.append(dict(offset=[dx, dy], native=native, drawn=drawn, kind=kind))
            rows.append(dict(name=sh['name'], rays=res))
            print(f"{sh['name']:34s}", ' '.join(x['kind'][:10].ljust(10) for x in res), flush=True)
    return rows


if __name__ == '__main__':
    ident, *routes = sys.argv[1:]
    rows = check(ident, routes)
    (folder(ident)/'report-collision-check.json').write_text(json.dumps(rows, indent=2))
