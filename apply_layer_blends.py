"""Restore Apex two-layer (bm) blending with Titanfall's native blend shader.

The previews bound only layer 1 of each Apex blend material: rock tops lost
their sand, moss and snow, and blended ground showed one texture. Titanfall's
native wld bm shader (Coliseum `concrete_plates_plain_wet_bm`, shaderset
0x1C26FE9E094361FE) evaluates the same equation as the Apex source:

    w = saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)
    albedo = lerp(albedo1, albedo2, w)

with all layers sampled at the mesh UV (t0-t3 layer 1, t22 mask, t23-t26
layer 2) and ramp at uber offset 92. This script:

* writes the Apex blend input into each corner's vertex alpha. For
  vertex-alpha materials that is the source vertex colour alpha (bsp_tool's
  `negative_one` for world geometry, VG colour for props). For z-up
  materials it is the source term saturate((n.z - maxCos)/(minCos - maxCos))
  * scale from the vertex normal.
* rebinds those materials to the native bm shader with source textures.

Geometry, indices, collision, lightmaps, entities and every other material
are unchanged. Layers whose Apex UV differs from the mesh UV (world-projected
layer 2) are sampled at the mesh UV: an approximation of tiling, not colour.
"""
import argparse
import json
import math
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder, source_bsp
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT

NATIVE_BM = 0x3C9AF4B3C2D1E723
NATIVE_BM_COLPASS = 0x4DD5D05777540133
NATIVE_BM_SHADERSET = 0x1C26FE9E094361FE
SKIP = ('_b2t', 'transparent')


def paths(ident):
    out = folder(ident)
    return out, out/'layer-blend', out/'before-layer-blend', out/(CONFIG[ident]['target']+'.bsp')


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')


def selection(ident):
    out = folder(ident)
    survey = json.loads((out/'layer-blend-survey.json').read_text())
    mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    chosen = {}
    for name, row in survey.items():
        if any(s in name for s in SKIP) or mapping.get(name, {}).get('transparent'):
            continue
        layers = [row.get(k) for k in ('albedoTexture', 'albedo2Texture', 'layerBlendTexture')]
        if any(l is None or l['kind'] not in ('mesh', 'world') for l in layers):
            continue
        d = out/'legion/exported_files/materials'/name
        if not (d/(name+'_albedo2Texture.dds')).exists() or not (d/(name+'_layerBlendTexture.dds')).exists():
            continue
        chosen[name] = row
    return chosen


def snapshot(ident):
    out, project, backup, bsp = paths(ident)
    if backup.exists():
        raise ValueError('Rollback already exists')
    backup.mkdir(parents=True)
    for p in (bsp, bsp.with_suffix('.stbsp'), out/'scene.json', out/'source-build.json'):
        shutil.copy2(p, backup/p.name)
    shutil.copytree(out/'materials', backup/'materials')
    live = out/'materials/build'/(ident.replace('-', '_')+'_world.rpak')
    temp = live.with_suffix('.detached.rpak'); shutil.copy2(live, temp); os.replace(temp, live)


