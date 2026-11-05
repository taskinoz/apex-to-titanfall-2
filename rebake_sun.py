"""Re-bake a port's sun visibility for a new sun direction, from the installed BSP alone.

Drop-Off (build_composite_map.py) was lit with Phase Runner's sun: angles 38.4 142, normal
(-0.618, 0.482, -0.621), while Apex's mp_rr_arena_composite light_environment is 45.2714 -46.919, so its baked
shadows and the sun shading fall from nearly the opposite side. Titanfall shades the sun at run time from the sun
world light; the lightmaps only store its visibility (RTL B channel 0, docs/gravemind/lighting.md). Sky visibility,
bent normals and local lights do not depend on the sun, so only that channel and the sun records change.

The bake input is rebuilt from the BSP: every lit-bump mesh triangle receives at its vertex lightmap UV (0x49 light,
scaled by its page's size), and the opaque shadow meshes (0x7C-0x7F, the build's caster set: no sky, transparent or
foliage) occlude. Pages of different sizes are baked in separate runs of bake_arena_environment.exe.

  python rebake_sun.py check <package>            bake with the map's current sun; report agreement with its RTL
  python rebake_sun.py apply <package> <pitch> <yaw>
  python rebake_sun.py probes <package> <probe positions.bin> <fixtures.bin>   sun visibility of the character probes
"""
import json
import math
import os
import struct
import sys
from pathlib import Path

import numpy as np
from build_composite_map import DT
from recover_composite_details import JOB
from light_new_arena_ports import run_logged
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from new_arena_ports import WORK

ROOT = Path(__file__).resolve().parent
EXE = WORK/'tools/bake_arena_environment.exe'
REPORT = 'sun-rebake.json'


def bake_scene(l):
    """Receiver triangles (positions, normals, luxel UVs, page) and caster triangles."""
    sizes = [struct.unpack_from('<I2H', l[0x53], i)[1:] for i in range(0, len(l[0x53]), 8)]
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3); nrm = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3)
    rec = np.frombuffer(l[0x49], DT); sorts = list(struct.iter_unpack('<3hHI', l[0x52])); out = []
    for mesh in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        if mesh[-1] & 0x600 != 0x200 or not mesh[1]:  # lit bump only: the other vertex types carry no lightmap
            continue
        sort = sorts[mesh[-2]]; ix = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('i8')+sort[-1]
        w, h = sizes[sort[1]]
        out.append((pos[rec['pi'][ix]].reshape(-1, 3, 3), nrm[rec['ni'][ix]].reshape(-1, 3, 3),
                    (rec['light'][ix, :2]*(w, h)).reshape(-1, 3, 2), np.full(mesh[1], sort[1], 'i4')))
    p, n, uv, page = (np.concatenate(x) for x in zip(*out))
    shadow = np.frombuffer(l[0x7C], '<f4').reshape(-1, 3); idx = np.frombuffer(l[0x7E], '<u2'); casters = []; at = 0
    for first, count, opaque, _ in struct.iter_unpack('<2I2h', l[0x7F]):
        if opaque:
            casters.append(shadow[first+idx[at:at+3*count].astype('i8')].reshape(-1, 3, 3))
        at += 3*count
    return p, n, uv, page, np.concatenate(casters), sizes


def bake(l, toward_sun, work):
    """{page: (sun visibility, valid mask)} for every lightmap page."""
    p, n, uv, page, casters, sizes = bake_scene(l)
    key = lambda t: np.sort(np.ascontiguousarray(t, '<f4').reshape(-1, 9).view('V12').reshape(-1, 3), 1).view('V36').ravel()
    receives_and_casts = np.isin(key(p), key(casters))
    extra = casters[~np.isin(key(casters), key(p))]  # casters no receiver covers (none, for build_composite_map)
    tris = np.concatenate((p, extra)).astype('<f4'); cast = np.concatenate((receives_and_casts, np.ones(len(extra), bool)))
    tris.tofile(work/'bake-triangles.bin'); cast.astype('u1').tofile(work/'bake-casters.bin')
    result = {}
    for w, h in sorted(set(sizes)):
        group = [k for k, s in enumerate(sizes) if s == (w, h)]; local = {k: i for i, k in enumerate(group)}
        jobs = np.zeros(len(tris), JOB); jobs['p'] = tris; jobs['n'][:len(n)] = n
        mine = np.isin(page, group); jobs['uv'][:len(uv)][mine] = uv[mine]
        jobs['page'][:len(page)][mine] = [local[k] for k in page[mine]]
        jobs.tofile(work/'bake-jobs.bin'); out = work/f'sun-{w}.bin'
        run_logged(EXE, [work/'bake-triangles.bin', work/'bake-jobs.bin', out, w, h, len(group), work/'bake-casters.bin',
                         *toward_sun], work/f'sun-{w}.log')
        sun = np.fromfile(out, '<f4').reshape(len(group), h, w, 5); mask = np.fromfile(str(out)+'.mask', 'u1').reshape(len(group), h, w)
        for k in group:
            result[k] = (sun[local[k], ..., 0].copy(), mask[local[k]].astype(bool))
    return result, dict(receivers=len(p), receivers_casting=int(receives_and_casts.sum()), caster_only=len(extra))


