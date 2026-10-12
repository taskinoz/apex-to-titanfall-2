"""Recover scenery up to a measured world-index budget without using entity slots.

Work is isolated under output/arena-fill. Existing player packages are inputs;
the builder never edits them. Source geometry, skins, UVs and colliders are
retained. Old collision exclusions, lightmaps, probes and game entities remain.
"""
import argparse
import collections
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

from plan_arena_fill import CONFIG, OUT, ROOT, model_index, native_materials, source_inventory
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
import numpy as np
from PIL import Image
from read_vg_static import load
from read_prop_physics import read_phy, read_bvh
from stage_prop_geometry import rotation
from package_player_mods import digest, runtime_files
from repair_preview_index_padding import read_lumps, validate_index_padding
from compact_preview_bsp import compact
from optimize_portalfree_render import DT, material_name
from spatial_preview_meshes import partition
from apply_baked_lighting import tangents
from build_center_detail import active
from native_triangle_collision import encode
from repair_tunnel_passages import remap_grid
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY
from build_phase_runner_catwalks import mesh_faces
import build_phase_runner_catwalks as lighting
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from build_phase_runner_presentation import guid
from build_phase_runner_firs import save_leaf_mips
from bake_terrain_transitions import save_mips
from restore_banner_display_textures import image_dds

TARGET = .971
MAXIMUM = .975
MAX_STATIC_BATCHES = 512
VERSIONS = {'phase-runner': '1.6.0', 'drop-off': '0.10.0'}
LIDS = (0, 1, 2, 3, 5, 0xe, 0x1e, 0x2b, 0x2c, 0x42, 0x44, 0x45,
        0x49, 0x4f, 0x50, 0x51, 0x52, 0x53, 0x55, 0x56, 0x57, 0x58,
        0x59, 0x5a, 0x5c, 0x60, 0x61, 0x62, 0x64, 0x69, 0x77, 0x78, 0x79, 0x7b,
        0x7c, 0x7e, 0x7f, 0x65, 0x66, 0x67, 0x68)


def source_path(ident):
    c = CONFIG[ident]
    return ROOT/'northstar'/c['package']/'mod/maps'/(c['map']+'.bsp')


def current_scene(lumps):
    triangles, masks = [], []
    for mesh, row, raw, vi, tri in mesh_faces(lumps):
        name = material_name(lumps, struct.unpack_from('<h', lumps[0x52], row[-2]*12)[0]).lower()
        triangles.append(tri)
        casts = not any(word in name for word in ('sky', 'leaf', 'leaves', 'foliage', 'grass', 'flower', 'decal', 'start_barrier'))
        casts &= not bool(row[-1] & 0x10)
        masks.append(np.full(len(tri), casts, 'u1'))
    return np.concatenate(triangles), np.concatenate(masks)


class Ground:
    """Vertical support sampling against actual retained render surfaces."""
    def __init__(self, triangles):
        normal = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
        area = np.linalg.norm(normal, axis=1)
        keep = (area > .01) & (np.abs(normal[:, 2]) > area*.3)
        self.tri = triangles[keep]
        self.cells = collections.defaultdict(list)
        low, high = self.tri[:, :, :2].min(1), self.tri[:, :, :2].max(1)
        for i, (lo, hi) in enumerate(zip(np.floor(low/512).astype(int), np.floor(high/512).astype(int))):
            if hi[0]-lo[0] > 40 or hi[1]-lo[1] > 40: continue
            for x in range(lo[0], hi[0]+1):
                for y in range(lo[1], hi[1]+1): self.cells[x, y].append(i)

    def height(self, point):
        ids = self.cells.get(tuple(np.floor(np.asarray(point[:2])/512).astype(int)), [])
        if not ids: return None
        t = self.tri[ids]; a = t[:, 1, :2]-t[:, 0, :2]; b = t[:, 2, :2]-t[:, 0, :2]
        p = np.asarray(point[:2])-t[:, 0, :2]
        determinant = a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            u = (p[:, 0]*b[:, 1]-p[:, 1]*b[:, 0])/determinant
            v = (a[:, 0]*p[:, 1]-a[:, 1]*p[:, 0])/determinant
        z = t[:, 0, 2]+u*(t[:, 1, 2]-t[:, 0, 2])+v*(t[:, 2, 2]-t[:, 0, 2])
        good = (u >= -.001) & (v >= -.001) & (u+v <= 1.001) & np.isfinite(z) & (np.abs(z-point[2]) < 96)
        if not good.any(): return None
        heights = z[good]
        return float(heights[np.argmin(np.abs(heights-point[2]))])


