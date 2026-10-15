"""Remove invisible player clips left by Apex's script-spawned range targets.

The Firing Range world collision keeps clip-only leaves (contents with player
clip 0x10000 and no solid/window bits) around shooting-range target markers.
In Apex, scripts spawn rotating/folding targets inside them; the port spawns
none, so the clips are invisible walls. A clip face is removed only if it is
(1) clip-only, (2) within RADIUS of a target marker, and (3) has no drawn
surface within GAP. Affected world triangle groups are disabled in the grid
and their remaining triangles re-appended unchanged.
"""
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_center_detail import active
from match_collision_to_render import replace_collision, sample

RADIUS = 250.0
GAP = 20.0
MARKERS = ('shooting_range_rotating_target', 'shooting_range_folding_target', 'firingrange_target_fold', 'frc_challenge1_target')


def keys(t):
    return {tuple(sorted(tuple(np.round(v, 2)) for v in f)) for f in t}


def run(ident='firing-range'):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp'); work = out/'target-clips'; backup = out/'before-target-clips'
    if (work/'result.json').exists():
        raise ValueError('Already applied')
    work.mkdir(exist_ok=True)
    if not backup.exists():
        backup.mkdir(); shutil.copy2(bsp, backup/bsp.name)
    off = np.asarray(CONFIG[ident]['offset'], 'f8'); scene = json.loads((out/'scene.json').read_text())
    marks = np.asarray([np.asarray([float(v) for v in e['origin'].split()])+off for e in scene['source_entities']
                        if e.get('script_name') in MARKERS or e.get('targetname') in MARKERS])
    clip = []; g = None; pts = []
    for line in open(out/'collision/world-collision-regular.obj'):
        if line.startswith('g '):
            c = int(line.split()[1].split('_')[1], 16); g = (c & 0x10000) and not (c & 0xb); pts = []
        elif line.startswith('v '):
            pts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f ') and g:
            clip.extend([pts[0], pts[i], pts[i+1]] for i in range(1, len(pts)-1))
    clip = np.asarray(clip, 'f8')
    from analyse_visibility import render_triangles
    near_marker = cKDTree(marks).query(clip.mean(1))[0] <= RADIUS
    # Only render geometry around the markers is needed for the visibility test.
    tris, mesh_of, names = render_triangles(bsp)
    keep = np.asarray([not any(w in n.lower() for w in ('sky', 'water')) for n in names])[mesh_of]
    tris = tris[keep].astype('f8'); tris = tris[cKDTree(marks).query(tris.mean(1))[0] <= RADIUS+GAP+600]
    drawn = cKDTree(sample(tris, 8))
    invisible = np.zeros(len(clip), bool)
    for k in np.flatnonzero(near_marker):
        invisible[k] = (drawn.query(sample(clip[k][None], 8))[0] > GAP).all()
    remove = clip[near_marker & invisible]
    want = keys(remove.astype('f4').astype('f8'))
    base = json.loads((out/'before-0.2.0/physics.json').read_text()); world_groups = base['triangle_headers']-sum(o['headers'] for o in base['owners'])
    l = read_lumps(bsp, range(128)); buf = {k: bytearray(v) for k, v in l.items()}; act = active(l)
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8'); words = np.frombuffer(l[0x42], '<u4'); heads = list(struct.iter_unpack('<6h4i4f', l[0x45]))
    drop_h, keep_tris, removed = set(), [], 0
    for i in range(world_groups):
        if (0x40, i) not in act:
            continue
        h = heads[i]; w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        f = pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)]
        hit = np.asarray([tuple(sorted(tuple(np.round(v, 2)) for v in t)) in want for t in f])
        if hit.any():
            drop_h.add(i); removed += int(hit.sum()); keep_tris.append(f[~hit])
    if not drop_h:
        raise ValueError('No target clip faces matched the native world collision')
    col = np.concatenate(keep_tris).astype('<f4')
    encoded = replace_collision(l, buf, set(), drop_h, col)
    temp = bsp.with_suffix('.clips.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    report = dict(markers=len(marks), clip_faces_near_markers=int(near_marker.sum()), removed_invisible_clip_triangles=removed,
                  world_groups_rebuilt=len(drop_h), retained_triangles_reappended=int(len(col)), radius=RADIUS, gap=GAP)
    (work/'result.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report), flush=True)


if __name__ == '__main__':
    run(*sys.argv[1:])
