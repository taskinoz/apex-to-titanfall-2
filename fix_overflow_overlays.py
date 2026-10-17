"""Overflow 0.4.1: coplanar Apex overlays drawn opaque (user report: z-fighting and flat textures).

Located with probe_view.py on the report screenshots; each spot shows two
materials at the identical view distance:

* stencil_white_blend (REFINERY lettering, capsule stencils) and
  sign_directional_blue (arrow signs) are decals whose albedo alpha is the
  stencil/sign shape. They move to the tested world-alpha decal preset of
  slum_grime_decal_01_bt (depth-biased, alpha flag) with an opacity map taken
  from that alpha channel.
* icelandic_dirt_01_wld_b2t fades over the asphalt by vertex alpha, which the
  native world shader cannot read; drawn opaque it is a flat brown sheet. It is
  retired, leaving the asphalt blend underneath.
* lava_river_v3_bm is an exact duplicate of every lava_river_flow triangle
  under the glowing flow layer; it is retired so only the flow is drawn.

  python fix_overflow_overlays.py apply|stage
"""
import argparse
import json
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
from new_arena_ports import ROOT, WORK, folder
from repair_preview_index_padding import read_lumps
from build_composite_map import DT

OUT = folder('overflow')
PROJECT = OUT/'overlay-repair'
BACKUP = OUT/'before-0.4.1'
VERSION, BASELINE = '0.4.1', '0.4.0'
RETIRE = ('icelandic_dirt_01_wld_b2t', 'lava_river_v3_bm')
DECALS = {'stencil_white_blend': 1.0, 'sign_directional_blue': 2.0}  # opacity = albedo alpha x scale
PRESET = 'slum_grime_decal_01_bt'
MATERIALS = OUT/'materials/assets/material/world/overflow'
TEXTURES = OUT/'materials/assets/texture/overflow'
TEXCONV = ROOT/'tools/directxtex/texconv.exe'


def snapshot():
    if BACKUP.exists():
        raise ValueError('Snapshot exists; restore it to rebuild')
    BACKUP.mkdir(parents=True)
    for name in ('mp_overflow.bsp', 'mp_overflow.stbsp', 'materials/mapping.json', 'materials/build.json',
                 'materials/build/overflow_world.rpak'):
        (BACKUP/name).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(OUT/name, BACKUP/name)
    for n in DECALS:
        shutil.copy2(MATERIALS/f'{n}_wld.json', BACKUP/f'{n}_wld.json'); shutil.copy2(MATERIALS/f'{n}_wld.uber', BACKUP/f'{n}_wld.uber')


def native_names(l):
    out = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        out.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    return out