def protected_spawns(lumps):
    sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
    from bsp_tool.branches.shared import Entities
    result = []
    for ent in Entities.from_bytes(lumps[0]):
        cls = ent.get('classname', '')
        if 'spawnpoint' not in cls and cls != 'info_hardpoint': continue
        if 'origin' not in ent: continue
        p = np.asarray([float(v) for v in ent['origin'].split()])
        titan = 'titan' in cls
        extent = np.asarray([110, 110, 420] if titan else [40, 40, 100])
        result.append((p-np.asarray([extent[0], extent[1], 8]), p+extent))
    return result


def material_folder(name):
    for root in (ROOT/'tools/composite-legion/exported_files/materials', ROOT/'tools/legion/exported_files/materials',
                 ROOT/'output/phase-runner/shared-assets/materials', ROOT/'output/phase-runner/common-assets/exported_files/materials'):
        folder = root/name
        if (folder/(name+'_albedoTexture.dds')).exists(): return folder
    return None


def collider(folder, solid, sections):
    if solid not in (2, 6, 7): return np.empty((0, 3, 3), '<f4'), 'Source non-solid'
    base = folder/folder.name
    pieces = None
    if base.with_suffix('.phy').exists():
        pieces = read_phy(base.with_suffix('.phy')); method = 'Source IRPS surface'
    else:
        try:
            pieces, _ = read_bvh(base.with_suffix('.rmdl')); method = 'Source embedded BVH surface'
        except (ValueError, struct.error): pass
    faces = [[f[0], f[i], f[i+1]] for piece in (pieces or []) for f in piece for i in range(1, len(f)-1)]
    if faces: return np.asarray(faces, '<f4'), method
    # A source solid without exported physics uses the original LOD0 surfaces,
    # not a guessed box or the lower rendering LOD. Foliage stays non-solid.
    raw, slots, skins = load(folder, 0)
    faces = [np.asarray(s, '<f4')[:, :, :3] for s in raw if len(s)]
    if not faces or sum(len(f) for f in faces) > 25000: raise ValueError('No bounded source collision fallback')
    return np.concatenate(faces), 'Source LOD0 mesh surface fallback'


def distributed(rows):
    cells = collections.defaultdict(list)
    for p in sorted(rows, key=lambda p:(p['index']*2654435761)&0xffffffff):
        cells[tuple(math.floor(v/1024) for v in p['origin'][:2])].append(p)
    order = sorted(cells, key=lambda k:(k[0]*73856093 ^ k[1]*19349663)&0xffffffff)
    for i in range(max(map(len, cells.values()), default=0)):
        for key in order:
            if i < len(cells[key]): yield cells[key][i]