def source_alpha(ident, names):
    """Positions and source blend alpha for world and prop vertices per material."""
    sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    from bsp_tool.branches.respawn.titanfall import MeshFlags
    from read_vg_static import load
    from stage_prop_geometry import rotation
    offset = np.asarray(CONFIG[ident]['offset'], 'f8')
    pos = {n: [] for n in names}; val = {n: [] for n in names}; lower = {n.lower(): n for n in names}
    geo = bsp_tool.load_bsp(str(source_bsp(ident))).external
    for mesh in geo.MESHES:
        sort = geo.MATERIAL_SORTS[mesh.material_sort]
        # Some source BSPs (Firing Range) store surface names in upper case.
        name = lower.get(geo.texture_data_surface_name(sort.texture_data).replace('\\', '/').rsplit('/', 1)[-1].lower())
        if name is None:
            continue
        records = getattr(geo, (mesh.flags & MeshFlags.MASK_VERTEX).name)
        for index in geo.MESH_INDICES[mesh.first_mesh_index:mesh.first_mesh_index+mesh.num_triangles*3]:
            v = records[index+sort.vertex_offset]
            pos[name].append(np.asarray(list(geo.VERTICES[v.position_index]))+offset)
            val[name].append(np.array([v.negative_one], '<i4').view('u1')[3]/255)
    scene = json.loads((folder(ident)/'scene.json').read_text()); cache = {}
    for p in scene['placements']:
        f = p.get('folder')
        if not f or not (Path(f)/(Path(f).name+'.vg')).exists():
            continue
        key = (f, p['lod'])
        if key not in cache:
            try:
                cache[key] = load(f, p['lod'], True)
            except ValueError:
                cache[key] = None
        if cache[key] is None:
            continue
        sections, slots, skins = cache[key]
        skin = skins[min(p['skin'], len(skins)-1)]
        matrix = np.asarray(rotation(p['angles']))
        for s, slot in zip(sections, slots):
            if not len(s) or skin[slot] not in pos:
                continue
            a = np.asarray(s, 'f8').reshape(-1, 12)
            pos[skin[slot]].extend(a[:, :3]@matrix.T*p['scale']+p['origin'])
            val[skin[slot]].extend(a[:, 11]/255)
    return {n: (np.asarray(pos[n]).reshape(-1, 3), np.asarray(val[n])) for n in names}


def patch(ident):
    out, project, backup, bsp = paths(ident)
    if (project/'blend-result.json').exists():
        raise ValueError('Already applied; restore before-layer-blend to rebuild')
    if not backup.exists():
        snapshot(ident)
    project.mkdir(exist_ok=True)
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from scipy.spatial import cKDTree
    chosen = selection(ident)
    alpha_names = [n for n, r in chosen.items() if not r['zup']]
    sources = source_alpha(ident, alpha_names)
    trees = {n: cKDTree(sources[n][0]) for n in alpha_names if len(sources[n][0])}
    l = read_lumps(bsp, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    native = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        native.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    records = np.frombuffer(buf[0x49], DT).copy()
    positions = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8')
    normals = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3).astype('f8')
    report = {n: dict(corners=0, matched=0, mean_alpha=0.) for n in chosen}
    for mesh in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        sort = sorts[mesh[-2]]; name = native[sort[0]]
        if name not in chosen:
            continue
        ix = np.unique(np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('u4')+sort[-1])
        row = chosen[name]
        if row['zup']:
            n = normals[records['ni'][ix]]; n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            lo, hi = row['zup_params']['max'][0], row['zup_params']['min'][0]
            a = np.clip((n[:, 2]-lo)/(hi-lo), 0, 1)*row['zup_params']['scale']
            matched = len(ix)
        elif name in trees:
            d, j = trees[name].query(positions[records['pi'][ix]])
            ok = d < .05
            a = np.where(ok, sources[name][1][j], 0.)
            matched = int(ok.sum())
        else:
            a = np.zeros(len(ix)); matched = 0
        records['color'][ix, 3] = np.rint(np.clip(a, 0, 1)*255).astype('u1')
        r = report[name]; r['mean_alpha'] += float(a.sum()); r['corners'] += len(ix); r['matched'] += matched
    for r in report.values():
        r['mean_alpha'] = r['mean_alpha']/max(r['corners'], 1)
    # Materials without matched source alpha keep their single-layer shader.
    unmatched = sorted(n for n, r in report.items() if r['corners'] and r['matched'] < .95*r['corners'])
    buf[0x49] = bytearray(records.tobytes())
    temp = bsp.with_suffix('.blend.bsp'); compact(bsp, temp, {0x49: buf[0x49]}); os.replace(temp, bsp)
    write(project/'blend-patch.json', dict(materials=report, zup=[n for n, r in chosen.items() if r['zup']],
                                          excluded_unmatched=unmatched))
    print('Wrote blend alpha for', len(report), 'materials', flush=True)


