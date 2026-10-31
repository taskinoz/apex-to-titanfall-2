"""Smoke test: native Titanfall 2 static props in a converted arena (docs/candidates/static-prop-conversion-2026-10-24.md).

Places stock models that live in englishclient_mp_common (always mounted, so no model shipping) as `sprp` v13
placements in a copy of a staged package, to establish what the BSP side needs before converting Apex models:

* GAME_LUMP `prps` v13: model names (128 bytes), counts (n, n, n), 64-byte placements copied from a retail
  placement of the same model (Homestead / Live Fire Deck), with origin and yaw replaced and cubemap 0xffff
  (the converted maps have no cubemaps);
* object references: props start at align64(LEVEL_INFO[2]) (engine.dll 0xcb2c4..0xcb2e6: +63, & ~63; Glitch
  2903 -> 2944, Live Fire Stacks 1763 -> 1792), in the same conservative camera-domain cell tree the conversions
  already use;
* LEVEL_INFO (0x7b) field 3 = placement count; 0x66 is LUMP_STATIC_PROP_LIGHTPROBE_INDEX (engine string): one
  uint32 light probe per placement (a permutation of 0..n-1 in retail, as each prop gets its own probe).

Result 2026-10-24: engine.dll parses the lump (an oversized count raises "Too many static props in map (map has
60000, limit is 57343)"), but the props were not drawn: that run used align16 (2864, not the engine's 2880).
Re-run 2026-10-29 with align64: all three props draw. Each placement also needs a kind 0x60 primitive in the
collision grid (collision()) to be solid; with it, the Apex crate from build_apex_static_prop.py (in APEX) and the
stock props all stop a falling player. See docs/candidates/static-prop-conversion-2026-10-24.md.

The new game lump is appended at the end of the BSP with its absolute payload offset; the old one is left unused.

  python add_stock_props.py thermal-station
"""
import json
import math
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, folder
from compact_preview_bsp import compact
from repair_preview_index_padding import read_lumps
from repair_camera_visibility import CAMERA_MIN, CAMERA_MAX

ROOT = Path(__file__).resolve().parent
# Retail placements (hex of the 64-byte v13 record) of mp_common models, from Homestead and Live Fire Deck.
TEMPLATES = {
    'models/containers/plastic_pallet_01.mdl': 'mp_homestead',
    'models/containers/pelican_case_large.mdl': 'mp_homestead',
    'models/barriers/sandbags_curved_01.mdl': 'mp_lf_deck',
}
# Compiled Apex models (build_apex_static_prop.py), placed with a stock model's retail record as the template.
APEX = {'models/apex/farmland_crate_md_80x64x72_03.mdl': 'models/containers/pelican_case_large.mdl'}
RETAIL = {'mp_homestead': ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',
          'mp_lf_deck': ROOT/'inputs/titanfall2-livefire-deck/maps/mp_lf_deck.bsp'}
# Ground in front of the user-report r2 camera (thermal-station-user-report.json) plus a row either side.
SPOT = dict(origin=(-2705.62, -70.13, -21.16), angles=(38.45, 154.5))
SPACING = 160.
PROP_EXTENT = 160  # collision broad-phase half size around each placement (larger than any test model)
LEAF = 255


def sprp(path):
    g = read_lumps(path, (0x23,))[0x23]; lo = struct.unpack_from('<4I', Path(path).read_bytes()[:2064], 16+0x23*16)[0]
    _, _, ver, off, ln = struct.unpack_from('<4sHHII', g, 4); p = g[off-lo:off-lo+ln]
    if ver != 13:
        raise ValueError('Expected sprp v13')
    mc = struct.unpack_from('<I', p)[0]; names = [p[4+i*128:4+(i+1)*128].split(b'\0')[0].decode().lower() for i in range(mc)]
    o = 4+mc*128; n = struct.unpack_from('<I', p, o)[0]; o += 12
    return names, [p[o+64*i:o+64*(i+1)] for i in range(n)]


def template(model):
    model = APEX.get(model, model); names, recs = sprp(RETAIL[TEMPLATES[model]])
    return next(r for r in recs if names[struct.unpack_from('<H', r, 28)[0]] == model)


