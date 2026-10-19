"""Close the play area of a battle royale area cut-out with invisible walls.

A cut-out (CONFIG bounds) ends abruptly at the box edge, so players could walk
off the converted world. Apex bounded these arenas with its ring; here the play
area (PLAY box, in port coordinates) gets vertical walls of native triangle
collision from below the lowest terrain to above the highest structure. They
are tessellated into STEP quads with both windings and appended with
match_collision_to_render.replace_collision (relocatable headers, grid rebuilt).
Nothing is drawn: the cut scenery beyond the wall stays visible.

Run after the native build/lighting steps, before packaging:
  python add_area_boundary.py apply thermal-station
  python add_area_boundary.py check thermal-station   # harness running on the map
"""
import json
import os
import sys

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from package_player_mods import digest

# Play boxes: the R5R deathmatch spawn hull plus 2,000 units (docs/candidates/poi-survey-2026-10-19.md).
PLAY = {'thermal-station': dict(min=[-5200, -4900], max=[5200, 4800], z=[-2100, 12000])}
STEP = 512.0


def walls(box):
    (x0, y0), (x1, y1), (z0, z1) = box['min'], box['max'], box['z']
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    zs = np.linspace(z0, z1, int(np.ceil((z1-z0)/STEP))+1); tris = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        n = int(np.ceil(max(abs(bx-ax), abs(by-ay))/STEP)); s = np.linspace(0, 1, n+1)
        xs, ys = ax+(bx-ax)*s, ay+(by-ay)*s
        for i in range(n):
            for j in range(len(zs)-1):
                a = (xs[i], ys[i], zs[j]); b = (xs[i+1], ys[i+1], zs[j]); c = (xs[i+1], ys[i+1], zs[j+1]); d = (xs[i], ys[i], zs[j+1])
                tris += [(a, b, c), (a, c, d), (a, c, b), (a, d, c)]  # both windings
    return np.asarray(tris, 'f4')


def apply(ident):
    from match_collision_to_render import replace_collision
    from repair_preview_index_padding import read_lumps
    from compact_preview_bsp import compact
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp'); receipt = out/'boundary.json'
    if receipt.exists() and json.loads(receipt.read_text())['bsp_after'] == digest(bsp):
        print('Boundary already applied to this build', flush=True); return
    before = digest(bsp); col = walls(PLAY[ident])
    l = read_lumps(bsp, tuple(range(128))); buf = {k: bytearray(v) for k, v in l.items()}
    first = len(l[0x45])//44
    replace_collision(l, buf, set(), set(), col)
    temp = bsp.with_suffix('.boundary.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    report = dict(play_box=PLAY[ident], wall_triangles=len(col), first_header=first, headers=len(buf[0x45])//44-first,
                  bsp_before=before, bsp_after=digest(bsp))
    receipt.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ('wall_triangles', 'headers')}), flush=True)


def check(ident):
    """Horizontal traces from inside the play box outwards must stop at the wall."""
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    box = PLAY[ident]; c = Controller(); rows = []
    (x0, y0), (x1, y1) = box['min'], box['max']
    for z in (0., 400., 1500.):
        for (px, py), (ex, ey), wall in (((0, y0+800), (0, y0-2000), y0), ((0, y1-800), (0, y1+2000), y1),
                                         ((x0+800, 0), (x0-2000, 0), x0), ((x1-800, 0), (x1+2000, 0), x1)):
            r = c.command('server', 'trace', px=px, py=py, pz=z, ex=ex, ey=ey, ez=z)['data']
            hit = [r['end'][0], r['end'][1]]; d = abs((hit[1] if px == 0 else hit[0])-wall)
            rows.append(dict(start=[px, py, z], end=r['end'], fraction=r['fraction'], start_solid=r['startSolid'],
                             stopped_at_wall=bool(r['fraction'] < 1 and d < 4), stopped_before=bool(r['fraction'] < 1 and d >= 4)))
    ok = all(r['stopped_at_wall'] or r['stopped_before'] or r['start_solid'] for r in rows)
    (folder(ident)/'boundary-check.json').write_text(json.dumps(dict(passed=ok, traces=rows), indent=2))
    print('passed' if ok else 'FAILED', sum(r['stopped_at_wall'] for r in rows), 'at wall,',
          sum(r['stopped_before'] for r in rows), 'on scenery first, of', len(rows), flush=True)
    if not ok:
        raise ValueError('A trace left the play area')


if __name__ == '__main__':
    {'apply': apply, 'check': check}[sys.argv[1]](sys.argv[2])
