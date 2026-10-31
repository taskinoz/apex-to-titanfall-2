"""Re-bake world lighting with the native static props (build_native_props.py) as shadow casters.

The world lightmaps were baked when the omitted props were not drawn, so they carry no shadow from them. This
re-runs the port's own bakes (light_new_arena_ports.py) with the props appended to the bake input as caster-only
triangles: a job with zero UVs is skipped by the rasterisers of bake_arena_environment.exe and
bake_interior_lighting.exe, so the triangle occludes without receiving a lightmap.

The installed lightmaps also carry post-bake edits (material glow charts, atmosphere passes), so they are not
rebuilt from scratch. The old bake outputs (sun.bin, local.bin, probes.bin in the work folder) are compared with the
new ones, and only the 4x4 lightmap tiles whose sun, sky or local-light visibility changed are updated:
* RTL (0x69): sun visibility (channel 0) and local-light visibility (1-3, where the light ids are unchanged);
* sky (0x62): the ambient term gains the bake formula's change (base x .35 x sky visibility, plus fill), decoded
  and re-encoded from the current RGBM, and the bent normal is replaced;
* character probes (0x65): replaced, once the old probe bake is shown to reproduce the current lump exactly;
  the props' 0x66 probe indices are then re-picked (build_native_props.nearest_probes).
Grass and other foliage do not cast (retail grass has the no-shadow flag).

  python rebake_native_prop_shadows.py thunderdome <package built by build_native_props.py>
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import WORK, folder
from light_new_arena_ports import run_logged, LOCAL
from read_vg_static import load, levels
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from stage_prop_geometry import rotation
from apply_baked_lighting import encode_rgbm
from recover_composite_details import JOB
from build_native_props import selection, asset_index, nearest_probes, SKIP
import build_native_props

ROOT = Path(__file__).resolve().parent
SHADOW_TRIANGLES = 1500   # first LOD at or under this many triangles casts (else the last LOD)
REPORT = 'native-prop-shadows.json'


def caster_triangles(ident):
    """World-space triangles of every non-foliage native prop, at a shadow LOD."""
    out, cache = [], {}
    for p in selection(ident, False):
        model = Path(p['model']).stem.lower()
        if model not in asset_index(ident):
            continue
        path = asset_index(ident)[model]
        if model not in cache:
            for lod in range(levels(path)):
                sections, slots, skins = load(path, lod, with_colors=True)
                keep = [np.asarray(s, 'f4').reshape(-1, 3, 12)[:, :, :3] for s, k in zip(sections, slots)
                        if len(s) and not any(x in skins[0][k].lower() for x in SKIP)]
                tris = np.concatenate(keep) if keep else np.empty((0, 3, 3), 'f4')
                if len(tris) <= SHADOW_TRIANGLES or lod == levels(path)-1:
                    break
            cache[model] = tris
        if len(cache[model]):
            m = np.asarray(rotation(p['angles']), 'f8')
            out.append((cache[model].astype('f8') @ m.T * p['scale'] + p['origin']).astype('<f4'))
    return np.concatenate(out)


def fill(values, valid):
    """light_new_arena_ports.build's rule: an invalid texel takes the nearest valid one in its own 4x4 chart."""
    values = values.copy(); ys, xs = np.nonzero(valid)
    if len(ys):
        for yy, xx in zip(*np.nonzero(~valid)):
            k = int(((ys-yy)**2+(xs-xx)**2).argmin()); values[yy, xx] = values[ys[k], xs[k]]
    return values


def decode_rgbm(c):
    c = c.astype('f8')/255
    return c[..., :3]*(c[..., 3:]*3.984375+.015625)


def probe_lump(values):
    values = values.copy(); values[:, :12] *= np.asarray([.055/.025]*4+[.065/.027]*4+[.085/.032]*4)
    return b''.join(struct.pack('<16h4B4hI', *np.rint(np.clip(row[:16]*8192, -32768, 32767)).astype(int),
                                *row[16:20].astype(int), *row[20:24].astype(int), 0) for row in values)


