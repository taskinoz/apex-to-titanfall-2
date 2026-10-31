"""Give small non-foliage static props a fade distance, so clutter across the arena is not drawn.

The 64-byte sprp v13 placement stores a fade distance at offset 36 (-1 = the model's own; bsp_tool's
`forced_fade_scale`). It is a distance in units: with 600 on every placement, everything beyond 600 units vanished
in game (30 October 2026). Retail sets it on small props as well as grass (Homestead's small granite rocks, Colony's
floor panels and beams, 1,000-6,000). build_native_props.py only fades foliage; this fades the placements with no
fade and a world-space radius (first LOD with <= build_visibility_cells.PROP_TRIANGLES triangles, times scale) of at
most MAX_RADIUS at FADE_PER_RADIUS x radius (about 12 pixels across at 1280x720 and 90 degrees), and at least
MIN_FADE. The game lump is patched in place.

  python fade_small_props.py thunderdome <package>
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
from build_visibility_cells import placements, model_triangles
from build_native_props import asset_index
from prepare_new_arena_scene import foliage

MAX_RADIUS = 80.
FADE_PER_RADIUS = 100.
MIN_FADE = 1500.
REPORT = 'small-prop-fades.json'


def records(data):
    """Absolute offsets of the sprp placements in a BSP's bytes."""
    lump, _ = struct.unpack_from('<2I', data, 16+0x23*16); count = struct.unpack_from('<I', data, lump)[0]
    entry = next(e for e in (struct.unpack_from('<4sHHII', data, lump+4+16*i) for i in range(count)) if e[0] == b'prps')
    if entry[2] != 13:
        raise ValueError('Expected sprp v13')
    at = entry[3]; models = struct.unpack_from('<I', data, at)[0]; at += 4+models*128
    n = struct.unpack_from('<I', data, at)[0]
    return [at+12+64*i for i in range(n)]


def fade(ident, package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('Fades already applied: '+str(package/REPORT))
    data = bytearray(bsp.read_bytes()); offsets = records(data); props = placements(ident, bsp)
    if len(offsets) != len(props):
        raise ValueError('Placement count differs')
    faded, distances = 0, []
    for at, p in zip(offsets, props):
        src = p['source']
        if struct.unpack_from('<f', data, at+36)[0] >= 0 or not src or foliage(src['model']):
            continue
        stem = Path(src['model']).stem.lower()
        if stem not in asset_index(ident):
            continue
        t, _ = model_triangles(ident, stem)
        radius = float(np.linalg.norm(t.reshape(-1, 3), axis=1).max())*p['scale'] if len(t) else 0.
        if 0 < radius <= MAX_RADIUS:
            d = max(MIN_FADE, FADE_PER_RADIUS*radius); struct.pack_into('<f', data, at+36, d); faded += 1; distances.append(d)
    temp = bsp.with_suffix('.fade.bsp'); temp.write_bytes(data); temp.replace(bsp)
    report = dict(placements=len(props), faded=faded, max_radius=MAX_RADIUS, fade_per_radius=FADE_PER_RADIUS, min_fade=MIN_FADE,
                  fade_percentiles=np.percentile(distances, [5, 50, 95]).round().tolist() if distances else [])
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    fade(sys.argv[1], sys.argv[2])
