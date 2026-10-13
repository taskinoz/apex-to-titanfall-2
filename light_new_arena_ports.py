"""Bake source sun visibility, local lights and native moving-model probes."""
import itertools
import json
import os
import struct
import subprocess
import sys
from new_arena_ports import CONFIG, ROOT, WORK, folder

sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
import numpy as np
from apply_baked_lighting import encode_rgbm
from compact_preview_bsp import compact
from repair_preview_index_padding import read_lumps
from build_character_lighting import make_tree
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3

LOCAL = np.dtype([('ids', '<u4'), ('vis', 'u1', 4), ('fill', '<f4', 3)])


def fixtures(ident):
    out = folder(ident)
    report = json.loads((out / 'scene.json').read_text())
    offset = np.asarray(CONFIG[ident]['offset'])
    low, high = np.asarray(CONFIG[ident]['bounds'])
    candidates = []
    for i, e in enumerate(report['source_entities']):
        if e.get('classname') not in ('light', 'light_spot'):
            continue
        p = np.asarray([float(v) for v in e['origin'].split()]) + offset
        if not (np.all(p >= low) and np.all(p <= high)):
            continue
        v = [float(v) for v in e.get('_light', '255 255 255 300').split()]
        colour = (np.asarray(v[:3]) / 255) ** 2.2 * min(2, max(.25, v[3] / 1500))
        radius = min(1800, max(256, float(e.get('_zero_percent_distance', e.get('_distance', '800')))))
        candidates.append(dict(source_entity=i, origin=p.tolist(), colour=colour.tolist(), radius=radius))
    picked = []
    if candidates:
        points = np.asarray([e['origin'] for e in candidates])
        picked = [int(np.linalg.norm(points - points.mean(0), axis=1).argmin())]
        distance = np.full(len(points), np.inf)
        while len(picked) < min(56, len(candidates)):
            distance = np.minimum(distance, np.linalg.norm(points - points[picked[-1]], axis=1))
            distance[picked] = -1
            picked.append(int(distance.argmax()))
    lights = [dict(candidates[j], hardware_index=i + 2) for i, j in enumerate(picked)]
    data = np.zeros(len(lights), np.dtype([('p', '<f4', 3), ('radius', '<f4'), ('colour', '<f4', 3), ('index', '<u4')]))
    for i, e in enumerate(lights):
        data[i] = e['origin'], e['radius'], e['colour'], e['hardware_index']
    data.tofile(out / 'fixtures.bin')
    (out / 'interior-lights.json').write_text(json.dumps(dict(source_lights=len(candidates), lights=lights), indent=2))
    return lights


def run_logged(executable, args, log):
    with log.open('w') as stream:
        subprocess.run([str(executable), *map(str, args)], stdout=stream, stderr=subprocess.STDOUT, check=True)
    print(log.read_text(), flush=True)


