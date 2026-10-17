"""Phase Runner 1.7.0: Apex two-layer blending and world-projected ground UVs.

Phase Runner bound only layer 1 of its Apex blend materials (snow/moss rocks,
moss/dirt ground) and its world-projected ground tiled 3-8x too coarsely.
This applies the Party Crasher 0.5.1/0.6.0 repairs (apply_layer_blends.py,
repair_party_surfaces.py) to Phase Runner's separate pack layout:

* survey: per blend material, the UV source of each layer (mesh UV or world
  position, c_uvN slot), the blend ramp and whether the blend input is vertex
  alpha or the z-up normal term, from the source pixel shaders.
* patch: writes the Apex blend input into vertex alpha (source BSP vertex
  colour alpha matched by position, or the z-up ramp from the normal) and,
  for materials whose layers are all projected from world position with one
  c_uvN slot, rewrites the mesh UV to that projection
  uv = (x, -y) . RotScale + Translate in source coordinates.
* materials: builds `phase_runner_blend.rpak` with native Coliseum wld bm
  materials (embedded shaderset) under world/phase_runner_blend/ and points
  the BSP texture data of those surfaces at them.

Geometry, indices, collision, lightmaps and every other material are unchanged.
"""
import argparse
import collections
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT/'northstar/PhaseRunner'
MAP = PACKAGE/'mod/maps/mp_phase_runner.bsp'
WORK = Path('D:/Games/ApexToTitanfallWork/legacy-work/phase-runner')
PROJECT = WORK/'blend'
BACKUP = WORK/'before-1.7.0'
SOURCE_PAK = ROOT/'inputs/decompressed/mp_rr_arena_phase_runner.rpak'
SOURCE_BSP = ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp'
OFFSET = np.asarray([-26000., -19000., 0.])  # source + OFFSET = port
EXPORTS = [ROOT/'tools/legion/exported_files/materials', ROOT/'output/phase-runner/legion-assets/exported_files/materials',
           ROOT/'output/phase-runner/common-assets/exported_files/materials', ROOT/'tools/composite-legion/exported_files/materials']
PAK = 'phase_runner_blend'
VERSION = '1.7.1'
SLUG = 'phase_runner_blend'


def write(path, value):
    path = Path(path); temp = path.with_suffix(path.suffix+'.new')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8'); os.replace(temp, path)


def export_dir(name):
    for root in EXPORTS:
        d = root/name
        if d.is_dir() and any(d.glob('*.dds')):
            return d
    return None


def native_names(l):
    out = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        out.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace(chr(92), '/'))
    return out


def counts():
    import analyse_visibility as vis
    t, m, n = vis.render_triangles(MAP); c = collections.Counter()
    for i, k in zip(*np.unique(m, return_counts=True)):
        c[n[i]] += int(k)
    return c


def survey():
    from apex_material_constants import ApexMaterials
    from classify_world_uv import albedo_source
    from inspect_apex_shader import disassemble
    from layer_blend_survey import texture_slots
    PROJECT.mkdir(parents=True, exist_ok=True); cache = PROJECT/'shader-inspection'; cache.mkdir(exist_ok=True)
    src = ApexMaterials(SOURCE_PAK); lower = {k.lower(): k for k in src.materials}; result = {}
    for name, count in counts().items():
        d = export_dir(name); key = lower.get(name.lower())
        if d is None or key is None:
            continue
        files = {p.name.lower() for p in d.iterdir()}
        has2 = any('albedo2texture' in f for f in files)
        path = cache/(key+'-ps.txt')
        if not path.exists():
            disassemble(src, key, cache)
        ps = path.read_text(errors='replace'); slots = texture_slots(ps); values, _ = src.constants(key)
        row = dict(triangles=count, source=key, export=str(d), two_layer=has2,
                   ramp=values.get('c_layerBlendRamp', [None])[0])
        for tex in ('albedoTexture', 'albedo2Texture', 'layerBlendTexture'):
            if tex not in slots:
                row[tex] = None; continue
            info = albedo_source(ps, slots[tex]); n = info.get('slot')
            if n:
                info.update(rot_x=values[f'c_uv{n}RotScaleX'], rot_y=values[f'c_uv{n}RotScaleY'], translate=values[f'c_uv{n}Translate'])
            row[tex] = info
        body = ps[ps.find('dcl_temps'):]
        row['zup'] = bool(re.search(r'mad r\d+\.\w, v\d+\.z, r\d+\.\w, -cb0\[21\]\.w', body))
        row['zup_params'] = dict(min=values.get('c_zUpBlendingMinAngleCos'), max=values.get('c_zUpBlendingMaxAngleCos'),
                                 scale=values.get('c_zUpBlendingVertexAlphaAndL0_albedoTint', [None])[0])
        if has2 or (row['albedoTexture'] or {}).get('kind') == 'world':
            result[name] = row
    write(PROJECT/'survey.json', result)
    for n, r in sorted(result.items(), key=lambda kv: -kv[1]['triangles']):
        f = lambda i: None if not i else (i['kind'], i.get('slot'), [round(v, 5) for v in i.get('rot_x', [])])
        print(r['triangles'], n, 'A', f(r['albedoTexture']), 'A2', f(r['albedo2Texture']), 'M', f(r['layerBlendTexture']),
              'zup' if r['zup'] else '', r['ramp'], flush=True)
    return result