def rtl_views(rtl, sizes):
    """Each page's (h, w, 4) visibility bytes in the RTL lump (ids, visibility, half-size plane per page)."""
    views, at = [], 0
    for w, h in sizes:
        views.append(np.ndarray((h, w, 4), 'u1', buffer=rtl, offset=at+w*h*4)); at += w*h*8+(w//2)*(h//2)*4
    if at != len(rtl):
        raise ValueError('RTL size does not match the lightmap pages')
    return views


def tile_fill(values, valid):
    """Invalid texels of a 4x4 chart tile with any valid texel take the mean of its valid ones."""
    h, w = values.shape; v = values.reshape(h//4, 4, w//4, 4); m = valid.reshape(h//4, 4, w//4, 4)
    count = m.sum((1, 3), keepdims=True); mean = (v*m).sum((1, 3), keepdims=True)/np.maximum(count, 1)
    return np.where(m | (count == 0), v, mean).reshape(h, w), (count > 0).repeat(4, 1).repeat(4, 3).reshape(h, w)


def normal(pitch, yaw):
    p, y = math.radians(pitch), math.radians(yaw)
    return [math.cos(p)*math.cos(y), math.cos(p)*math.sin(y), -math.sin(p)]


def run(action, package, pitch=None, yaw=None):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if action == 'apply' and (package/REPORT).exists():
        raise ValueError('Sun already re-baked: '+str(package/REPORT))
    work = Path(os.environ.get('SUN_WORK', ROOT/'output'))/(bsp.stem+'-sun'); work.mkdir(parents=True, exist_ok=True)
    l = read_lumps(bsp, (0, 3, 5, 0x1e, 0x36, 0x49, 0x4f, 0x50, 0x52, 0x53, 0x69, 0x7C, 0x7E, 0x7F))
    current = list(struct.unpack_from('<3f', l[5], 24))
    sun = current if action == 'check' else normal(pitch, yaw)
    pages, stats = bake(l, [-v for v in sun], work)
    sizes = [struct.unpack_from('<I2H', l[0x53], i)[1:] for i in range(0, len(l[0x53]), 8)]
    rtl = bytearray(l[0x69]); views = rtl_views(rtl, sizes); diff = []
    for k, (vis, valid) in pages.items():
        new = np.rint(np.clip(vis, 0, 1)*255).astype(int)
        diff.append(np.abs(new[valid]-views[k][..., 0][valid].astype(int)))
        if action == 'apply':
            filled, write = tile_fill(new.astype('f8'), valid)
            views[k][..., 0][write] = np.rint(filled[write]).astype('u1')
    d = np.concatenate(diff)
    stats.update(sun_normal=sun, previous_sun_normal=current, texels=int(len(d)), mean_difference=float(d.mean()),
                 within_8=float((d <= 8).mean()), changed_over_64=float((d > 64).mean()))
    if action == 'apply':
        from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
        from repair_environment_lighting import entities, text_entities
        lights = [WorldLightv3.from_bytes(l[0x36][i:i+112]) for i in range(0, len(l[0x36]), 112)]
        suns = [w for w in lights if np.allclose(list(w.normal), current, atol=1e-4)]
        if len(suns) != 1:
            raise ValueError('Expected one sun world light along the shadow environment normal')
        suns[0].normal = sun; shadow = bytearray(l[5]); struct.pack_into('<3f', shadow, 24, *sun)
        rows = entities(bsp)
        for e in rows:
            if e.get('classname') == 'light_environment' and e.get('lightEnvironmentIndex', '*0') == '*0':
                e.update(angles=f'{pitch} {yaw} 0', pitch=str(-pitch))
        temp = bsp.with_suffix('.sun.bsp')
        compact(bsp, temp, {0: text_entities(rows), 5: bytes(shadow), 0x36: b''.join(w.as_bytes() for w in lights),
                            0x69: bytes(rtl)}); os.replace(temp, bsp)
        (package/REPORT).write_text(json.dumps(stats, indent=2)+'\n')
    print(json.dumps(stats, indent=2), flush=True)
    return stats


def probes(package, positions, fixtures):
    """Character probes: replace only each probe's sun visibility (byte 0 of its four visibility bytes) with a bake
    along the map's current sun. Drop-Off's ambient coefficients and light references come from a later bake than
    output/composite's, so a full re-bake does not reproduce them; its sun byte matched on 98.8% of probes."""
    from rebake_native_prop_shadows import probe_lump
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    work = Path(os.environ.get('SUN_WORK', ROOT/'output'))/(bsp.stem+'-sun')
    l = read_lumps(bsp, (5, 0x65)); sun = struct.unpack_from('<3f', l[5], 24)
    tris = np.fromfile(work/'bake-triangles.bin', '<f4').reshape(-1, 3, 3)
    tris[np.fromfile(work/'bake-casters.bin', 'u1').astype(bool)].tofile(work/'probe-casters.bin')
    count = len(np.fromfile(positions, '<f4'))//3
    if count*48 != len(l[0x65]):
        raise ValueError('Probe positions do not match the probe lump')
    run_logged(WORK/'tools/bake_arena_character_probes.exe', [work/'probe-casters.bin', positions, fixtures,
               work/'probes.bin', *[-v for v in sun]], work/'probes.log')
    baked = np.frombuffer(probe_lump(np.fromfile(work/'probes.bin', '<f4').reshape(count, 24)), 'u1').reshape(count, 48)
    lump = np.frombuffer(l[0x65], 'u1').reshape(count, 48).copy(); before = lump[:, 32].copy()
    lump[:, 32] = baked[:, 32]  # <16h4B4hI: the first visibility byte follows the 16 coefficients
    temp = bsp.with_suffix('.probes.bsp'); compact(bsp, temp, {0x65: lump.tobytes()}); os.replace(temp, bsp)
    report = dict(probes=count, sunlit_before=int((before > 127).sum()), sunlit_after=int((lump[:, 32] > 127).sum()))
    (package/'sun-probes.json').write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps(report), flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'probes':
        probes(*a[1:4])
    else:
        run(a[0], a[1], *(float(v) for v in a[2:4]))