def ground_points(out, count):
    """Where the r2 camera looks, then a row SPACING apart across it, each dropped onto the converted scene."""
    z = np.load(out/'scene.npz'); T = z['triangles'][:, :, :3].astype('f8')
    def ray(o, d):
        e1 = T[:, 1]-T[:, 0]; e2 = T[:, 2]-T[:, 0]; h = np.cross(d, e2); a = (e1*h).sum(1); ok = np.abs(a) > 1e-9
        f = np.where(ok, 1/np.where(ok, a, 1), 0); s = o-T[:, 0]; u = f*(s*h).sum(1); q = np.cross(s, e1)
        v = f*(q@d); t = f*(e2*q).sum(1); hit = ok & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > 1)
        return o+d*t[hit].min()
    p, y = map(math.radians, SPOT['angles'])
    look = np.array([math.cos(p)*math.cos(y), math.cos(p)*math.sin(y), -math.sin(p)])
    centre = ray(np.asarray(SPOT['origin']), look); side = np.array([-math.sin(y), math.cos(y), 0.])
    return [ray(centre+side*(k-1)*SPACING+[0, 0, 400], np.array([0, 0, -1.])) for k in range(count)], float(SPOT['angles'][1])


def visibility(bounds_51, meshes, props, base):
    """Flat conservative tree (as repair_camera_visibility): every box spans the camera domain."""
    refs, boxes = [], []
    for i, m in enumerate(struct.iter_unpack('<8f', bounds_51[:meshes*32])):
        refs.append(i); boxes.append((m[:3], m[4:7], True))
    for k, o in enumerate(props):
        refs.append(base+k); boxes.append((o, (256., 256., 256.), True))
    wide = [(tuple(min(CAMERA_MIN[j], c[j]-e[j]-1) for j in range(3)), tuple(max(CAMERA_MAX[j], c[j]+e[j]+1) for j in range(3)))
            for c, e, _ in boxes]
    if math.ceil(len(wide)/LEAF) > 255 or max(refs) > 65535:
        raise ValueError('Object references exceed native uint16/byte counts')
    lo = tuple(min(b[0][j] for b in wide) for j in range(3)); hi = tuple(max(b[1][j] for b in wide) for j in range(3))
    nodes = [struct.pack('<3f2BH3f2H', *lo, math.ceil(len(wide)/LEAF), 0, len(wide), *hi, 1, 0)]
    for first in range(0, len(wide), LEAF):
        batch = wide[first:first+LEAF]
        blo = tuple(min(b[0][j] for b in batch) for j in range(3)); bhi = tuple(max(b[1][j] for b in batch) for j in range(3))
        nodes.append(struct.pack('<3f2BH3f2H', *blo, 0, len(batch), len(batch), *bhi, 0, first))
    return (b''.join(nodes), struct.pack(f'<{len(refs)}H', *refs),
            b''.join(struct.pack('<3fI3fI', *l, 0, *h, 0) for l, h in wide))


def game_lump(models, placements):
    names = b''.join(m.encode().ljust(128, b'\0') for m in models)
    n = len(placements)
    return struct.pack('<I', len(models))+names+struct.pack('<3I', n, n, n)+b''.join(placements)+struct.pack('<I', 0)