SKIP = ('_b2t', 'transparent', 'decal')
# Native captures showed regressions for these; they keep their single-layer material.
EXCLUDE = {'asphalt08_cracked_bm'}
MATCH = .5  # prop SMDs were rebuilt from QC; positions agree to well under a unit


def chosen():
    """Two-layer materials converted to the native bm shader, and world-UV rewrites."""
    survey = json.loads((PROJECT/'survey.json').read_text()); blend, uv = {}, {}
    for name, r in survey.items():
        a = r['albedoTexture']
        # Rewrite the mesh UV only when layer 1 itself is world projected (not foliage cards or decals).
        if a and a['kind'] == 'world' and not name.startswith(('icelandic_grass', 'flowers_', 'cement_')):
            uv[name] = a
        if not r['two_layer'] or any(k in name for k in SKIP) or r['ramp'] is None or name in EXCLUDE:
            continue
        have = {p.name.lower() for p in Path(r['export']).iterdir()}
        if name+'_albedo2texture.dds' in have and name+'_layerblendtexture.dds' in have:
            blend[name] = r
    return blend, uv


def snapshot():
    if BACKUP.exists():
        return
    BACKUP.mkdir(parents=True)
    for rel in ('mod/maps/mp_phase_runner.bsp', 'mod/maps/mp_phase_runner.stbsp', 'paks/rpak.json', 'mod.json'):
        (BACKUP/rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(PACKAGE/rel, BACKUP/rel)


def source_alpha(names):
    """Source positions (port frame) and blend alpha for world and prop vertices per material."""
    sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    from bsp_tool.branches.respawn.titanfall import MeshFlags
    from read_vg_static import load
    from stage_prop_geometry import rotation
    from plan_arena_fill import model_index
    pos = {n: [] for n in names}; val = {n: [] for n in names}; lower = {n.lower(): n for n in names}
    geo = bsp_tool.load_bsp(str(SOURCE_BSP)); geo = getattr(geo, 'external', geo)
    for mesh in geo.MESHES:
        sort = geo.MATERIAL_SORTS[mesh.material_sort]
        name = lower.get(geo.texture_data_surface_name(sort.texture_data).replace(chr(92), '/').rsplit('/', 1)[-1].lower())
        if name is None:
            continue
        records = getattr(geo, (mesh.flags & MeshFlags.MASK_VERTEX).name)
        for index in geo.MESH_INDICES[mesh.first_mesh_index:mesh.first_mesh_index+mesh.num_triangles*3]:
            v = records[index+sort.vertex_offset]
            pos[name].append(np.asarray(list(geo.VERTICES[v.position_index]))+OFFSET)
            val[name].append(np.array([v.negative_one], '<i4').view('u1')[3]/255)
    world = {n: len(pos[n]) for n in names}
    props = json.loads(Path('D:/Games/ApexToTitanfallWork/project-storage/output/phase-runner/static-props.json').read_text())
    index = model_index(); cache = {}
    for p in props:
        stem = Path(p['model']).stem.lower()
        if stem not in index:
            continue
        if stem not in cache:
            cache[stem] = []
            try:
                levels = struct.unpack_from('<18Q', (index[stem]/(index[stem].name+'.vg')).read_bytes(), 16)[13]
                for lod in range(min(levels, 6)):
                    cache[stem].append(load(index[stem], lod, True))
            except Exception:
                pass
        matrix = np.asarray(rotation(p['angles']))
        for sections, slots, skins in cache[stem]:
            skin = skins[min(p.get('skin', 0), len(skins)-1)]
            for s, slot in zip(sections, slots):
                name = lower.get(skin[slot].lower())
                if not len(s) or name is None:
                    continue
                a = np.asarray(s, 'f8').reshape(-1, 12)
                pos[name].extend(a[:, :3]@matrix.T*p.get('scale', 1)+p['origin']); val[name].extend(a[:, 11]/255)
    return {n: (np.asarray(pos[n]).reshape(-1, 3), np.asarray(val[n])) for n in names}, world


def project_uv(info, port_positions):
    p = port_positions-OFFSET  # source frame
    xy = np.stack((p[:, 0], -p[:, 1]), -1)
    return np.stack((xy@np.asarray(info['rot_x'])+info['translate'][0], xy@np.asarray(info['rot_y'])+info['translate'][1]), -1)


def patch():
    snapshot(); PROJECT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from scipy.spatial import cKDTree
    blend, uvfix = chosen()
    work = WORK/'mp_phase_runner.bsp'; shutil.copy2(BACKUP/'mod/maps/mp_phase_runner.bsp', work)
    alpha_names = [n for n, r in blend.items() if not r['zup']]
    sources, world = source_alpha(alpha_names)
    trees = {n: cKDTree(sources[n][0]) for n in alpha_names if len(sources[n][0])}
    l = read_lumps(work, range(128)); names = [n.rsplit('/', 1)[-1] for n in native_names(l)]
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); records = np.frombuffer(l[0x49], DT).copy()
    positions = np.frombuffer(l[3], '<f4').reshape(-1, 3).astype('f8'); normals = np.frombuffer(l[0x1e], '<f4').reshape(-1, 3).astype('f8')
    report = {n: dict(corners=0, matched=0, mean_alpha=0., world_source_vertices=world.get(n, 0)) for n in blend}
    uvreport = collections.Counter()
    for mesh in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        sort = sorts[mesh[-2]]; name = names[sort[0]]
        if name not in blend and name not in uvfix:
            continue
        ix = np.unique(np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('u4')+sort[-1])
        if name in uvfix:
            records['uv'][ix] = project_uv(uvfix[name], positions[records['pi'][ix]]).astype('f4'); uvreport[name] += len(ix)
        if name not in blend:
            continue
        row = blend[name]
        if row['zup']:
            n = normals[records['ni'][ix]]; n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            lo, hi = row['zup_params']['max'][0], row['zup_params']['min'][0]
            a = np.clip((n[:, 2]-lo)/(hi-lo), 0, 1)*row['zup_params']['scale']; matched = len(ix)
        elif name in trees:
            d, j = trees[name].query(positions[records['pi'][ix]]); ok = d < MATCH
            a = np.where(ok, sources[name][1][j], 0.); matched = int(ok.sum())
        else:
            a = np.zeros(len(ix)); matched = 0
        records['color'][ix, 3] = np.rint(np.clip(a, 0, 1)*255).astype('u1')
        r = report[name]; r['mean_alpha'] += float(a.sum()); r['corners'] += len(ix); r['matched'] += matched
    for r in report.values():
        r['mean_alpha'] = round(r['mean_alpha']/max(r['corners'], 1), 4)
    # Materials without matched source alpha keep their single-layer shader.
    unmatched = sorted(n for n, r in report.items() if r['corners'] and r['matched'] < .9*r['corners'])
    temp = work.with_suffix('.blend.bsp'); compact(work, temp, {0x49: bytearray(records.tobytes())}); os.replace(temp, work)
    write(PROJECT/'patch.json', dict(materials=report, zup=[n for n, r in blend.items() if r['zup']], excluded_unmatched=unmatched,
                                     uv_rewritten_corners=dict(uvreport), match_distance=MATCH))
    for n, r in sorted(report.items(), key=lambda kv: -kv[1]['corners']):
        print(f"{n:55s} corners {r['corners']:7d} matched {r['matched']/max(r['corners'], 1):.2f} alpha {r['mean_alpha']}",
              'zup' if blend[n]['zup'] else '', flush=True)
    print('UV rewritten', dict(uvreport), 'excluded', unmatched, flush=True)