def retire_meshes(bsp):
    """Drop every mesh of the RETIRE materials (by material: the lava base shares its flow layer's positions)."""
    import os
    from compact_preview_bsp import compact
    from repair_camera_visibility import build_camera_visibility
    from repair_native_render_partitions import reorder
    l = read_lumps(bsp, tuple(range(128))); buf = {k: bytearray(v) for k, v in l.items()}; names = native_names(l)
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3); rec = np.frombuffer(l[0x49], DT)
    keep, bounds, indices, counts = [], bytearray(), bytearray(), {}
    for mesh in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        s = sorts[mesh[-2]]; name = names[s[0]]
        if name in RETIRE:
            counts[name] = counts.get(name, 0)+mesh[1]; continue
        local = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).reshape(-1, 3)
        record = list(mesh); record[0] = len(indices)//2; indices.extend(local.tobytes())
        if len(local) & 1:
            indices.extend(struct.pack('<3H', *[int(local[-1, -1])]*3))
        p = pos[rec['pi'][local.reshape(-1).astype('u4')+s[-1]]]; lo = p.min(0)-.02; hi = p.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
        keep.append(struct.pack('<I3H6b2h2BHI', *record)); bounds.extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
    if set(counts) != set(RETIRE):
        raise ValueError(f'Missing overlay meshes: {counts}')
    count = len(keep); buf[0x4f] = indices; buf[0x50] = bytearray(b''.join(keep)); buf[0x51] = bounds
    struct.pack_into('<2I', buf[0xe], 24, 0, count)
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    buf.update(reorder(buf)[0])
    temp = bsp.with_suffix('.overlay.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    return counts


def alpha_flags(bsp):
    """Decal materials join the alpha pass: texdata and mesh flag 0x10."""
    import os
    from compact_preview_bsp import compact
    l = read_lumps(bsp, tuple(range(128))); buf = {k: bytearray(v) for k, v in l.items()}; names = native_names(l)
    texdata = [i for i, n in enumerate(names) if n in DECALS]
    for i in texdata:
        at = i*36+32; struct.pack_into('<I', buf[2], at, struct.unpack_from('<I', l[2], at)[0] | 0x10)
    sorts = {i for i, s in enumerate(struct.iter_unpack('<3hHI', l[0x52])) if s[0] in texdata}; meshes = 0
    for at in range(0, len(l[0x50]), 28):
        r = struct.unpack_from('<I3H6b2h2BHI', l[0x50], at)
        if r[-2] in sorts:
            struct.pack_into('<I', buf[0x50], at+24, r[-1] | 0x10); meshes += 1
    temp = bsp.with_suffix('.overlay.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    return dict(texdata=len(texdata), meshes=meshes)


def opacity(name, scale):
    from PIL import Image
    PROJECT.mkdir(parents=True, exist_ok=True)
    src = OUT/'legion/exported_files/materials'/name/(name+'_albedoTexture.dds')
    subprocess.run([str(TEXCONV), '-nologo', '-y', '-ft', 'png', '-f', 'R8G8B8A8_UNORM', '-o', str(PROJECT), str(src)], check=True, capture_output=True)
    png = PROJECT/(name+'_albedoTexture.png'); a = np.asarray(Image.open(png).convert('RGBA'))[:, :, 3].astype('f4')
    mask = PROJECT/(name+'_opacityMultiply.png'); Image.fromarray(np.clip(a*scale, 0, 255).astype('u1')).save(mask)
    subprocess.run([str(TEXCONV), '-nologo', '-y', '-f', 'BC4_UNORM', '-dx10', '-o', str(PROJECT), str(mask)], check=True, capture_output=True)
    dest = TEXTURES/(name+'_opacityMultiply.dds'); shutil.move(str(PROJECT/(name+'_opacityMultiply.dds')), str(dest))
    return 'texture/overflow/'+name+'_opacityMultiply.rpak'


def materials():
    from recover_arena_atmosphere import NativeMaterials
    preset = json.loads((MATERIALS/f'{PRESET}_wld.json').read_text())
    manifest = json.loads((OUT/'materials/build.json').read_text()); builder = NativeMaterials(OUT/'materials', 'overflow', manifest)
    mapping_path = OUT/'materials/mapping.json'; mapping = json.loads(mapping_path.read_text())
    for name, scale in DECALS.items():
        old = json.loads((BACKUP/f'{name}_wld.json').read_text()); path = opacity(name, scale)
        spec = dict(preset); spec.update(name=old['name'], surfaceProp=old['surfaceProp'], width=old['width'], height=old['height'])
        spec['$textures'] = {k: old['$textures'][k] for k in ('0', '1', '2', '3') if k in old['$textures']}; spec['$textures']['13'] = path
        (MATERIALS/f'{name}_wld.json').write_text(json.dumps(spec, indent=2))
        shutil.copy2(MATERIALS/f'{PRESET}_wld.uber', MATERIALS/f'{name}_wld.uber')
        builder.files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True})
        mapping['materials'][name].update(textures=spec['$textures'], transparent=True,
                                          native_source_channels='World-alpha decal; opacity from source albedo alpha')
    mapping_path.write_text(json.dumps(mapping, indent=2)); builder.finish(manifest)


def apply():
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; restore before-0.4.1 to rebuild')
    snapshot(); PROJECT.mkdir(parents=True, exist_ok=True)
    counts = retire_meshes(OUT/'mp_overflow.bsp'); flags = alpha_flags(OUT/'mp_overflow.bsp'); materials()
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_overflow', 'overflow_world')
    result = dict(version=VERSION, retired_triangles=counts, decals=DECALS, alpha_flags=flags)
    (PROJECT/'result.json').write_text(json.dumps(result, indent=2)); print(json.dumps(result), flush=True)


def stage():
    from map_pack_lifetime import audit as pack_audit
    from package_player_mods import digest
    accepted = ROOT/'northstar/ArenaOverflow'
    if json.loads((accepted/'mod.json').read_text())['Version'] != BASELINE:
        raise ValueError('Unexpected accepted baseline')
    if digest(BACKUP/'mp_overflow.bsp') != digest(accepted/'mod/maps/mp_overflow.bsp'):
        raise ValueError('Round baseline is not the accepted payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run the binary audit first')
    candidate = WORK/'overflow-candidates'/'ArenaOverflow-0.4.1'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for rel, src in (('mod/maps/mp_overflow.bsp', OUT/'mp_overflow.bsp'), ('mod/maps/mp_overflow.stbsp', OUT/'mp_overflow.stbsp'),
                     ('paks/overflow_world.rpak', OUT/'materials/build/overflow_world.rpak')):
        shutil.copy2(src, candidate/rel)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = VERSION
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2)); pack_audit(candidate/'paks', 'mp_overflow')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=['apply', 'stage'])
    dict(apply=apply, stage=stage)[p.parse_args().action]()