def prepare(ident):
    config = CONFIG[ident]; work = OUT/ident; work.mkdir(parents=True, exist_ok=True)
    base = ROOT/'northstar'/config['package']
    assert json.loads((base/'mod.json').read_text())['Version'] == config['version']
    snapshot = work/'baseline'
    if not snapshot.exists():
        for path in runtime_files(base):
            dst = snapshot/path.relative_to(base); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dst)
        (work/'baseline-hashes.json').write_text(json.dumps({p.relative_to(base).as_posix():digest(p) for p in runtime_files(base)}, indent=2))
    assert digest(source_path(ident)) == digest(snapshot/'mod/maps'/(config['map']+'.bsp'))
    lumps = read_lumps(source_path(ident), LIDS)
    scene, cast = current_scene(lumps); ground = Ground(scene); protected = protected_spawns(lumps)
    candidates, present = source_inventory(ident); folders = model_index(); native = native_materials(ident)
    audit_rows = {r['model']:r for r in json.loads((OUT/(ident+'-audit.json')).read_text())['models']}
    cache = {}; rows = []; skipped = []; geometry = []; matnames = []; foliage_flags = []; physical = []; used = 0
    triangle_budget = int((WORLD_INDEX_CAPACITY*TARGET-audit(source_path(ident))['native_padded_indices'])/3)-650
    groups = collections.defaultdict(list)
    for p in candidates:
        if abs(p['origin'][0]) > (7200 if ident=='phase-runner' else 5000): continue
        if not (-6500 < p['origin'][1] < 7400 and -2000 < p['origin'][2] < 2800): continue
        if ident=='drop-off' and not (abs(p['origin'][0])<3700 and -200<p['origin'][1]<7100 and -256<p['origin'][2]<2200): continue
        name = Path(p['model']).stem.lower()
        if any(w in name for w in ('test_', 'ceiling_vent', 'godray', 'lobby', 'barrier', 'screen', 'monitor', 'marvin', 'puddle', 'decal')): continue
        if ident=='phase-runner':
            if '/foliage/' not in p['model'] and name not in ('power_gen1','power_cell_64','power_cell_64_single_01','icelandic_snow_rockcluster_02','rock_lava_cluster_desertlands_03'): continue
            if 'tree_' in name or 'moss_green_hanging' in name: continue
        elif '/foliage/' in p['model'] or any(w in name for w in ('wire_cluster', 'wires_hanging', 'wire_ceiling')): continue
        r = audit_rows.get(p['model'], {})
        if not r.get('triangles_each'): continue
        if any(any(w in m for w in ('godray','ambient_occlusion','start_barrier','atmosphere','glow_overlay','animation')) for m in r['materials']): continue
        if any(material_folder(m) is None for m in r['new_materials']): continue
        groups[name].append(p)
    if ident=='phase-runner':
        weights = [('power_gen1', .10), ('power_cell_64', .035), ('icelandic_snow_rockcluster_02', .06),
                   ('flowers_ground_01', .09), ('icelandic_moss_grass_01', .13), ('icelandic_ground_plant_01', .10),
                   ('foliage_ground_plants', .10), ('plant_icelandic_02', .055),
                   ('ground_plant_desertlands_01_group_01', .33)]
        sequence = [(name, min(triangle_budget, int(triangle_budget*fraction))) for name,fraction in weights]
        sequence += [('ground_plant_desertlands_01_group_01', triangle_budget), ('foliage_ground_plants', triangle_budget)]
    else:
        def rank(name):
            if any(w in name for w in ('desk','chair','container','crate','oxygen','power','rack','fence','bracket','clamp','planter')): return 0
            if any(w in name for w in ('pipe','panel','conduit','fusebox','light','fan')): return 1
            if 'wire' in name: return 3
            if 'ceiling' in name: return 4
            return 2
        sequence = [(name, triangle_budget) for name in sorted(groups, key=lambda n:(rank(n), n))]
    selected = set()
    for name, allowance in sequence:
        group_used = 0
        for p in distributed(groups.get(name, [])):
            if p['index'] in selected: continue
            try:
                folder = folders[name]
                if name not in cache:
                    levels = struct.unpack_from('<18Q', (folder/(folder.name+'.vg')).read_bytes(), 16)[13]
                    lod = min(levels-1, 2 if '/foliage/' in p['model'] else 3)
                    parts, slots, skins = load(folder, lod, with_colors=True)
                    cache[name] = [np.asarray(s, '<f4') for s in parts], slots, skins, lod
                parts, slots, skins, lod = cache[name]
                skin = skins[p['skin']]; solid = p.get('solid_mode', p.get('solid', 0))
                is_foliage = '/foliage/' in p['model']
                origin = np.asarray(p['origin'], 'f4'); original_origin = origin.copy()
                matrix = np.asarray(rotation(p['angles']), 'f4')
                if is_foliage:
                    support = ground.height(origin)
                    if support is None or abs(support-origin[2]) > 48: raise ValueError('No nearby retained ground support')
                    raw_points=np.concatenate([s[:,:,:3].reshape(-1,3) for s in parts if len(s)])
                    extent=raw_points.max(0)-raw_points.min(0)
                    flat=extent[2]<max(extent[:2])*.15
                    if flat and (abs(p['angles'][0])>35 or abs(p['angles'][2])>35):
                        raise ValueError('Surface foliage needs its original steep support, not a ground projection')
                    local_points=raw_points@matrix.T*p['scale']
                    origin[2]=support-local_points[:,2].min()+.5 if flat else support-3
                    if abs(origin[2]-original_origin[2])>48:
                        raise ValueError('Grounded foliage would need an excessive vertical adjustment')
                local = []; count = 0
                for section, slot in zip(parts, slots):
                    if not len(section): continue
                    data = section.copy(); data[:, :, :3] = section[:, :, :3]@matrix.T*p['scale']+origin
                    data[:, :, 3:6] = section[:, :, 3:6]@matrix.T
                    data[:, :, 3:6] /= np.maximum(np.linalg.norm(data[:, :, 3:6], axis=2, keepdims=True), 1e-12)
                    data[:, :, 7] = 1-section[:, :, 7]
                    area = np.linalg.norm(np.cross(data[:, 1, :3]-data[:, 0, :3], data[:, 2, :3]-data[:, 0, :3]), axis=1)
                    data = data[area > .00001]
                    cross = np.cross(data[:, 1, :3]-data[:, 0, :3], data[:, 2, :3]-data[:, 0, :3])
                    reverse = np.sum(cross*data[:, :, 3:6].sum(1), axis=1) < 0
                    data[reverse] = data[reverse][:, [0, 2, 1]]
                    if len(data): local.append((skin[slot], data)); count += len(data)
                if not count: raise ValueError('Empty source rendering LOD')
                if used+count > triangle_budget or group_used+count > allowance: continue
                allp = np.concatenate([d[:, :, :3].reshape(-1, 3) for _,d in local]); lo, hi = allp.min(0), allp.max(0)
                if solid in (2,6,7) and any(np.all(hi >= a) and np.all(lo <= b) for a,b in protected):
                    raise ValueError('Source prop would overlap a game-mode spawn or objective clearance')
                col, method = collider(folder, solid, parts)
                col = (col@matrix.T*p['scale']+origin).astype('<f4')
                first = sum(len(d) for d in geometry)
                for material, data in local:
                    geometry.append(data); matnames.extend([material]*len(data)); foliage_flags.extend([is_foliage]*len(data))
                physical.append(col)
                row = dict(index=p['index'], model=p['model'], source_origin=p['origin'], origin=origin.tolist(),
                    origin_adjustment=(origin-original_origin).tolist(), angles=p['angles'], scale=p['scale'], skin=p['skin'],
                    lod=lod, first_triangle=first, triangles=count, collision_triangles=len(col), collision_method=method,
                    source_solid=solid, foliage=is_foliage)
                rows.append(row); selected.add(p['index']); used += count; group_used += count
            except (ValueError, OSError, struct.error, KeyError) as error:
                skipped.append(dict(index=p['index'], model=p['model'], reason=str(error)))
    if used < triangle_budget*.96: raise ValueError(f'Eligible geometry only {used}/{triangle_budget}; review selection before relaxing safeguards')
    data = np.concatenate(geometry); physical = np.concatenate(physical)
    np.savez(work/'addition.npz', data=data, materials=np.asarray(matnames), foliage=np.asarray(foliage_flags,'u1'), collision=physical)
    report = dict(map=config['map'], baseline_version=config['version'], target_version=VERSIONS[ident],
        baseline_bsp_sha256=digest(source_path(ident)), native_world_fraction_target=TARGET, maximum_world_fraction=MAXIMUM,
        added_placements=len(rows), added_render_triangles=used, added_collision_triangles=len(physical),
        model_counts=dict(collections.Counter(Path(p['model']).stem for p in rows)), placements=rows, skipped=skipped,
        source_placements_previously_rendered=len(present), dynamic_entities_added=0,
        gameplay_and_ai_entity_slots_not_consumed=True, foliage_source_nonsolid_settings_preserved=True)
    (work/'plan.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('placements','skipped')}, indent=2), flush=True)


def channel(folder, name, semantic, work):
    aliases = dict(albedo='col', normal='nml', gloss='gls', spec='spc')
    for path in (folder/(name+'_'+semantic+'Texture.dds'), folder/(name+'_'+aliases[semantic]+'.dds')):
        if path.exists(): return path
    if semantic == 'albedo': raise ValueError('Source albedo unavailable: '+name)
    values = dict(normal=(128,128,255,255), gloss=(30,30,30,255), spec=(8,8,8,255))
    path = work/('neutral_'+semantic+'.dds')
    if not path.exists(): save_mips(Image.new('RGBA', (4,4), values[semantic]), path)
    return path


def build_materials(ident, names, foliage_names):
    work = OUT/ident/'materials'; work.mkdir(parents=True, exist_ok=True)
    slug = ident.replace('-', '_'); packname = slug+'_fill'
    assets = work/'assets'; manifest = dict(version=7, name=packname, keepDevOnly=True, assetsDir=str(assets),
        outputDir=str(work/'build'), compressLevel=0, hasDynamicLibrary=False, files=[])
    native = native_materials(ident); mapping = {}; template = NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
    leafnative = NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak'); shaders = {}
    common = None
    def embed(g):
        nonlocal common
        if g in shaders: return shaders[g]
        a = next(a for a in leafnative.assets if a['guid']==g); h = leafnative.address(a['header'])
        vs, ps = struct.unpack_from('<2Q', leafnative.data, h+72)
        vt, pt, samplers = struct.unpack_from('<3H', leafnative.data, h+24); first, resources = struct.unpack_from('<2H', leafnative.data, h+30)
        def code(guidvalue):
            nonlocal common
            asset = next((a for a in leafnative.assets if a['guid']==guidvalue), None)
            if asset: return shader(leafnative, asset)[0]
            if common is None: common = NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak')
            return shader(common, next(a for a in common.assets if a['guid']==guidvalue))[0]
        pixel, vertex = code(ps), code(vs); name = slug+'_fill_'+hex(g)[2:]; path = 'shaderset/'+name+'.rpak'
        target = (assets/path).with_suffix('.msw'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'MSW\x03\x01'+struct.pack('<2Q3H2B2I',guid('shader/'+name+'_ps.rpak'),guid('shader/'+name+'_vs.rpak'),pt,vt,samplers,first,resources,37,37+len(pixel))+pixel+vertex)
        manifest['files'].append(dict(_type='shds', _path=path)); shaders[g]=path; return path
    for name in sorted(names):
        leaf = name in foliage_names
        if name.lower() in native and not leaf:
            mapping[name] = dict(name=native[name.lower()]['name'], index=native[name.lower()]['index'], existing=True,
                                  alpha=bool(native[name.lower()]['flags'] & 0x10), foliage=False)
            continue
        folder = material_folder(name)
        if folder is None: raise ValueError('Source texture folder unavailable: '+name)
        albedo = image_dds(channel(folder, name, 'albedo', work))
        if max(albedo.size) > 1024: albedo.thumbnail((1024,1024), Image.Resampling.LANCZOS)
        if leaf:
            opacity = folder/(name+'_opacityMultiplyTexture.dds')
            if opacity.exists():
                mask = image_dds(opacity).getchannel('R').resize(albedo.size, Image.Resampling.LANCZOS)
                values = np.asarray(albedo).copy(); values[:,:,3] = ((values[:,:,3].astype('u2')*np.asarray(mask).astype('u2')+127)//255).astype('u1'); albedo=Image.fromarray(values)
            if albedo.getchannel('A').getextrema()[0] == 255: raise ValueError('Foliage has no recovered opacity: '+name)
            if albedo.getchannel('A').getextrema()[1] < 128: raise ValueError('Foliage opacity has no visible texels: '+name)
        textures = {}
        for i, semantic in enumerate(('albedo','normal','gloss','spec')):
            path = f'texture/{slug}_fill/{name}_{semantic}.rpak'; target=(assets/path).with_suffix('.dds'); target.parent.mkdir(parents=True,exist_ok=True)
            if semantic=='albedo':
                if leaf: save_leaf_mips(albedo, target)
                else: save_mips(albedo, target)
                # These helpers encode BC3 blocks with a legacy DXT5 header.
                # Tag the unchanged blocks as sRGB using a DX10 header; avoid
                # sampling sRGB-authored foliage colours as linear values.
                raw=bytearray(target.read_bytes());assert raw[84:88]==b'DXT5'
                raw[84:88]=b'DX10';target.write_bytes(raw[:128]+struct.pack('<5I',78,3,0,1,0)+raw[128:])
            else:
                source=channel(folder,name,semantic,work); raw=image_dds(source)
                if max(raw.size)>1024: raw.thumbnail((1024,1024),Image.Resampling.LANCZOS);save_mips(raw,target)
                else: shutil.copy2(source,target)
            textures[str(i)]=path; manifest['files'].append(dict(_type='txtr',_path=path,**{'$disableStreaming':True}))
        world = 'world/'+slug+'_fill/'+name
        if leaf:
            emitted = {}; pending = []
            def emit(g):
                if not g: return '0x0'
                if g in emitted: return emitted[g]
                a=next(a for a in leafnative.assets if a['guid']==g);spec,uber=leafnative.material(a)
                suffix=spec['name'].rsplit('/',1)[-1].replace('rope_net',name);path='material/world/'+slug+'_fill/'+suffix+'_wld.rpak'
                emitted[g]=path;spec.update(name='world/'+slug+'_fill/'+suffix,width=albedo.width,height=albedo.height,
                    surfaceProp='grass',blendStates=spec['blendStates']+['0x0']*4,rasterizerFlags=hex(int(spec['rasterizerFlags'],16)&~4))
                spec['shaderSet']=embed(int(spec['shaderSet'],16));spec['$textures']={slot:textures[slot] for slot in spec['$textures']}
                for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'): spec[field]=emit(int(spec[field],16))
                target=assets/path;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(spec,indent=2));target.with_suffix('.uber').write_bytes(uber)
                pending.append(dict(_type='matl',_path=path));return path
            emit(0x77559dca514b790f);manifest['files']+=pending
        else:
            for g, suffix in ((0x1F8E00B988C71BBB,'_colpass'),(0x92424EA716974A64,'')):
                spec,uber=template.material(next(a for a in template.assets if a['guid']==g));spec.update(name=world+suffix,width=albedo.width,height=albedo.height,blendStates=spec['blendStates']+['0x0']*4)
                spec['$textures']=dict(spec['$textures'])|textures
                if not suffix: spec['$colpassMaterial']='material/'+world+'_colpass_wld.rpak'
                path='material/'+world+suffix+'_wld.rpak';target=assets/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.with_suffix('.json').write_text(json.dumps(spec,indent=2));target.with_suffix('.uber').write_bytes(uber);manifest['files'].append(dict(_type='matl',_path=path))
        mapping[name]=dict(name=world,width=albedo.width,height=albedo.height,existing=False,alpha=False,foliage=leaf,
            opacity_preserved=leaf,material_provenance='Native two-sided cutout' if leaf else 'Native opaque PBR', source_folder=str(folder.relative_to(ROOT)))
    (work/'mapping.json').write_text(json.dumps(mapping,indent=2))
    pak=None
    if manifest['files']:
        (work/'build.json').write_text(json.dumps(manifest,indent=2))
        process=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(work/'build.json')],capture_output=True,text=True)
        (work/'build.log').write_text(process.stdout+process.stderr);process.check_returncode();pak=work/'build'/(packname+'.rpak')
        built=NativePak(pak);known={a['guid'] for a in built.assets}
        for path in (ROOT/'inputs/tf2-rpak-work/common.raw.rpak',ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak'):
            known.update(a['guid'] for a in NativePak(path).assets)
        for a in built.assets:
            if a['type']!='matl':continue
            spec,_=built.material(a)
            for value in list(spec['$textures'].values())+[spec[k] for k in ('shaderSet','$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]:
                assert not int(value,16) or int(value,16) in known, 'Unresolved new material dependency'
    return mapping,pak


def append_collision(lumps, buffers, physical):
    previous=active(lumps);first=len(lumps[0x45])//44
    area=np.linalg.norm(np.cross(physical[:,1]-physical[:,0],physical[:,2]-physical[:,0]),axis=1);physical=physical[area>.00001]
    if not len(physical):return dict(new_headers=0,new_triangles=0,existing_active_collision_preserved=True)
    center=physical.mean(1);physical=physical[np.lexsort((center[:,2],center[:,1],center[:,0]))]
    encoded,newbounds=encode([physical[i:i+96] for i in range(0,len(physical),96)],len(buffers[3])//12)
    for at in range(0,len(encoded[0x45]),44):
        struct.pack_into('<i',encoded[0x45],at+16,struct.unpack_from('<i',encoded[0x45],at+16)[0]+len(buffers[0x42])//4)
        struct.pack_into('<i',encoded[0x45],at+20,struct.unpack_from('<i',encoded[0x45],at+20)[0]+len(buffers[0x44])//16)
    for key in (3,0x42,0x44,0x45,0x60):buffers[key].extend(encoded[key])
    positions=np.frombuffer(lumps[3],'<f4').reshape(-1,3);bb=[];bi=[];tb=[];ti=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',lumps[0x5c])):
        if (0,i) in previous:
            c=np.array(r[:3]);e=np.array(r[6:9]);bb.append(((c-e).tolist(),(c+e).tolist()));bi.append(i)
    for i,h in enumerate(struct.iter_unpack('<6h4i4f',lumps[0x45])):
        if (0x40,i) in previous:
            p=positions[h[6]:h[6]+h[3]];tb.append((p.min(0).tolist(),p.max(0).tolist()));ti.append(i)
    tb.extend(newbounds);ti.extend(range(first,first+len(newbounds)))
    assert first+len(newbounds)<65000, 'Collision header reserve exhausted'
    buffers.update({k:bytearray(v) for k,v in remap_grid(bb,tb,bi,ti).items()})
    assert active(buffers)==previous|{(0x40,i) for i in range(first,first+len(newbounds))}, 'Old collision exclusions changed'
    return dict(new_headers=len(newbounds),new_triangles=len(physical),first_new_header=first,
                existing_active_collision_preserved=True,existing_disabled_collision_not_reactivated=True)


def sidecar(source,target,pak,mapping):
    if pak is None:shutil.copy2(source,target);return
    raw=source.read_bytes();offsets=[struct.unpack_from('<2Q',raw,168+i*16) for i in range(6)]
    blocks=[bytearray(raw[o:o+n*(24 if i in (1,4) else 1)]) for i,(o,n) in enumerate(offsets)]
    native=NativePak(pak)
    for entry in mapping.values():
        if entry['existing']:continue
        path='material/'+entry['name']+'_wld.rpak';g=guid(path);assert any(a['guid']==g for a in native.assets)
        blocks[1].extend(struct.pack('<2IQ2I',len(blocks[0]),0,g,0,0));blocks[0].extend(entry['name'].encode()+b'\0')
    header=bytearray(raw[:392]);at=392
    for i in (1,2,3,0,4,5):struct.pack_into('<2Q',header,168+i*16,at,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));at+=len(blocks[i])
    target.write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)))
    assert all(bytes(blocks[i])==raw[offsets[i][0]:offsets[i][0]+offsets[i][1]*(24 if i in (1,4) else 1)] for i in (2,3,4,5))


def build(ident):
    config=CONFIG[ident];work=OUT/ident;plan=json.loads((work/'plan.json').read_text());source=source_path(ident)
    assert digest(source)==plan['baseline_bsp_sha256']
    archive=np.load(work/'addition.npz');data=archive['data'];names=archive['materials'];foliage=archive['foliage'];physical=archive['collision'];archive.close()
    leafnames=set(names[foliage.astype(bool)]);mapping,pak=build_materials(ident,set(names),leafnames)
    lumps=read_lumps(source,LIDS);scene,oldcast=current_scene(lumps)
    # Reuse the tested incremental atlas/bake path and keep every old page byte.
    lightroot=work/'lighting-input';(lightroot/'interior-lighting').mkdir(parents=True,exist_ok=True)
    fixtures=ROOT/('output/phase-runner/interior-lighting/lights.bin' if ident=='phase-runner' else 'output/composite/fixtures.bin')
    shutil.copy2(fixtures,lightroot/'interior-lighting/lights.bin')
    lighting.P=lightroot;lighting.BAKE=work/'bake'
    newcast=np.asarray([not bool(leaf or mapping[str(name)]['alpha']) for name,leaf in zip(names,foliage)],'u1')
    ambient=dict(ambient_rgb=(.09,.10,.12),ambient_visibility=(.65,.35)) if ident=='drop-off' else {}
    uv,page,normal,light,lightreport=lighting.bake_catwalks(scene,oldcast,data[:,:,:3],corner_normals=data[:,:,3:6],new_casters=newcast,**ambient)
    buffers={k:bytearray(v) for k,v in lumps.items()};oldpages=len(lumps[0x53])//8
    assert oldpages+len(light[0x53])//8<64, 'Lightmap page reserve exhausted'
    for key in (0x53,0x62,0x69):buffers[key].extend(light[key])
    texids={}
    for name,entry in mapping.items():
        if entry['existing']:texids[name]=entry['index'];continue
        texids[name]=len(buffers[2])//36;st=len(buffers[0x2c])//4
        buffers[0x2c].extend(struct.pack('<I',len(buffers[0x2b])));buffers[0x2b].extend(entry['name'].replace('/','\\').encode()+b'\0')
        buffers[2].extend(struct.pack('<3f6I',0,0,0,st,entry['width'],entry['height'],0,0,0xa00))
    for name in sorted(set(names)):
        for pg in np.unique(page[names==name]):
            selected=np.flatnonzero((names==name)&(page==pg))
            for start in range(0,len(selected),19000):
                selected_group=selected[start:start+19000];n=len(selected_group);src=data[selected_group]
                points=src[:,:,:3];normals=src[:,:,3:6];tangent,mirror=tangents(points,normals,src[:,:,6:8])
                pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12;base=len(buffers[0x49])//44
                buffers[3].extend(points.astype('<f4').tobytes());ns=np.empty((n*6,3),'<f4');ns[::2]=normals.reshape(-1,3);ns[1::2]=tangent.reshape(-1,3);buffers[0x1e].extend(ns.tobytes())
                vertices=np.zeros(n*3,DT);vertices['pi']=np.arange(pi,pi+n*3);vertices['ni']=np.arange(ni,ni+n*6,2);vertices['uv']=src[:,:,6:8].reshape(-1,2)
                vertices['color']=np.rint(np.clip(src[:,:,8:12],0,255)).astype('u1').reshape(-1,4)
                # Source vertex alpha is a shader mask; native cutout opacity
                # comes from the recovered texture, not this unrelated mask.
                vertices['color'][:,3]=255;vertices['light'][:,:2]=uv[selected_group].reshape(-1,2)
                vertices['tangent']=np.arange(ni+1,ni+n*6,2,dtype='u4')|(mirror.reshape(-1).astype('u4')<<31);buffers[0x49].extend(vertices.tobytes())
                sort=len(buffers[0x52])//12;buffers[0x52].extend(struct.pack('<3hHI',texids[name],oldpages+int(pg),-1,n*3-1,base))
                local=np.arange(n*3,dtype='<u2').reshape(-1,3)[:,[0,2,1]]
                for chunk in partition(points.mean(1),np.arange(n),limit=256):
                    ix=local[chunk];pts=points[chunk].reshape(-1,3);lo=pts.min(0)-.02;hi=pts.max(0)+.02;c=(lo+hi)/2;e=(hi-lo)/2
                    flags=0x100a00|(0x10 if mapping[str(name)]['alpha'] else 0)
                    buffers[0x50].extend(struct.pack('<I3H6b2h2BHI',len(buffers[0x4f])//2,len(chunk),int(ix.min()),int(ix.max()-ix.min()),2,-1,-1,-1,-1,-1,-1,-1,255,255,sort,flags))
                    buffers[0x4f].extend(ix.tobytes())
                    if len(chunk)&1:buffers[0x4f].extend(struct.pack('<3H',*[int(ix[-1,-1])]*3))
                    buffers[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    collision=append_collision(lumps,buffers,physical)
    shadow=data[newcast.astype(bool),:,:3]
    for start in range(0,len(shadow),16000):
        p=shadow[start:start+16000].reshape(-1,3);_,first,inverse=np.unique(p.view('V12').ravel(),return_index=True,return_inverse=True)
        assert len(first)<65536
        buffers[0x7f].extend(struct.pack('<2I2h',len(buffers[0x7c])//12,len(p)//3,1,-1));buffers[0x7c].extend(p[first].tobytes());buffers[0x7e].extend(inverse.astype('<u2').tobytes())
    count=len(buffers[0x7f])//12
    for at in (20,44,56):struct.pack_into('<i',buffers[5],at,count)
    count=len(buffers[0x50])//28;struct.pack_into('<2I',buffers[0xe],24,0,count);struct.pack_into('<3I',buffers[0x7b],0,count,count,count)
    # Preserve the common playable camera envelope from the tested all-visible build.
    objs=np.asarray([(*r[:3],*r[4:7]) for r in struct.iter_unpack('<3fI3fI',lumps[0x79])])
    camera_min=objs[:,:3].max(0);camera_max=objs[:,3:].min(0)
    assert np.all(camera_min<camera_max), 'Existing all-visible camera domain cannot be inferred'
    vis=build_camera_visibility(buffers[0x51],np.arange(count,dtype='<u2').tobytes(),camera_min,camera_max)
    for key,value in zip((0x77,0x78,0x79),vis):buffers[key]=bytearray(value)
    changes,order,inverse=reorder(buffers);buffers.update({k:bytearray(v) for k,v in changes.items()})
    validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52])
    output=work/(config['map']+'.bsp');compact(source,output,buffers);budget=audit(output)
    fraction=budget['native_padded_indices']/WORLD_INDEX_CAPACITY
    assert .97<=fraction<=MAXIMUM, f'World budget {fraction:.6%} outside target/reserve'
    assert budget['static_batch_runs']<MAX_STATIC_BATCHES, 'Dynamic-light batch reserve exhausted'
    assert budget['all_meshes_fit_simultaneously'] and budget['static_batches_fit_simultaneously']
    assert all(buffers[k][:len(lumps[k])]==lumps[k] for k in (0,1,2,3,0x1e,0x42,0x44,0x45,0x49,0x4f,0x52,0x53,0x5c,0x62,0x69,0x65,0x66,0x67,0x68))
    target=OUT/'candidates'/config['package'];target.mkdir(parents=True,exist_ok=True)
    for path in runtime_files(ROOT/'northstar'/config['package']):
        dst=target/path.relative_to(ROOT/'northstar'/config['package']);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
    shutil.copy2(output,target/'mod/maps'/output.name)
    sidecar(source.with_suffix('.stbsp'),target/'mod/maps'/(config['map']+'.stbsp'),pak,mapping)
    if pak:
        shutil.copy2(pak,target/'paks'/pak.name);cfg=json.loads((target/'paks/rpak.json').read_text());cfg['Postload'][pak.name]='mp_coliseum.rpak';(target/'paks/rpak.json').write_text(json.dumps(cfg,indent=2))
    manifest=json.loads((target/'mod.json').read_text());manifest['Version']=VERSIONS[ident];(target/'mod.json').write_text(json.dumps(manifest,indent=2))
    report=dict(**plan,budget=budget,world_fraction=fraction,remaining_world_indices=WORLD_INDEX_CAPACITY-budget['native_padded_indices'],
        static_batch_reserve=2048-budget['static_batch_runs'],collision=collision,lighting=lightreport,
        existing_lightmap_pages=oldpages,added_lightmap_pages=len(light[0x53])//8,
        original_entities_and_probes_preserved=True,original_render_attribute_prefixes_preserved=True,
        existing_camera_domain_preserved=[camera_min.tolist(),camera_max.tolist()],new_portals=0,
        material_count=len(mapping),new_material_count=sum(not m['existing'] for m in mapping.values()),
        bsp_sha256=digest(output),native_runtime_verified=False)
    (work/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('placements','skipped')},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','build'));parser.add_argument('map',choices=CONFIG)
    args=parser.parse_args();(prepare if args.action=='prepare' else build)(args.map)