def materials():
    from extract_native_material import NativePak
    from bake_terrain_transitions import save_mips
    from apply_layer_blends import convert, embed_shaderset, NATIVE_BM, NATIVE_BM_COLPASS
    from PIL import Image
    blend, _ = chosen(); excluded = set(json.loads((PROJECT/'patch.json').read_text())['excluded_unmatched'])
    mats = PROJECT/'materials'; assets = mats/'assets'
    if mats.exists():
        shutil.rmtree(mats)
    assets.mkdir(parents=True)
    coliseum = NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
    spec0, uber0 = coliseum.material(next(a for a in coliseum.assets if a['guid'] == NATIVE_BM))
    cspec0, cuber0 = coliseum.material(next(a for a in coliseum.assets if a['guid'] == NATIVE_BM_COLPASS))
    files = {}; shaderset = embed_shaderset(SLUG, assets); files[shaderset] = dict(_type='shds', _path=shaderset)
    neutral = {}
    for semantic, colour in (('normal', (128, 128, 255, 255)), ('gloss', (30, 30, 30, 255)), ('spec', (8, 8, 8, 255))):
        path = f'texture/{SLUG}/neutral_{semantic}.rpak'; (assets/path).parent.mkdir(parents=True, exist_ok=True); save_mips(Image.new('RGBA', (4, 4), colour), (assets/path).with_suffix('.dds'))
        files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); neutral[semantic] = path
    rebound = {}
    for name, row in blend.items():
        if name in excluded:
            continue
        lowered = {p.name.lower(): p for p in Path(row['export']).iterdir()}; tex = {}
        for slot, semantic, fallback in (('0', 'albedo', None), ('1', 'normal', 'normal'), ('2', 'gloss', 'gloss'), ('3', 'spec', 'spec'),
                                         ('22', 'layerBlend', None), ('23', 'albedo2', None), ('24', 'normal2', '1'),
                                         ('25', 'gloss2', '2'), ('26', 'spec2', '3')):
            src = lowered.get(f'{name}_{semantic}texture.dds'.lower())
            if src is not None:
                path = f'texture/{SLUG}/{name}_{semantic}.rpak'; convert(src, (assets/path).with_suffix('.dds'))
                files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); tex[slot] = path
            elif fallback in neutral:
                tex[slot] = neutral[fallback]
            elif fallback:
                tex[slot] = tex[fallback]
            else:
                raise ValueError(f'{name} lacks {semantic}')
        tex['15'] = neutral['normal']
        material = f'world/{SLUG}/{name}'
        uber = bytearray(uber0); cuber = bytearray(cuber0)
        for buffer in (uber, cuber):
            struct.pack_into('<f', buffer, 92, row['ramp']); struct.pack_into('<3f', buffer, 96, 1, 1, 1)
        mpath = 'material/'+material+'_wld.rpak'; cpath = 'material/'+material+'_colpass_wld.rpak'
        for destination, spec, buffer in ((cpath, cspec0, cuber), (mpath, spec0, uber)):
            new = dict(spec, name=material+('_colpass' if destination == cpath else ''), width=1024, height=1024,
                       shaderSet=shaderset, surfaceProp='default')
            new['blendStates'] = spec['blendStates']+['0x0']*4; new['$textures'] = dict(tex)
            new['$colpassMaterial'] = cpath if destination == mpath else '0x0'
            target = (assets/destination).with_suffix('.json'); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(new, indent=2)); target.with_suffix('.uber').write_bytes(buffer)
            files[destination] = dict(_type='matl', _path=destination)
        rebound[name] = material
    decals = build_decals(assets, files, neutral)
    rebound.update(decals)
    manifest = dict(version=7, name=PAK, keepDevOnly=True, assetsDir=str(assets), outputDir=str(mats/'build'), compressLevel=0,
                    hasDynamicLibrary=False, files=sorted(files.values(), key=lambda f: {'shds': 0, 'txtr': 1}.get(f['_type'], 2)))
    write(mats/'build.json', manifest)
    run = subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(mats/'build.json')], capture_output=True, text=True)
    (PROJECT/'material-build.log').write_text(run.stdout+run.stderr)
    if run.returncode or 'ERROR' in run.stdout+run.stderr:
        raise ValueError('RePak failed; see '+str(PROJECT/'material-build.log'))
    # Point the BSP texture data of those surfaces at the native blend materials.
    work = WORK/'mp_phase_runner.bsp'; l = read_lumps(work, (2, 0x2b, 0x2c, 0x50, 0x52)); full = native_names(l)
    strings = bytearray(l[0x2b]); table = bytearray(l[0x2c]); tex = bytearray(l[2]); meshes = bytearray(l[0x50]); changed = 0
    alpha_tex = set()
    for ti, nm in enumerate(full):
        base = nm.rsplit('/', 1)[-1]
        if base in rebound and nm.startswith('world/phase_runner_preview/'):
            struct.pack_into('<I', tex, ti*36+12, len(table)//4); table.extend(struct.pack('<I', len(strings)))
            strings.extend(rebound[base].replace('/', chr(92)).encode()+b'\0'); changed += 1
            if base in decals:
                # Alpha-blended decal: texture data and mesh translucency flags (as the road decal in 1.x).
                struct.pack_into('<I', tex, ti*36+32, struct.unpack_from('<I', tex, ti*36+32)[0] | 0x10); alpha_tex.add(ti)
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); decal_meshes = 0
    for at in range(0, len(meshes), 28):
        if sorts[struct.unpack_from('<H', meshes, at+22)[0]][0] in alpha_tex:
            struct.pack_into('<I', meshes, at+24, struct.unpack_from('<I', meshes, at+24)[0] | 0x10); decal_meshes += 1
    temp = work.with_suffix('.mat.bsp'); compact(work, temp, {2: tex, 0x2b: strings, 0x2c: table, 0x50: meshes}); os.replace(temp, work)
    (WORK/'source-build.json').write_text(json.dumps(dict(map='mp_phase_runner')))
    from build_preview_stbsp import build
    build(WORK, mats, 'mp_phase_runner', PAK, extra_paks=list((PACKAGE/'paks').glob('*.rpak'))+[ROOT/'inputs/tf2-rpak-work/common.raw.rpak'])
    write(PROJECT/'materials.json', dict(native_blend_materials=rebound, texture_data_rebound=changed,
                                         pak_bytes=(mats/'build'/(PAK+'.rpak')).stat().st_size))
    print('Native blend materials', len(rebound), 'texture data rebound', changed, flush=True)


