"""Lift baked-world overlay layers off the surface they cover, so they stop z-fighting.

Apex draws `*_blend2trans`, `*_blend_2_trans`, `*_transparent` and decal layers over a coplanar surface, faded by
vertex alpha. The port bakes them as opaque world meshes at the same depth as that surface, and the scene build
stored vertex alpha as 255, so the fade cannot be recovered here. Each overlay vertex instead gets its own new
position (appended to lump 3, so the shared position under the base surface does not move) OFFSET units along
its normal. Lightmaps, collision (which reads lump 3 by absolute index) and other materials are untouched.

  python separate_world_overlays.py <package>
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from fix_overflow_overlays import native_names
from build_composite_map import DT
from build_native_props import OVERLAY

OFFSET = 0.4
REPORT = 'world-overlays.json'


def separate(package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('Overlays already separated: '+str(package/REPORT))
    l = read_lumps(bsp, (2, 3, 0x1e, 0x2b, 0x2c, 0x49, 0x4f, 0x50, 0x52))
    names = native_names(l); sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    rec = np.frombuffer(l[0x49], DT).copy(); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3)
    normals = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3)
    chosen, materials = set(), {}
    for m in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        if not m[-1] & 0x200:  # lit-bump vertices (0x49)
            continue
        srt = sorts[m[-2]]; name = names[srt[0]]
        if OVERLAY.search(name.lower()):
            ix = np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('i8')+srt[-1]
            chosen.update(ix.tolist()); materials[name] = materials.get(name, 0)+len(ix)//3
    # The overlay vertices must not be shared with any other material's mesh.
    others = set()
    for m in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        srt = sorts[m[-2]]
        if m[-1] & 0x200 and not OVERLAY.search(names[srt[0]].lower()):
            others.update((np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('i8')+srt[-1]).tolist())
    if chosen & others:
        raise ValueError('Overlay vertices are shared with other materials')
    ix = np.array(sorted(chosen)); lifted = pos[rec['pi'][ix]].astype('f8')+normals[rec['ni'][ix]]*OFFSET
    rec['pi'][ix] = len(pos)+np.arange(len(ix))
    temp = bsp.with_suffix('.overlays.bsp')
    compact(bsp, temp, {3: l[3]+lifted.astype('<f4').tobytes(), 0x49: rec.tobytes()}); os.replace(temp, bsp)
    report = dict(offset=OFFSET, vertices=len(ix), materials=materials)
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    separate(sys.argv[1])
