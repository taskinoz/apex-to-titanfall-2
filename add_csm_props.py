"""List a port's native static props as sun-shadow (cascaded shadow map) casters.

The world builds write an empty CSM tree (0x63: one inverted root per shadow environment, 0x64 empty), so static
props never cast real-time sun shadows: Thunderdome's 6,757 props shadow the lightmaps (rebake_native_prop_shadows.py)
but not players, or each other near the camera. Retail lists them: Homestead's gameplay environment has 5,162
nodes over 6,833 of its 16,146 props, at most 24 direct references per node.

Layout (MRVN-Radiant docs/respawn/RESPAWN_TF2_LUMPS.md, checked here on Homestead): 0x63 uses the cell AABB node
layout, in light space with z = -sun, x = normalize(sun.y, -sun.x, 0), y = z x x, where sun is the shadow
environment's normal; 6,809 of Homestead's 6,833 referenced prop origins lie inside their node's box with that basis
and 5 with the sun negated. 0x64 holds object ids, the OBJ_REFERENCES namespace: static props start at the first sky
mesh rounded up to 64. A shadow environment (0x05) owns nodes and references [first, last).

Casters: every placement with a world radius of at least MIN_RADIUS, except grass, flowers and other ground cover
(retail grass has the no-shadow flag). Each prop's box is its drawn LOD's light-space bounds.

  python add_csm_props.py thunderdome <package>
"""
import json
import os
import re
import struct
import sys
from pathlib import Path

import numpy as np
from build_visibility_cells import placements, model_triangles
from build_native_props import asset_index
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact

MIN_RADIUS = 48.
LEAF = 16
NO_SHADOW = re.compile(r'grass|flower|clump|fern|weed|moss|ivy|ground_?cover|debris_small|pebble')
NODE = '<3f2BH3f2H'
ENV = '<6i3f'
REPORT = 'csm-props.json'


def light_basis(sun):
    sun = np.asarray(sun, 'f8'); z = -sun; x = np.array([sun[1], -sun[0], 0.]); x /= np.linalg.norm(x)
    return np.stack((x, np.cross(z, x), z))


def tree(boxes, ids):
    """Binary median-split AABB tree in the cell node layout; references contiguous per subtree."""
    nodes, refs = [], []

    def emit(index, members):
        lo = boxes[members, 0].min(0); hi = boxes[members, 1].max(0); first = len(refs)
        if len(members) <= LEAF:
            refs.extend(int(ids[m]) for m in members)
            nodes[index] = struct.pack(NODE, *lo, 0, len(members), len(members), *hi, 0, first)
            return
        centre = boxes[members].mean(1); axis = int(np.ptp(centre, 0).argmax())
        members = members[np.argsort(centre[:, axis], kind='stable')]; mid = len(members)//2
        left = len(nodes); nodes.extend([None, None])
        nodes[index] = struct.pack(NODE, *lo, 2, 0, len(members), *hi, left, first)
        emit(left, members[:mid]); emit(left+1, members[mid:])
    nodes.append(None); emit(0, np.arange(len(ids)))
    return nodes, refs


def add(ident, package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('CSM props already added: '+str(package/REPORT))
    l = read_lumps(bsp, (5, 0x63, 0x64, 0x7b))
    envs = [list(struct.unpack_from(ENV, l[5], i)) for i in range(0, len(l[5]), 36)]
    if l[0x64] or any(e[3]-e[0] != 1 for e in envs) or len(l[0x63]) != 32*len(envs):
        raise ValueError('Expected the empty per-environment CSM roots the world builds write')
    R = light_basis(envs[0][6:]); info = struct.unpack('<4I3f', l[0x7b][:28]); base = (info[2]+63) & ~63
    boxes, ids, skipped = [], [], dict(small=0, ground_cover=0, unknown=0)
    for k, p in enumerate(placements(ident, bsp)):
        src = p['source']; stem = Path(src['model']).stem.lower() if src else None
        if not src or stem not in asset_index(ident):
            skipped['unknown'] += 1; continue
        if NO_SHADOW.search(stem):
            skipped['ground_cover'] += 1; continue
        t, _ = model_triangles(ident, stem)
        if not len(t) or np.linalg.norm(t.reshape(-1, 3), axis=1).max()*p['scale'] < MIN_RADIUS:
            skipped['small'] += 1; continue
        world = t.reshape(-1, 3) @ np.asarray(rotation(p['angles'])).T * p['scale'] + p['origin']
        light = world @ R.T; boxes.append((light.min(0)-1, light.max(0)+1)); ids.append(base+k)
    if base+len(placements(ident, bsp)) > 65535:
        raise ValueError('Object ids exceed uint16')
    nodes, refs = tree(np.asarray(boxes), np.asarray(ids))
    # Environment 0 (the gameplay sun) gets the tree; the others keep their empty root after it.
    empty = [l[0x63][32*i:32*i+32] for i in range(1, len(envs))]
    envs[0][0], envs[0][1], envs[0][3], envs[0][4] = 0, 0, len(nodes), len(refs)
    for i, e in enumerate(envs[1:]):
        e[0], e[1], e[3], e[4] = len(nodes)+i, len(refs), len(nodes)+i+1, len(refs)
    changes = {0x63: b''.join(nodes+empty), 0x64: struct.pack(f'<{len(refs)}H', *refs),
               5: b''.join(struct.pack(ENV, *e) for e in envs)}
    temp = bsp.with_suffix('.csm.bsp'); compact(bsp, temp, changes); os.replace(temp, bsp)
    report = dict(casters=len(refs), nodes=len(nodes), leaf=LEAF, min_radius=MIN_RADIUS, skipped=skipped,
                  sun=envs[0][6:], prop_object_base=base)
    (package/REPORT).write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    add(sys.argv[1], sys.argv[2])
