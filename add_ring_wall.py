"""Draw Apex's storm/ring wall on an area cut-out's boundary (visual; collision is add_area_boundary.py).

A battle royale area cut-out ends at its play box; Apex marked arena edges with
its ring. The ring itself is engine-drawn, so this uses the current Apex storm
wall texture (common_mp `oly_storm_base_center`, a greyscale cloud) tinted to
the ring's red-orange, with opacity from the cloud brightness. The wall is a
STEP-tessellated quad strip INSET units inside the collision walls, facing
inward and outward, appended with released lightmap tiles (append_free_charts)
as the world-alpha material `apex_ring_wall`. Run after lighting, the
boundary and blends, before packaging:

  python add_ring_wall.py plan|materials|append|flatten thermal-station
  python add_ring_wall.py restore thermal-station   # back to the snapshot before rebuilding
"""
import json
import struct
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from add_area_boundary import PLAY
import recover_party_structure as structure
import recover_composite_details as recovery

STORM = Path('D:/Games/ApexToTitanfallWork/apex-current/ring/exported_files/material/oly_storm_base_center_rgdp/oly_storm_base_center_vxd.png')
NAME = 'apex_ring_wall'
TINT = (205, 110, 95)     # muted ring red: reads alike near (lit) and far (fogged)
OPACITY = (0.35, 0.85)    # opacity range mapped from cloud brightness
INSET = 4.0
STEP = 512.0
TILE = 2048.0             # texture repeat in world units
INDEX_FRACTION = .98
AMBIENT = .7               # self-lit level (linear, RGBM) in place of baked light


def paths(ident):
    out = folder(ident)
    return out, out/'ring-wall', out/'before-ring-wall'


def configure(ident):
    out, project, backup = paths(ident)
    structure.OUT, structure.PROJECT, structure.BACKUP = out, project, backup
    structure.TARGET, structure.SLUG, structure.SOURCE = CONFIG[ident]['target'], ident.replace('-', '_'), CONFIG[ident]['source']
    return out, project, backup


def textures(out):
    """Legion-style material folder: tinted albedo and opacity from the storm cloud."""
    from PIL import Image
    d = out/'legion/exported_files/materials'/NAME; d.mkdir(parents=True, exist_ok=True)
    cloud = np.asarray(Image.open(STORM).convert('L').resize((1024, 1024), Image.Resampling.LANCZOS)).astype('f4')/255
    albedo = np.clip(np.stack([np.full_like(cloud, c) for c in TINT], 2)*(0.6+0.4*cloud[:, :, None]), 0, 255).astype('u1')
    alpha = np.clip((OPACITY[0]+(OPACITY[1]-OPACITY[0])*cloud)*255, 0, 255).astype('u1')
    tool = ROOT/'tools/directxtex/texconv.exe'
    # Explicit matte channels: without them the glass template's defaults mirror the sky cubemap (teal streaks on
    # the north and west walls, view-dependent colour everywhere).
    flat = lambda c: Image.new('RGB', (64, 64), c)
    for image, semantic, fmt in ((Image.fromarray(albedo), 'albedo', 'BC1_UNORM_SRGB'), (Image.fromarray(alpha), 'opacityMultiply', 'BC4_UNORM'),
                                 (flat((128, 128, 255)), 'normal', 'BC1_UNORM'), (flat((0, 0, 0)), 'gloss', 'BC4_UNORM'),
                                 (flat((0, 0, 0)), 'spec', 'BC1_UNORM_SRGB')):
        png = d/f'{NAME}_{semantic}Texture.png'; image.save(png)
        subprocess.run([str(tool), '-nologo', '-y', *(['-srgb'] if 'SRGB' in fmt else []), '-f', fmt, '-o', str(d), str(png)],
                       check=True, capture_output=True)
        png.unlink()


