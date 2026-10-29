"""Rescale world-material UVs whose density is far outside a texture's working range.

Current Apex terrain materials scale their UVs in the (reflection-stripped) shader, so the exported mesh UVs are
not what the game draws. In Thunderdome 0.2.0:
* `td2_manicured_grass_green_01_to_homestead_dirt_01` and `homestead_dirt_01_blend2trans` carry world-unit UVs
  (one repeat per unit, +-5,000): the native shader samples their smallest mip, so grass reads as flat green;
* `sand_desert_02_dirt_desert_05_bm_wld` and `homestead_dirt_01_to_dirt_desert_05_eld` stretch one repeat over
  6,600-8,700 units, so the dirt is blurry.

Each world material's median UV density (sqrt of UV area / world area, over its BSP triangles) is measured. A
terrain material (name containing a TERRAIN word) with fewer than MIN_UNITS or more than MAX_UNITS world units per
repeat has its UVs multiplied about the origin to TILE units per repeat. Other materials are left alone: atlases
(stadium crowd, trim sheets, vehicles) and the sky legitimately span thousands of units per repeat. Lightmap UVs, the vertex alpha blend and lighting are untouched. The BSP is read
from one package and written to another, with the applied factors recorded beside it (and refused if present):

  python rescale_world_uvs.py <source package> <output package>
"""
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from fix_overflow_overlays import native_names
from build_composite_map import DT

TILE = 256.0          # world units per texture repeat after rescaling
MIN_UNITS, MAX_UNITS = 8.0, 2048.0
TERRAIN = ('dirt', 'mud', 'sand', 'grass', 'rubble')
REPORT = 'uv-rescale.json'


def densities(l):
    """Per world material: its BSP vertex indices and median world units per UV repeat."""
    names = native_names(l); sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    rec = np.frombuffer(l[0x49], DT); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3)
    tris, verts = {}, {}
    for m in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        if not m[-1] & 0x200:  # lit-bump vertices (0x49) only
            continue
        srt = sorts[m[-2]]; name = names[srt[0]]
        ix = np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('i8')+srt[-1]
        tris.setdefault(name, []).append(ix.reshape(-1, 3)); verts.setdefault(name, set()).update(ix.tolist())
    out = {}
    for name, t in tris.items():
        t = np.concatenate(t); p = pos[rec['pi'][t]].astype('f8'); uv = rec['uv'][t].astype('f8')
        world = np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1)
        e1, e2 = uv[:, 1]-uv[:, 0], uv[:, 2]-uv[:, 0]; area = np.abs(e1[:, 0]*e2[:, 1]-e1[:, 1]*e2[:, 0])
        ok = (world > 1) & (area > 0)
        if ok.any():
            out[name] = (np.array(sorted(verts[name])), float(1/np.median(np.sqrt(area[ok]/world[ok]))))
    return out


def link(a, b):
    try:
        os.link(a, b)
    except OSError:
        shutil.copy2(a, b)


def rescale(source, target):
    source, target = Path(source), Path(target)
    if (target/REPORT).exists():
        raise ValueError('UVs already rescaled in '+str(target))
    if not target.exists():  # link (or, across drives, copy) everything except the BSP, which is rewritten
        shutil.copytree(source, target, copy_function=lambda a, b: None if a.endswith('.bsp') else link(a, b))
    bsp = next((source/'mod/maps').glob('*.bsp')); l = read_lumps(bsp, tuple(range(128)))
    rec = np.frombuffer(l[0x49], DT).copy(); changed = {}; measured = densities(l)
    selected = {name for name, (ix, units) in measured.items()
                if any(w in name for w in TERRAIN) and not MIN_UNITS <= units <= MAX_UNITS}
    kept = set().union(*(set(ix.tolist()) for name, (ix, units) in measured.items() if name not in selected))
    for name, (ix, units) in sorted(measured.items()):
        if name not in selected:
            continue
        if kept.intersection(ix.tolist()):
            raise ValueError(f'{name} shares vertices with a material that is not rescaled')
        k = units/TILE; rec['uv'][ix] *= k
        changed[name] = dict(units_per_repeat=round(units, 3), factor=k, vertices=len(ix))
    if not changed:
        raise ValueError('No terrain material outside the UV density range')
    out = target/'mod/maps'/bsp.name
    if out.exists():
        out.unlink()  # a hard link to the source would otherwise be rewritten in place
    compact(bsp, out, {0x49: rec.tobytes()})
    report = dict(source=str(bsp), tile=TILE, range=[MIN_UNITS, MAX_UNITS], materials=changed)
    (target/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    rescale(sys.argv[1], sys.argv[2])