DECALS = ('sign_warning_yellow', 'cement_stripes_decals_vert', 's2s_bolt_decals_03', 's2s_boltdecals_02', 's2s_decals_01')
DECAL_MATERIAL = 0x92b5ba61a3bf2e7a  # Homestead alpha decal (build_art_supports.py road decal)
# Source vertex colour of the stripe decal (Apex tints it per vertex; baked into the albedo here).
DECAL_TINT = {'cement_stripes_decals_vert': (213, 190, 74)}
# sign_warning_yellow only stands in for the unrecovered Apex 'signage_building_02' lettering
# (repair_dev_materials.py); its CCTV texture is wrong everywhere, so it is drawn fully transparent.
DECAL_HIDDEN = {'sign_warning_yellow'}


def build_decals(assets, files, neutral):
    """Opaque coplanar source decals z-fought the floor (base 'CAUTION LOADING AREA'): alpha-blended
    native decal materials with decal raster depth bias and an opacity map from the source."""
    import io
    from PIL import Image
    from extract_native_material import NativePak
    from bake_terrain_transitions import save_mips
    from apply_layer_blends import convert
    homestead = NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak')
    spec, uber = homestead.material(next(a for a in homestead.assets if a['guid'] == DECAL_MATERIAL))
    # The alpha-decal shader set ships in the art-supports pack (the glass-console one is a glass shader).
    shader = next(a['guid'] for a in NativePak(PACKAGE/'paks/phase_runner_art_supports.rpak').assets if a['type'] == 'shds')
    def conv(src, dest):
        try:
            convert(src, dest)
        except (KeyError, ValueError):
            # Uncompressed legacy DDS (e.g. an L8 opacity map): decode and re-encode.
            dest.parent.mkdir(parents=True, exist_ok=True); im = Image.open(src).convert('RGBA')
            if max(im.size) > 1024:
                im = im.resize((min(1024, im.width), min(1024, im.height)))
            save_mips(im, dest)
    out = {}
    for name in DECALS:
        d = ROOT/'tools/legion/exported_files/materials'/name; tex = {}
        for slot, semantic in (('0', 'albedo'), ('1', 'normal'), ('2', 'gloss')):
            src = d/f'{name}_{semantic}Texture.dds'
            if semantic == 'albedo' and name in DECAL_TINT:
                raw = bytearray(src.read_bytes())
                if raw[84:88] == b'DX10' and struct.unpack_from('<I', raw, 128)[0] in (72, 75, 78, 99):
                    struct.pack_into('<I', raw, 128, struct.unpack_from('<I', raw, 128)[0]-1)
                im = np.asarray(Image.open(io.BytesIO(raw)).convert('RGBA')).astype('f4')
                im[:, :, :3] *= np.asarray(DECAL_TINT[name], 'f4')/255
                path = f'texture/{SLUG}/{name}_decal_albedo.rpak'; dest_ = (assets/path).with_suffix('.dds'); dest_.parent.mkdir(parents=True, exist_ok=True)
                save_mips(Image.fromarray(np.clip(im, 0, 255).astype('u1')), dest_)
                files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); tex[slot] = path
            elif src.exists():
                path = f'texture/{SLUG}/{name}_decal_{semantic}.rpak'; conv(src, (assets/path).with_suffix('.dds'))
                files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True}); tex[slot] = path
            else:
                tex[slot] = neutral[semantic]
        black = f'texture/{SLUG}/decal_black_spec.rpak'
        if black not in files:
            save_mips(Image.new('RGBA', (4, 4), (0, 0, 0, 255)), (assets/black).with_suffix('.dds'))
            files[black] = dict(_type='txtr', _path=black, **{'$disableStreaming': True})
        tex['3'] = black
        opacity = f'texture/{SLUG}/{name}_decal_opacity.rpak'; dest = (assets/opacity).with_suffix('.dds')
        source = d/f'{name}_opacityMultiplyTexture.dds'
        if name in DECAL_HIDDEN:
            dest.parent.mkdir(parents=True, exist_ok=True); save_mips(Image.new('RGBA', (4, 4), (0, 0, 0, 255)), dest)
        elif source.exists():
            conv(source, dest)
        else:
            raw = bytearray((d/f'{name}_albedoTexture.dds').read_bytes())
            if raw[84:88] == b'DX10' and struct.unpack_from('<I', raw, 128)[0] in (72, 75, 78, 99):
                struct.pack_into('<I', raw, 128, struct.unpack_from('<I', raw, 128)[0]-1)
            a = Image.open(io.BytesIO(raw)).convert('RGBA').getchannel('A')
            save_mips(Image.merge('RGBA', (a, a, a, Image.new('L', a.size, 255))), dest)
        files[opacity] = dict(_type='txtr', _path=opacity, **{'$disableStreaming': True}); tex['13'] = opacity
        world = f'world/{SLUG}/{name}_alpha'; path = 'material/'+world+'_wld.rpak'
        new = dict(spec, name=world, width=1024, height=1024, shaderSet=hex(shader), rasterizerFlags='0x16', surfaceProp='default',
                   blendStates=spec['blendStates']+['0x0']*4)
        new['$textures'] = tex
        buf = bytearray(uber); struct.pack_into('<6f', buf, 0, 1, 0, -0., 1, 0, 0); struct.pack_into('<f', buf, 108, 1.)
        target = (assets/path).with_suffix('.json'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(new, indent=2)); target.with_suffix('.uber').write_bytes(buf)
        files[path] = dict(_type='matl', _path=path); out[name] = world
    return out


def stage():
    from package_player_mods import digest
    candidate = WORK/'candidate'/'PhaseRunner'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(PACKAGE, candidate)
    for rel, src in (('mod/maps/mp_phase_runner.bsp', WORK/'mp_phase_runner.bsp'), ('mod/maps/mp_phase_runner.stbsp', WORK/'mp_phase_runner.stbsp'),
                     (f'paks/{PAK}.rpak', PROJECT/'materials/build'/(PAK+'.rpak'))):
        shutil.copy2(src, candidate/rel)
    rp = json.loads((candidate/'paks/rpak.json').read_text()); rp['Postload'][PAK+'.rpak'] = 'mp_coliseum.rpak'
    (candidate/'paks/rpak.json').write_text(json.dumps(rp, indent=2))
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = VERSION; (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    print('Staged', candidate, digest(candidate/'mod/maps/mp_phase_runner.bsp')[:12], flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['survey', 'patch', 'materials', 'stage'])
    dict(survey=survey, patch=patch, materials=materials, stage=stage)[p.parse_args().action]()