def wall(box):
    (x0, y0), (x1, y1), (z0, z1) = box['min'], box['max'], box['z']
    x0 += INSET; y0 += INSET; x1 -= INSET; y1 -= INSET
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    zs = np.linspace(z0, z1, int(np.ceil((z1-z0)/STEP))+1); tris = []; s0 = 0.
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        length = float(np.hypot(bx-ax, by-ay)); n = int(np.ceil(length/STEP)); t = np.linspace(0, 1, n+1)
        inward = np.array([-(by-ay), bx-ax, 0.])/length  # counter-clockwise loop: left normal points into the box
        for i in range(n):
            for j in range(len(zs)-1):
                pa = (ax+(bx-ax)*t[i], ay+(by-ay)*t[i]); pb = (ax+(bx-ax)*t[i+1], ay+(by-ay)*t[i+1])
                ua, ub = (s0+length*t[i])/TILE, (s0+length*t[i+1])/TILE; va, vb = zs[j]/TILE, zs[j+1]/TILE
                q = [((*pa, zs[j]), (ua, va)), ((*pb, zs[j]), (ub, va)), ((*pb, zs[j+1]), (ub, vb)), ((*pa, zs[j+1]), (ua, vb))]
                for normal, order in ((inward, ((0, 2, 1), (0, 3, 2))), (-inward, ((0, 1, 2), (0, 2, 3)))):
                    for a, b, c in order:
                        tri = []
                        for k in (a, b, c):
                            (p, uv) = q[k]; tri.append([*p, *normal, uv[0], 1-uv[1], 255, 255, 255, 255])
                        tris.append(tri)
        s0 = (s0+length) % TILE  # texture repeats each TILE: keep u small
    return np.asarray(tris, 'f4')


def strip_scene(out):
    """The append records the ring in scene.npz/json; a rebuild must not inherit it as ordinary (shadow-casting)
    geometry, or every rebuild stacks another copy (4 copies darkened Thermal Station on 2026-10-21)."""
    z = np.load(out/'scene.npz'); names = list(z['names'])
    if NAME not in names:
        return 0
    i = names.index(NAME); keep = z['material'] != i; removed = int((~keep).sum())
    material = z['material'][keep]; material = np.where(material > i, material-1, material).astype(z['material'].dtype)
    np.savez(out/'scene.npz', triangles=z['triangles'][keep], material=material, names=np.asarray(names[:i]+names[i+1:])); z.close()
    scene = json.loads((out/'scene.json').read_text()); scene['materials'].pop(NAME, None); scene['triangles'] = int(keep.sum())
    (out/'scene.json').write_text(json.dumps({k: v for k, v in scene.items() if 'ring' not in k}, indent=2))
    return removed


def restore(ident):
    """Put back the pre-ring snapshot (bsp, stbsp, scene, physics, materials manifest and rpak) for a rebuild."""
    out, project, backup = paths(ident)
    for f in backup.rglob('*'):
        if f.is_file():
            target = out/f.relative_to(backup); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, target)
    shutil.rmtree(project); shutil.rmtree(backup)
    print('Restored', ident, 'without the ring wall', flush=True)


def plan(ident):
    out, project, backup = configure(ident)
    stale = strip_scene(out)
    if stale:
        print('Removed', stale, 'ring triangles inherited from an earlier build', flush=True)
    if (project/'result.json').exists():
        raise ValueError('Already applied; restore before-ring-wall to rebuild')
    project.mkdir(parents=True, exist_ok=True); textures(out)
    t = wall(PLAY[ident])
    np.savez(project/'addition.npz', triangles=t, material=np.zeros(len(t), 'i4'), names=[NAME], collision=np.empty((0, 3, 3), 'f4'))
    structure.write(project/'plan.json', dict(version=ident+'-ring-wall', added_props=0, added_triangles=len(t), placements=[],
                                             play_box=PLAY[ident], tint=TINT, opacity=OPACITY, texture=str(STORM)))
    print('Ring wall triangles', len(t), flush=True)