def collision(l, origins, extents=None):
    """Retail maps reference each solid static prop from the collision grid as a primitive of kind 0x60 (index =
    placement, low byte = contents; Homestead has 5,659, Live Fire Deck 2,052); the engine then traces the model's
    own collision. Without one a prop is drawn but not solid. Append a single-primitive geoset per placement to every
    2x2 grid cell (pack_grid's layout) its box touches (half size extents[k], default PROP_EXTENT; None = not
    solid); existing sets are kept in order."""
    extents = [PROP_EXTENT]*len(origins) if extents is None else extents
    if struct.unpack('<7i', l[0x55])[1:5] != (-1, -1, 2, 2):
        raise ValueError('Expected the conversions\' 2x2 collision grid')
    contents = struct.unpack(f'<{len(l[0x5b])//4}I', l[0x5b]).index(1)  # CONTENTS_SOLID
    cells = list(struct.iter_unpack('<HH', l[0x56]))[:4]; sets, bounds = bytearray(), bytearray(); index = bytearray()
    for c, (first, count) in enumerate(cells):
        start = len(sets)//8
        sets.extend(l[0x57][first*8:(first+count)*8]); bounds.extend(l[0x58][first*16:(first+count)*16])
        for k, (o, e) in enumerate(zip(origins, extents)):
            if e is None:
                continue
            e = int(min(32000, -(-e//1))); lo, hi = [v-e for v in o], [v+e for v in o]
            if hi[0] >= (c % 2-1)*32768 and lo[0] <= c % 2*32768 and hi[1] >= (c//2-1)*32768 and lo[1] <= c//2*32768:
                sets.extend(struct.pack('<HHI', 0, 1, (0x60 << 24) | (k << 8) | contents))
                bounds.extend(struct.pack('<3hH3hH', *map(round, o), 0x8000, e, e, e, 0))
        index.extend(struct.pack('<HH', start, len(sets)//8-start))
    if len(sets)//8 > 65535:
        raise ValueError('Grid reference overflow')
    index.extend(struct.pack('<HH', len(sets)//8, 0))
    return {0x56: bytes(index), 0x57: bytes(sets), 0x58: bytes(bounds)}


def apply(bsp, models, placements, solid=True, probes=None, extents=None):
    """solid: add kind 0x60 grid primitives (extents: per-placement half size, None = not solid); probes: 0x66
    light probe per placement (default 0..n-1)."""
    l = read_lumps(bsp, (0x50, 0x51, 0x55, 0x56, 0x57, 0x58, 0x5b, 0x7b)); meshes = len(l[0x50])//28
    info = list(struct.unpack('<4I3f', l[0x7b])); base = (info[2]+63) & ~63
    origins = [struct.unpack_from('<3f', p) for p in placements]
    nodes, refs, objects = visibility(l[0x51], info[2], origins, base)
    info[3] = len(placements)
    temp = bsp.with_suffix('.props.bsp')
    compact(bsp, temp, {0x77: nodes, 0x78: refs, 0x79: objects, 0x7b: struct.pack('<4I3f', *info),
                        0x66: struct.pack(f'<{len(placements)}I', *(range(len(placements)) if probes is None else probes)),
                        **(collision(l, origins, extents) if solid else {})})
    payload = game_lump(models, placements)
    with temp.open('r+b') as f:
        f.seek(0, 2); f.write(bytes((-f.tell()) % 16)); at = f.tell()
        lump = struct.pack('<I4sHHII', 1, b'prps', 0, 13, at+20, len(payload))+payload
        f.write(lump); f.seek(16+0x23*16); old = struct.unpack('<4I', f.read(16))
        f.seek(16+0x23*16); f.write(struct.pack('<4I', at, len(lump), old[2], old[3]))
    temp.replace(bsp)
    return dict(meshes=meshes, level_info_meshes=info[2], prop_object_base=base, placements=len(placements),
                references=len(refs)//2)


def run(ident):
    c = CONFIG[ident]; out = folder(ident)
    src = out.parent/'candidates'/c['package']; dst = out.parent/'candidates'/(c['package']+'-proptest')
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=lambda a, b: shutil.copy2(a, b) if a.endswith(('.bsp', '.json')) else __import__('os').link(a, b))
    models = list(TEMPLATES)+list(APEX); points, yaw = ground_points(out, len(models)); placements = []
    for model in APEX:  # the loose .mdl, and the materials RPak loaded after the map's own
        built = out/'apex-props'/Path(model).stem; target = dst/'mod'/model
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(built/model, target)
        shutil.copy2(built/'build'/(ident.replace('-', '_')+'_props.rpak'), dst/'paks')
        manifest = json.loads((dst/'paks/rpak.json').read_text())
        manifest['Postload'][ident.replace('-', '_')+'_props.rpak'] = 'mp_coliseum.rpak'
        (dst/'paks/rpak.json').write_text(json.dumps(manifest, indent=2))
    for k, (model, p) in enumerate(zip(models, points)):
        r = bytearray(template(model))
        struct.pack_into('<3f', r, 0, *p); struct.pack_into('<f', r, 16, yaw)  # angles stored y, z, x: index 1 = yaw
        struct.pack_into('<H', r, 28, k); struct.pack_into('<H', r, 34, 0xffff)
        placements.append(bytes(r))
    bsp = dst/'mod/maps'/(c['target']+'.bsp')
    report = dict(apply(bsp, models, placements), models=models, origins=[list(map(float, p)) for p in points])
    (dst/'stock-props.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run(sys.argv[1])
