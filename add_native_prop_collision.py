"""Give the native static props (build_native_props.py) collision as world triangle collision.

A static prop's kind 0x60 grid primitive makes the engine trace the model's physics (map-collision block), and
the per-triangle tree alone does not collide: a player dropped on a native Thunderdome rock fell straight through it
with or without the primitive (29 October 2026). Apex's collision for these models is concave triangle soup
(RSX `.stl`, 12.7M triangles for Thunderdome's solid props: twice the 65,535 triangle-header limit), and there is
no convex decomposition here, so the drawn geometry at a collision LOD (the first LOD with at most COLLISION_TRIANGLES
triangles, as match_collision_to_render.py's drawn-triangle collision) is appended as native triangle collision.
That follows recover_composite_details.append_collision: groups of 96 encoded by native_triangle_collision.encode,
relocated after the existing buffers, then the grid rebuilt over the previously active primitives plus the new
headers (disabled source colliders stay disabled).

Solid means source solid mode 1, 2, 6 or 7 and not foliage (grass, flowers, trees: Apex players walk through them);
the treehouse building is solid despite its name. Props under MIN_RADIUS are skipped, and the LOD cap keeps the
appended headers inside the free uint16 index space (30,600 headers are stored, 11,943 of them active).

  python add_native_prop_collision.py thunderdome <package built by build_native_props.py>
"""
import functools
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from read_vg_static import load, levels
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from stage_prop_geometry import rotation
from native_triangle_collision import encode
from extend_prop_collision import pack_grid
from build_center_detail import active
from build_native_props import selection, asset_index, SKIP
from prepare_new_arena_scene import foliage

COLLISION_TRIANGLES = 1200
MIN_RADIUS = 24.0   # pebbles and small debris do not block a player
GROUP = 96
HEADER_LIMIT = 65535
REPORT = 'native-prop-collision.json'
COLLISION_LUMPS = (3, 0x42, 0x44, 0x45, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b, 0x5c, 0x60, 0x61)


def solid(p):
    return p['solid'] in (1, 2, 6, 7) and (not foliage(p['model']) or 'building' in p['model'])


@functools.lru_cache(None)
def collision_lod(ident, model):
    path = asset_index(ident)[model]
    for lod in range(levels(path)):
        sections, slots, skins = load(path, lod, with_colors=True)
        keep = [np.asarray(s, 'f4').reshape(-1, 3, 12)[:, :, :3] for s, k in zip(sections, slots)
                if len(s) and not any(x in skins[0][k].lower() for x in SKIP)]
        tris = np.concatenate(keep).astype('f8') if keep else np.empty((0, 3, 3))
        if len(tris) <= COLLISION_TRIANGLES or lod == levels(path)-1:
            return tris


def triangles(ident):
    out = []
    for p in selection(ident, True):
        if solid(p) and Path(p['model']).stem.lower() in asset_index(ident):
            t = collision_lod(ident, Path(p['model']).stem.lower())
            if len(t) and np.linalg.norm(t.reshape(-1, 3), axis=1).max()*p['scale'] >= MIN_RADIUS:
                out.append(t @ np.asarray(rotation(p['angles'])).T * p['scale'] + p['origin'])
    col = np.concatenate(out)
    good = np.linalg.norm(np.cross(col[:, 1]-col[:, 0], col[:, 2]-col[:, 0]), axis=1) > 1e-5
    col = col[good]; centres = col.mean(1)
    return col[np.lexsort((centres[:, 2], centres[:, 1], centres[:, 0]))].astype('<f4')


def add(ident, package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('Collision already added: '+str(package/REPORT))
    l = read_lumps(bsp, COLLISION_LUMPS); buf = {k: bytearray(v) for k, v in l.items()}
    previously = active(l); first_new = len(buf[0x45])//44
    col = triangles(ident)
    encoded, _ = encode([col[i:i+GROUP] for i in range(0, len(col), GROUP)])
    if first_new + len(encoded[0x45])//44 > HEADER_LIMIT:
        raise ValueError('Triangle collision headers exceed the uint16 primitive index')
    vertexbase, wordbase, nodebase = len(buf[3])//12, len(buf[0x42])//4, len(buf[0x44])//16
    for at in range(0, len(encoded[0x45]), 44):  # relocate the header's vertex, triangle and node streams
        header = list(struct.unpack_from('<6h4i4f', encoded[0x45], at))
        header[6] += vertexbase; header[7] += wordbase; header[8] += nodebase
        buf[0x45].extend(struct.pack('<6h4i4f', *header))
    for key in (3, 0x42, 0x44, 0x60):
        buf[key].extend(encoded[key])
    # Grid over the previously active brushes and headers plus every new header.
    positions = np.frombuffer(buf[3], '<f4').reshape(-1, 3); words = np.frombuffer(buf[0x42], '<u4'); bounds = []
    for h in struct.iter_unpack('<6h4i4f', buf[0x45]):
        w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        faces = positions[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)]
        bounds.append((faces.min((0, 1)).tolist(), faces.max((0, 1)).tolist()))
    brush = [([r[i]-r[i+6] for i in range(3)], [r[i]+r[i+6] for i in range(3)]) for r in struct.iter_unpack('<3f2BH3fI', buf[0x5c])]
    keep_b = [i for i in range(len(brush)) if (0, i) in previously]
    keep_t = [i for i in range(len(bounds)) if (0x40, i) in previously or i >= first_new]
    g = pack_grid([brush[i] for i in keep_b]+[bounds[i] for i in keep_t]); off = len(keep_b)
    prims, sets = bytearray(g[0x59]), bytearray(g[0x57])

    def remap(word):
        k = (word >> 8) & 65535
        return (keep_b[k] << 8) | (word & 255) if k < off else (0x40 << 24) | (keep_t[k-off] << 8) | (word & 255)
    for at in range(0, len(prims), 4):
        struct.pack_into('<I', prims, at, remap(struct.unpack_from('<I', prims, at)[0]))
    for at in range(0, len(sets), 8):
        if struct.unpack_from('<H', sets, at+2)[0] == 1:
            struct.pack_into('<I', sets, at+4, remap(struct.unpack_from('<I', sets, at+4)[0]))
    changes = {k: bytes(buf[k]) for k in (3, 0x42, 0x44, 0x45, 0x60)}
    changes.update({0x56: g[0x56], 0x57: bytes(sets), 0x58: g[0x58], 0x59: bytes(prims), 0x5a: g[0x5a]})
    temp = bsp.with_suffix('.collision.bsp'); compact(bsp, temp, changes); os.replace(temp, bsp)
    report = dict(solid_placements=sum(1 for p in selection(ident, True) if solid(p)), triangles=len(col),
                  new_headers=len(encoded[0x45])//44, headers=len(buf[0x45])//44, header_limit=HEADER_LIMIT,
                  previously_active_brushes=len(keep_b), collision_lod_triangles=COLLISION_TRIANGLES, min_radius=MIN_RADIUS)
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    add(sys.argv[1], sys.argv[2])