def build(ident):
    out = folder(ident)
    source = out / (CONFIG[ident]['target'] + '.bsp')
    cfg = json.loads((out / 'bake.json').read_text())
    w, h, pages = cfg['width'], cfg['height'], cfg['pages']
    lights = fixtures(ident)
    direction = -np.asarray(json.loads((out / 'environment.json').read_text())['native_sun_normal'])
    run_logged(WORK / 'tools/bake_arena_environment.exe',
        [out / 'bake-triangles.bin', out / 'bake-jobs.bin', out / 'sun.bin', w, h, pages,
         out / 'bake-casters.bin', *direction], out / 'sun-bake.log')
    run_logged(ROOT / 'tools/bake_interior_lighting.exe',
        [out / 'bake-triangles.bin', out / 'bake-jobs.bin', out / 'fixtures.bin', out / 'local.bin',
         w, h, pages, out / 'bake-casters.bin'], out / 'local-bake.log')
    sun = np.memmap(out / 'sun.bin', '<f4', 'r', shape=(pages, h, w, 5))
    valid = np.memmap(out / 'sun.bin.mask', 'u1', 'r', shape=(pages, h, w))
    local = np.memmap(out / 'local.bin', LOCAL, 'r', shape=(pages, h, w))
    scene = json.loads((out / 'scene.json').read_text())
    names = list(scene['materials'])
    offsets = {}
    first = 0
    for name in names:
        count = scene['materials'][name]
        offsets[name] = first, first + count
        first += count
    sky = bytearray(); rtl = bytearray(); stats = []
    # Extend each triangle's valid samples only inside its own four-texel chart.
    # A global nearest-neighbour fill was responsible for earlier wall seams.
    perpage = (w // 4) * (h // 4)
    for page in range(pages):
        values = np.asarray(sun[page]).copy()
        lv = np.asarray(local[page]).copy()
        for y, x in itertools.product(range(0, h, 4), range(0, w, 4)):
            mask = valid[page, y:y + 4, x:x + 4].astype(bool)
            if not mask.any():
                continue
            ys, xs = np.nonzero(mask)
            for yy, xx in zip(*np.nonzero(~mask)):
                k = int(((ys - yy) ** 2 + (xs - xx) ** 2).argmin())
                values[y + yy, x + xx] = values[y + ys[k], x + xs[k]]
                lv[y + yy, x + xx] = lv[y + ys[k], x + xs[k]]
        yy, xx = np.indices((h, w))
        tiles = page * perpage + (yy // 4) * (w // 4) + xx // 4
        a, b = offsets['sky']
        photo = (tiles >= a) & (tiles < b)
        ambient = np.asarray([.055, .065, .085]) * (.65 + .35 * np.maximum(values[..., 1, None], 0)) + lv['fill']
        ambient[photo] = [.8, .8, .8]
        bent = np.empty((h, w, 4), 'u1')
        bent[..., :3] = np.rint(np.clip((values[..., 2:5] + 1) / 2.007874, 0, 1) * 255).astype('u1')
        bent[..., 3] = 255
        sky.extend(encode_rgbm(ambient).tobytes()); sky.extend(bent.tobytes())
        ids = lv['ids'].copy(); visibility = lv['vis'].copy()
        visibility[..., 0] = np.rint(np.clip(values[..., 0], 0, 1) * 255).astype('u1')
        ids[photo] = 0x00ffffff; visibility[photo] = 0
        rtl.extend(ids.tobytes()); rtl.extend(visibility.tobytes()); rtl.extend(bytes((w // 2) * (h // 2) * 4))
        stats.append(dict(page=page, valid_luxels=int(valid[page].sum()),
                          sunlit_fraction=float(values[..., 0][valid[page].astype(bool)].mean())))
    l = read_lumps(source, (0x36, 0x65, 0x68))
    world = bytearray(l[0x36])
    reference = read_lumps(ROOT / 'inputs/titanfall2-homestead/maps/mp_homestead.bsp', (0x36,))[0x36]
    template = next(WorldLightv3.from_bytes(reference[i:i + 112]) for i in range(0, len(reference), 112)
        if WorldLightv3.from_bytes(reference[i:i + 112]).type.name == 'POINT' and
        abs(WorldLightv3.from_bytes(reference[i:i + 112]).linear * WorldLightv3.from_bytes(reference[i:i + 112]).radius + 1) < 1e-5)
    for e in lights:
        t = WorldLightv3.from_bytes(template.as_bytes())
        t.origin=e['origin']; t.intensity=e['colour']; t.radius=e['radius']; t.linear=-1/t.radius
        t.quadratic=0; t.constant=1; t.texture_data=0; t.parent=0; t.style=0
        world.extend(t.as_bytes())
    points = []
    for e in scene['placements']:
        if any(w in e['model'].lower() for w in ('floor', 'stairs', 'stair', 'terrain', 'building', 'rock')):
            p = np.rint(np.asarray(e['origin']) / 512) * 512
            for z in (64, 192, 512, 1024):
                points.append(p + [0, 0, z])
    low, high = np.asarray(CONFIG[ident]['bounds'])
    for x, y, z in itertools.product(range(int(low[0]), int(high[0]), 1024),
            range(int(low[1]), int(high[1]), 1024), (-1024, -512, 0, 512, 1024, 2048, 4096)):
        points.append([x, y, z])
    points = np.unique(np.asarray(points, '<f4'), axis=0)
    points.tofile(out / 'probe-positions.bin')
    triangles = np.fromfile(out / 'bake-triangles.bin', '<f4').reshape(-1, 3, 3)
    casters = np.fromfile(out / 'bake-casters.bin', 'u1').astype(bool)
    triangles[casters].tofile(out / 'probe-casters.bin')
    run_logged(WORK / 'tools/bake_arena_character_probes.exe',
        [out / 'probe-casters.bin', out / 'probe-positions.bin', out / 'fixtures.bin', out / 'probes.bin', *direction],
        out / 'probe-bake.log')
    values = np.fromfile(out / 'probes.bin', '<f4').reshape(len(points), 24)
    values[:, :12] *= np.asarray([.055/.025]*4 + [.065/.027]*4 + [.085/.032]*4)
    probes = b''.join(struct.pack('<16h4B4hI', *np.rint(np.clip(row[:16]*8192,-32768,32767)).astype(int),
        *row[16:20].astype(int), *row[20:24].astype(int), 0) for row in values)
    tree, order = make_tree(points)
    references = b''.join(struct.pack('<3fIi', *points[i], int(i), 0) for i in order)
    parent = struct.pack('<i6I', 0, 0, len(points), 0, len(points), 0, len(tree)//8)
    target = source.with_suffix('.lit.bsp')
    compact(source, target, {4: parent, 0x36: world, 0x62: sky, 0x69: rtl,
        0x7a: struct.pack('<63h', *range(len(lights)+2), *[-1]*(61-len(lights))),
        0x65: probes, 0x67: tree, 0x68: references})
    os.replace(target, source)
    (out / 'lighting.json').write_text(json.dumps(dict(source_sun_ray=direction.tolist(),
        surface_pages=pages, local_lights=len(lights), character_probes=len(points), charts=stats,
        limitations=['Source spot lights approximated as points', 'No bounced GI or fresh reflection cubemaps']), indent=2))
    glow(ident)


def glow(ident):
    """Apply constant baked radiance only to recovered molten-material charts."""
    out=folder(ident);source=out/(CONFIG[ident]['target']+'.bsp');scene=json.loads((out/'scene.json').read_text())
    mapping=json.loads((out/'materials/mapping.json').read_text())['materials'];cfg=json.loads((out/'bake.json').read_text())
    w,h,pages=cfg['width'],cfg['height'],cfg['pages'];l=read_lumps(source,(0x62,0x69))
    sky=bytearray(l[0x62]);rtl=bytearray(l[0x69]);first=0;changed=0;stride=w*h*8+(w//2)*(h//2)*4
    for name,count in scene['materials'].items():
        colour=mapping[name].get('static_glow_ambient')
        if colour:
            texel=encode_rgbm(np.asarray(colour)).tobytes()
            for i in range(first,first+count):
                page=i//((w//4)*(h//4));tile=i%((w//4)*(h//4));x=tile%(w//4)*4;y=tile//(w//4)*4
                for yy in range(y,y+4):
                    at=page*w*h*8+(yy*w+x)*4;sky[at:at+16]=texel*4
                    at=page*stride+(yy*w+x)*4;rtl[at:at+16]=struct.pack('<I',0x00ffffff)*4
                    at=page*stride+w*h*4+(yy*w+x)*4;rtl[at:at+16]=bytes(16)
                changed+=1
        first+=count
    if changed:
        target=source.with_suffix('.glow.bsp');compact(source,target,{0x62:sky,0x69:rtl});os.replace(target,source)
    (out/'material-glow.json').write_text(json.dumps(dict(charts=changed,source_layer_masks_preserved=True,
        approximation='Frozen lava emission through constant baked radiance; animated shader and dynamic lava illumination not reproduced'),indent=2))


def ambient(ident,factor=2.0):
    """Calibrate the preview ambient floor consistently for surfaces and pilots."""
    out=folder(ident);receipt=out/'ambient-calibration.json'
    if receipt.exists():return
    source=out/(CONFIG[ident]['target']+'.bsp');cfg=json.loads((out/'bake.json').read_text())
    scene=json.loads((out/'scene.json').read_text());w,h,pages=cfg['width'],cfg['height'],cfg['pages'];l=read_lumps(source,(0x62,0x65,0x36))
    sky=np.frombuffer(l[0x62],'u1').reshape(pages,2,h,w,4).copy();first=0;skip=np.zeros(pages*(w//4)*(h//4),bool)
    for name,count in scene['materials'].items():
        if name=='sky':skip[first:first+count]=True
        first+=count
    yy,xx=np.indices((h,w))
    for page in range(pages):
        pixels=sky[page,0];rgb=pixels[:,:,:3]/255*(pixels[:,:,3,None]/255*3.984375+.015625)
        mask=~skip[page*(w//4)*(h//4)+(yy//4)*(w//4)+xx//4]
        pixels[mask]=encode_rgbm(rgb[mask]*factor)
    probes=np.frombuffer(l[0x65],np.dtype([('sh','<i2',16),('rest','V16')])).copy()
    probes['sh'][:,:12]=np.rint(np.clip(probes['sh'][:,:12].astype('f4')*factor,-32768,32767)).astype('<i2')
    lights=bytearray(l[0x36]);t=WorldLightv3.from_bytes(lights[:112]);t.intensity=[v*factor for v in t.intensity];lights[:112]=t.as_bytes()
    target=source.with_suffix('.ambient.bsp');compact(source,target,{0x62:sky.tobytes(),0x65:probes.tobytes(),0x36:lights});os.replace(target,source)
    receipt.write_text(json.dumps(dict(factor=factor,sky_photo_unchanged=True,source_sun_and_collision_unchanged=True),indent=2))
    glow(ident)


if __name__ == '__main__':
    if sys.argv[1]=='glow':
        glow(sys.argv[2]);sys.exit(0)
    if sys.argv[1]=='ambient':
        ambient(sys.argv[2]);sys.exit(0)
    for ident in CONFIG if sys.argv[1] == 'all' else [sys.argv[1]]:
        build(ident)
