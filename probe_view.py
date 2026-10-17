"""Cast a screenshot's view ray through a native BSP and list every drawn surface it crosses.

The Northstar debug overlay prints `pos` (player origin) and `ang` (pitch yaw roll).
The ray starts at `pos` and follows the view direction; every triangle hit
within RANGE is listed with its distance, material and mesh. Two hits with
different materials within a few units of each other are coplanar overlaps
(z-fighting).

  python probe_view.py <bsp> x y z pitch yaw [--spread N]
"""
import argparse
import json

import numpy as np

EYE = 0.0  # the overlay `pos` is the camera position
RANGE = 4000.0


def direction(pitch, yaw):
    p, y = np.radians(pitch), np.radians(yaw)
    return np.asarray([np.cos(p)*np.cos(y), np.cos(p)*np.sin(y), -np.sin(p)])


def hits(tris, origin, d, limit=RANGE):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = b-a, c-a; h = np.cross(d, e2); det = (e1*h).sum(1)
    ok = np.abs(det) > 1e-9; f = np.zeros_like(det); f[ok] = 1/det[ok]
    s = origin-a; u = f*(s*h).sum(1); q = np.cross(s, e1); v = f*(q@d); t = f*(e2*q).sum(1)
    m = ok & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > 0) & (t < limit)
    i = np.flatnonzero(m)
    return i[np.argsort(t[i])], t


def probe(bsp, pos, ang, spread=0, cache={}):
    from analyse_visibility import render_triangles
    if bsp not in cache:
        tris, mesh_of, names = render_triangles(bsp); cache[bsp] = (tris.astype('f8'), mesh_of, names)
    tris, mesh_of, names = cache[bsp]
    origin = np.asarray(pos, 'f8')+[0, 0, EYE]; out = []
    for dp in range(-spread, spread+1):
        for dy in range(-spread, spread+1):
            d = direction(ang[0]+dp*2, ang[1]+dy*2); order, t = hits(tris, origin, d)
            out.append(dict(offset=[dp*2, dy*2], hits=[dict(distance=round(float(t[i]), 2), material=names[mesh_of[i]],
                                                            mesh=int(mesh_of[i]), triangle=int(i)) for i in order[:6]]))
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('bsp'); p.add_argument('coords', nargs=5, type=float); p.add_argument('--spread', type=int, default=0)
    a = p.parse_args()
    for row in probe(a.bsp, a.coords[:3], a.coords[3:], a.spread):
        print(row['offset'], [(h['distance'], h['material'], h['mesh']) for h in row['hits']])