def rebake(ident, package):
    out = folder(ident); package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('Already re-baked: '+str(package/REPORT))
    work = out/'native-prop-bake'; work.mkdir(exist_ok=True)
    cfg = json.loads((out/'bake.json').read_text()); w, h, pages = cfg['width'], cfg['height'], cfg['pages']
    direction = -np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
    # Bake inputs: the world's triangles and jobs, then the props as caster-only triangles.
    props = caster_triangles(ident); print('Prop caster triangles', len(props), flush=True)
    tri = np.fromfile(out/'bake-triangles.bin', '<f4').reshape(-1, 3, 3); jobs = np.fromfile(out/'bake-jobs.bin', JOB)
    cast = np.fromfile(out/'bake-casters.bin', 'u1')
    extra = np.zeros(len(props), JOB); extra['p'] = props
    np.concatenate((tri, props)).tofile(work/'bake-triangles.bin'); np.concatenate((jobs, extra)).tofile(work/'bake-jobs.bin')
    np.concatenate((cast, np.ones(len(props), 'u1'))).tofile(work/'bake-casters.bin')
    run_logged(WORK/'tools/bake_arena_environment.exe', [work/'bake-triangles.bin', work/'bake-jobs.bin', work/'sun.bin', w, h, pages,
               work/'bake-casters.bin', *direction], work/'sun-bake.log')
    run_logged(ROOT/'tools/bake_interior_lighting.exe', [work/'bake-triangles.bin', work/'bake-jobs.bin', out/'fixtures.bin',
               work/'local.bin', w, h, pages, work/'bake-casters.bin'], work/'local-bake.log')
    np.concatenate((tri[cast.astype(bool)], props)).tofile(work/'probe-casters.bin')
    run_logged(WORK/'tools/bake_arena_character_probes.exe', [work/'probe-casters.bin', out/'probe-positions.bin', out/'fixtures.bin',
               work/'probes.bin', *direction], work/'probe-bake.log')

    shape = (pages, h, w)
    sun0 = np.memmap(out/'sun.bin', '<f4', 'r', shape=shape+(5,)); sun1 = np.memmap(work/'sun.bin', '<f4', 'r', shape=shape+(5,))
    valid = np.memmap(out/'sun.bin.mask', 'u1', 'r', shape=shape)
    loc0 = np.memmap(out/'local.bin', LOCAL, 'r', shape=shape); loc1 = np.memmap(work/'local.bin', LOCAL, 'r', shape=shape)
    l = read_lumps(bsp, (0x62, 0x65, 0x69))
    sky = np.frombuffer(l[0x62], 'u1').reshape(pages, 2, h, w, 4).copy(); rtl = bytearray(l[0x69])
    stride = w*h*8+(w//2)*(h//2)*4
    scene = json.loads((out/'scene.json').read_text()); first = 0; photo = None
    for name, count in scene['materials'].items():  # the sky dome's charts are photographic: never relit
        if name == 'sky':
            photo = (first, first+count)
        first += count
    base = np.asarray([.055, .065, .085]); stats = dict(tiles=0, texels=0, darker=0, lighter=0)
    for page in range(pages):
        a, b = np.asarray(sun0[page]), np.asarray(sun1[page]); m = np.asarray(valid[page]).astype(bool)
        la, lb = np.asarray(loc0[page]), np.asarray(loc1[page])
        changed = m & ((np.abs(a[..., 0]-b[..., 0]) > .5/255) | (np.abs(a[..., 1]-b[..., 1]) > .002) |
                       (np.abs(la['vis'].astype(int)-lb['vis'].astype(int)).max(-1) > 0))
        ids = np.ndarray((h, w), '<u4', buffer=rtl, offset=page*stride)
        vis = np.ndarray((h, w, 4), 'u1', buffer=rtl, offset=page*stride+w*h*4)
        for ty, tx in sorted({(y//4, x//4) for y, x in zip(*np.nonzero(changed))}):
            tile = page*(w//4)*(h//4)+ty*(w//4)+tx
            if photo and photo[0] <= tile < photo[1]:
                continue
            ys, xs = slice(ty*4, ty*4+4), slice(tx*4, tx*4+4); mm = m[ys, xs]
            oa, ob = fill(a[ys, xs], mm), fill(b[ys, xs], mm)
            fa, fb = fill(la[ys, xs]['fill'], mm), fill(lb[ys, xs]['fill'], mm)
            va, vb = fill(la[ys, xs]['vis'], mm), fill(lb[ys, xs]['vis'], mm)
            vis[ys, xs, 0] = np.rint(np.clip(ob[..., 0], 0, 1)*255).astype('u1')
            same = fill(la[ys, xs]['ids'], mm) == fill(lb[ys, xs]['ids'], mm)
            vis[ys, xs, 1:][same] = vb[..., 1:][same]
            ambient = decode_rgbm(sky[page, 0, ys, xs]) + base*.35*(np.maximum(ob[..., 1:2], 0)-np.maximum(oa[..., 1:2], 0)) + (fb-fa)
            sky[page, 0, ys, xs] = encode_rgbm(np.maximum(ambient, 0))
            sky[page, 1, ys, xs, :3] = np.rint(np.clip((ob[..., 2:5]+1)/2.007874, 0, 1)*255).astype('u1')
            d = ob[..., 0]-oa[..., 0]
            stats['tiles'] += 1; stats['texels'] += 16; stats['darker'] += int((d < -.5/255).sum()); stats['lighter'] += int((d > .5/255).sum())
        del ids
    positions = np.fromfile(out/'probe-positions.bin', '<f4').reshape(-1, 3)
    old = probe_lump(np.fromfile(out/'probes.bin', '<f4').reshape(len(positions), 24))
    if old != l[0x65]:
        raise ValueError('The work folder probe bake does not reproduce the installed 0x65; probes left unchanged')
    probes = probe_lump(np.fromfile(work/'probes.bin', '<f4').reshape(len(positions), 24))
    temp = bsp.with_suffix('.shadows.bsp')
    compact(bsp, temp, {0x62: sky.tobytes(), 0x69: bytes(rtl), 0x65: probes}); os.replace(temp, bsp)
    # Re-pick each prop's lit probe against the new probe values (positions are unchanged), at its lighting origin.
    names, recs = build_native_props.add_stock_props.sprp(bsp)
    points = np.array([struct.unpack_from('<3f', r, 40) for r in recs]); picks = nearest_probes(bsp, points)
    lump = read_lumps(bsp, (0x66,))[0x66]
    if len(lump) != 4*len(recs):
        raise ValueError('0x66 does not match the placements')
    temp = bsp.with_suffix('.probes.bsp'); compact(bsp, temp, {0x66: struct.pack(f'<{len(picks)}I', *picks)}); os.replace(temp, bsp)
    report = dict(caster_triangles=len(props), shadow_lod_triangles=SHADOW_TRIANGLES, **stats,
                  probes=len(positions), placements=len(recs), sun=direction.tolist())
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    rebake(sys.argv[1], sys.argv[2])