def materials(ident):
    """The world-alpha template is Homestead glass: F0 .03 at 208 and gloss .9 at 180 make grazing views of the
    wall mirror the sky (blue-grey faces beside red ones). A storm wall is matte."""
    out, project, backup = configure(ident); structure.materials()
    uber = out/'materials/assets/material/world'/ident.replace('-', '_')/(NAME+'_wld.uber')
    buf = bytearray(uber.read_bytes()); struct.pack_into('<f', buf, 180, 0.); struct.pack_into('<3f', buf, 212, 0., 0., 0.)
    uber.write_bytes(buf)
    subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(out/'materials/build.json')], check=True, capture_output=True)


def append(ident):
    out, project, backup = configure(ident)
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = out, project, out/(CONFIG[ident]['target']+'.bsp'), backup
    direction = -np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
    from append_free_charts import append as append_free
    append_free(out, INDEX_FRACTION, str(structure.WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    from build_preview_stbsp import build
    build(out, out/'materials', CONFIG[ident]['target'], ident.replace('-', '_')+'_world')


def flatten(ident):
    """A storm wall is self-lit, not shadowed. The world shader adds sun N.L wherever the RTL sun visibility is
    set, so faces turned from the sun were dark and see-through (teal sky) and sun-facing ones red. Per ring
    lightmap tile: sun visibility 0 (0x69 vis channel 0), one ambient level AMBIENT (0x62 layer 0, RGBM) and the
    face's own normal as the bent normal (0x62 layer 1); terrain shadows and lava bounce go with them."""
    import os
    from repair_preview_index_padding import read_lumps
    from compact_preview_bsp import compact
    from build_composite_map import DT
    from fix_overflow_overlays import native_names
    from apply_baked_lighting import encode_rgbm
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp')
    l = read_lumps(bsp, tuple(range(128))); names = native_names(l)
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); rec = np.frombuffer(l[0x49], DT)
    normals = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3)
    pages = len(l[0x62])//(2*2048*2048*4); sky = np.frombuffer(l[0x62], 'u1').reshape(pages, 2, 2048, 2048, 4).copy()
    rtl = bytearray(l[0x69]); tiles = {}
    for m in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        srt = sorts[m[-2]]
        if names[srt[0]] != NAME:
            continue
        ix = np.unique(np.frombuffer(l[0x4f], '<u2', m[1]*3, m[0]*2).astype('u4')+srt[-1])
        for (x, y), n in zip(np.floor(rec['light'][ix][:, :2]*2048/4).astype(int), normals[rec['ni'][ix]]):
            tiles[(srt[1], int(y)*4, int(x)*4)] = n
    if not tiles:
        raise ValueError('No ring wall lightmap tiles')
    ambient = encode_rgbm(np.full(3, AMBIENT))
    for (p, y, x), n in tiles.items():
        sky[p, 0, y:y+4, x:x+4] = ambient
        sky[p, 1, y:y+4, x:x+4, :3] = np.rint(np.clip((n+1)/2.007874, 0, 1)*255).astype('u1'); sky[p, 1, y:y+4, x:x+4, 3] = 255
        vis = np.ndarray((2048, 2048, 4), 'u1', buffer=rtl, offset=p*(2048*2048*8+1024*1024*4)+2048*2048*4)
        vis[y:y+4, x:x+4, 0] = 0
    temp = bsp.with_suffix('.ringlight.bsp'); compact(bsp, temp, {0x62: sky.tobytes(), 0x69: bytes(rtl)}); os.replace(temp, bsp)
    print('Ring wall lighting set over', len(tiles), 'tiles: ambient', AMBIENT, 'no direct sun', flush=True)

if __name__ == '__main__':
    {'restore': restore, 'plan': plan, 'materials': materials, 'append': append, 'flatten': flatten}[sys.argv[1]](sys.argv[2])