def convert(source, dest):
    """Resident 1024-capped copy with full mips, keeping the source BC format."""
    from optimize_preview_textures import dds, FORMATS
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes(); info = dds(raw); fmt = FORMATS[info['format']][0]
    scale = min(1, 1024/max(info['width'], info['height']))
    w, h = max(4, round(info['width']*scale)), max(4, round(info['height']*scale))
    temp = dest.parent/('_conv_'+dest.stem); temp.mkdir(exist_ok=True)
    run = subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '--ignore-mips', '-f', fmt,
                          '-dx10', '-gpu', '0', '-bc', 'q', '-if', 'BOX', '-wrap', '-w', str(w), '-h', str(h), '-o', str(temp), str(source)],
                         capture_output=True, text=True)
    if run.returncode:
        raise ValueError(run.stdout+run.stderr)
    shutil.move(str(next(temp.glob('*.dds'))), dest); shutil.rmtree(temp)


def embed_shaderset(slug, assets):
    from extract_native_material import NativePak
    from extract_world_glass_shader import shader
    from build_phase_runner_presentation import guid
    paks = [NativePak(ROOT/f'inputs/tf2-rpak-work/{n}.raw.rpak') for n in ('coliseum', 'common', 'homestead')]
    def find(g):
        for p in paks:
            for a in p.assets:
                if a['guid'] == g:
                    return p, a
        raise ValueError('Native asset not found: '+hex(g))
    pak, a = find(NATIVE_BM_SHADERSET); at = pak.address(a['header'])
    vs, ps = struct.unpack_from('<2Q', pak.data, at+72)
    vt, pt, samplers = struct.unpack_from('<3H', pak.data, at+24)
    first, resources = struct.unpack_from('<2H', pak.data, at+30)
    pixel = shader(*find(ps))[0]; vertex = shader(*find(vs))[0]
    name = slug+'_native_bm'; path = 'shaderset/'+name+'.rpak'
    target = (assets/path).with_suffix('.msw'); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'MSW\x03\x01'+struct.pack('<2Q3H2B2I', guid('shader/'+name+'_ps.rpak'), guid('shader/'+name+'_vs.rpak'),
                                                pt, vt, samplers, first, resources, 37, 37+len(pixel))+pixel+vertex)
    return path


def materials(ident):
    from extract_native_material import NativePak
    from bake_terrain_transitions import save_mips
    from PIL import Image
    out, project, backup, bsp = paths(ident)
    slug = ident.replace('-', '_'); mats = out/'materials'; assets = mats/'assets'
    mapping = json.loads((mats/'mapping.json').read_text()); manifest = json.loads((mats/'build.json').read_text())
    files = {f['_path']: f for f in manifest['files']}
    coliseum = NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
    spec0, uber0 = coliseum.material(next(a for a in coliseum.assets if a['guid'] == NATIVE_BM))
    cspec0, cuber0 = coliseum.material(next(a for a in coliseum.assets if a['guid'] == NATIVE_BM_COLPASS))
    shaderset = embed_shaderset(slug, assets); files[shaderset] = dict(_type='shds', _path=shaderset)
    flat = f'texture/{slug}/layer_blend_flat_normal.rpak'
    save_mips(Image.new('RGBA', (4, 4), (128, 128, 255, 255)), (assets/flat).with_suffix('.dds'))
    files[flat] = dict(_type='txtr', _path=flat, **{'$disableStreaming': True})
    from apex_material_constants import ApexMaterials
    source = ApexMaterials(out/'paks'/(CONFIG[ident]['source']+'.rpak'))
    report = {}
    excluded = set(json.loads((project/'blend-patch.json').read_text())['excluded_unmatched'])
    for name, row in selection(ident).items():
        if name in excluded:
            continue
        r = mapping['materials'][name]; base = name
        d = out/'legion/exported_files/materials'/name
        tex = dict(r['textures'])
        for slot, semantic, fallback in (('22', 'layerBlend', None), ('23', 'albedo2', None), ('24', 'normal2', '1'),
                                         ('25', 'gloss2', '2'), ('26', 'spec2', '3')):
            src = d/f'{name}_{semantic}Texture.dds'
            if src.exists():
                path = f'texture/{slug}/{base}_{semantic}.rpak'
                if not (assets/path).with_suffix('.dds').exists():
                    convert(src, (assets/path).with_suffix('.dds'))
                files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); tex[slot] = path
            elif fallback and fallback in tex:
                tex[slot] = tex[fallback]
        tex['15'] = flat
        # Some source materials (Overflow lava_river_v3_bm) lack a PBR layer-1 map.
        for slot, semantic, colour in (('1', 'normal', (128, 128, 255, 255)), ('2', 'gloss', (30, 30, 30, 255)), ('3', 'spec', (8, 8, 8, 255))):
            if slot not in tex:
                path = f'texture/{slug}/layer_blend_neutral_{semantic}.rpak'
                if not (assets/path).with_suffix('.dds').exists():
                    save_mips(Image.new('RGBA', (4, 4), colour), (assets/path).with_suffix('.dds'))
                files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); tex[slot] = path
                tex.setdefault(str(int(slot)+23), path)
        for slot in ('0', '1', '2', '3', '22', '23'):
            if slot not in tex:
                raise ValueError(f'{name} lacks native bm slot {slot}')
        values, _ = source.constants(name)
        uber = bytearray(uber0); cuber = bytearray(cuber0)
        for buffer in (uber, cuber):
            struct.pack_into('<f', buffer, 92, row['ramp'])
            struct.pack_into('<3f', buffer, 96, 1, 1, 1)
        mpath = 'material/'+r['name']+'_wld.rpak'; cpath = 'material/'+r['name']+'_colpass_wld.rpak'
        for destination, spec, buffer in ((cpath, cspec0, cuber), (mpath, spec0, uber)):
            new = dict(spec, name=r['name']+('_colpass' if destination == cpath else ''), width=1024, height=1024,
                       shaderSet=shaderset, surfaceProp='default')
            new['blendStates'] = spec['blendStates']+['0x0']*4
            new['$textures'] = dict(tex)
            new['$colpassMaterial'] = cpath if destination == mpath else '0x0'
            target = (assets/destination).with_suffix('.json'); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(new, indent=2)); target.with_suffix('.uber').write_bytes(buffer)
            files[destination] = dict(_type='matl', _path=destination)
        r.update(textures=tex, native_layer_blend=dict(shader='Coliseum wld bm', ramp=row['ramp'],
                 blend_input='z-up normal ramp' if row['zup'] else 'source vertex alpha'))
        report[name] = r['native_layer_blend']
    manifest['files'] = sorted(files.values(), key=lambda f: {'shds': 0, 'txtr': 1}.get(f['_type'], 2))
    write(mats/'build.json', manifest); write(mats/'mapping.json', mapping)
    run = subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(mats/'build.json')], capture_output=True, text=True)
    (project/'material-build.log').write_text(run.stdout+run.stderr)
    if run.returncode or 'ERROR' in run.stdout+run.stderr:
        raise ValueError('RePak failed; see '+str(project/'material-build.log'))
    from build_preview_stbsp import build
    build(out, mats, CONFIG[ident]['target'], slug+'_world')
    write(project/'blend-result.json', dict(materials=report))
    print('Native blend materials', len(report), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['patch', 'materials']); p.add_argument('ident', choices=sorted(CONFIG))
    a = p.parse_args(); dict(patch=patch, materials=materials)[a.action](a.ident)
