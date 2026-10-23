"""Preserve foliage coverage and frozen source emission in isolated packs."""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from new_arena_ports import ROOT, folder

sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
import numpy as np
from PIL import Image
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from build_phase_runner_presentation import guid
from restore_banner_display_textures import image_dds, frozen_display
from build_phase_runner_firs import save_leaf_mips
from bake_terrain_transitions import save_mips
from read_vg_static import compiled_materials
from prepare_new_arena_scene import foliage


def build(ident):
    out = folder(ident) / 'materials'
    scene = json.loads((folder(ident) / 'scene.json').read_text())
    mapping = json.loads((out / 'mapping.json').read_text())
    manifest = json.loads((out / 'build.json').read_text())
    assets = out / 'assets'
    leaf_names = set()
    for p in scene['placements']:
        if foliage(p['model']):
            base = Path(p['folder']) / Path(p['folder']).name
            if base.with_suffix('.rmdl').exists():
                slots, skins = compiled_materials(base.with_suffix('.rmdl').read_bytes())
            else:  # current Apex: RSX Cast export carries the material names
                import read_cast; skins = read_cast.load(Path(p['folder']), 0)[2]
            leaf_names.update(n for skin in skins for n in skin)
    roots = [folder(ident) / 'legion/exported_files/materials', ROOT / 'tools/composite-legion/exported_files/materials',
             ROOT / 'tools/legion/exported_files/materials', ROOT / 'output/phase-runner/shared-assets/materials',
             ROOT / 'output/phase-runner/common-assets/exported_files/materials']
    folders = {}
    for root in roots:
        for p in root.rglob('*_albedoTexture.dds'):
            folders.setdefault(p.stem.removesuffix('_albedoTexture').lower(), p.parent)
    native = NativePak(ROOT / 'inputs/tf2-rpak-work/homestead.raw.rpak')
    common = NativePak(ROOT / 'inputs/tf2-rpak-work/common.raw.rpak')
    emitted_shaders = {}
    files = {f['_path']: f for f in manifest['files']}
    slug = ident.replace('-', '_')

    def embed(g):
        if g in emitted_shaders:
            return emitted_shaders[g]
        a = next(a for a in native.assets if a['guid'] == g)
        at = native.address(a['header'])
        vs, ps = struct.unpack_from('<2Q', native.data, at + 72)
        vt, pt, samplers = struct.unpack_from('<3H', native.data, at + 24)
        first, resources = struct.unpack_from('<2H', native.data, at + 30)
        def code(value):
            asset = next((a for a in native.assets if a['guid'] == value), None)
            return shader(native, asset)[0] if asset else shader(common, next(a for a in common.assets if a['guid'] == value))[0]
        pixel, vertex = code(ps), code(vs)
        name = slug + '_cutout_' + hex(g)[2:]
        path = 'shaderset/' + name + '.rpak'
        target = (assets / path).with_suffix('.msw'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'MSW\x03\x01' + struct.pack('<2Q3H2B2I', guid('shader/'+name+'_ps.rpak'),
            guid('shader/'+name+'_vs.rpak'), pt, vt, samplers, first, resources, 37, 37+len(pixel)) + pixel + vertex)
        files[path] = dict(_type='shds', _path=path)
        emitted_shaders[g] = path
        return path

    repaired = []
    for name, record in mapping['materials'].items():
        albedo_path = (assets / record['textures']['0']).with_suffix('.dds')
        raw = bytearray(albedo_path.read_bytes())
        if raw[84:88] == b'DX10':
            fmt = struct.unpack_from('<I', raw, 128)[0]
            if fmt in (71, 74, 77, 98):
                struct.pack_into('<I', raw, 128, fmt + 1)
                albedo_path.write_bytes(raw)
        source = folders.get(name)
        if source is None:
            continue
        emission = source / (source.name + '_emissiveTexture.dds')
        if emission.exists():
            a = image_dds(source / (source.name + '_albedoTexture.dds'))
            if max(a.size)>1024:a.thumbnail((1024,1024),Image.Resampling.LANCZOS)
            e = image_dds(emission).resize(a.size, Image.Resampling.LANCZOS)
            save_mips(frozen_display(name, a, e), albedo_path)
            record['frozen_source_emission'] = True
            if any(word in name for word in ('screen','display','advert')):
                record['static_glow_ambient']=[.65,.65,.65]
            repaired.append(dict(material=name, kind='frozen-emission', dynamic_emission=False))
        second=source/(source.name+'_emissive2Texture.dds')
        if name.startswith('lava_river') and second.exists():
            a=image_dds(source/(source.name+'_albedoTexture.dds'))
            if max(a.size)>1024:a.thumbnail((1024,1024),Image.Resampling.LANCZOS)
            def channel(semantic):return image_dds(source/(source.name+'_'+semantic+'Texture.dds')).resize(a.size,Image.Resampling.LANCZOS)
            first=np.asarray(a).astype('f4')/255;other=np.asarray(channel('albedo2')).astype('f4')/255
            mask=np.asarray(channel('layerBlend'))[:,:,:1].astype('f4')/255
            emit1=np.asarray(channel('emissive'))[:,:,:3].astype('f4')/255
            emit2=np.asarray(channel('emissive2'))[:,:,:3].astype('f4')/255
            multiply=np.asarray(channel('emissiveMultiply2'))[:,:,:1].astype('f4')/255
            base=(first[:,:,:3]**2.2)*(1-mask)+(other[:,:,:3]**2.2)*mask
            heat=(emit1**2.2)*(1-mask)+(emit2**2.2)*mask*multiply
            radiance=base+heat*10
            values=np.empty((*a.size[::-1],4),'u1');values[:,:,:3]=np.rint(np.clip(radiance/(1+radiance.max(2,keepdims=True)),0,1)**(1/2.2)*255).astype('u1');values[:,:,3]=255
            save_mips(Image.fromarray(values),albedo_path)
            record.update(frozen_lava_layers=True,static_glow_ambient=[.9,.9,.9])
            repaired.append(dict(material=name,kind='frozen-two-layer-lava',source_layer_mask=True,animated_flow=False))
        if name not in leaf_names:
            continue
        albedo = image_dds(source / (source.name + '_albedoTexture.dds'))
        if max(albedo.size)>1024:albedo.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        opacity = record['textures'].get('13')
        if opacity:
            mask = image_dds((assets / opacity).with_suffix('.dds')).getchannel('R').resize(albedo.size, Image.Resampling.LANCZOS)
            v = np.asarray(albedo).copy()
            v[:, :, 3] = ((v[:, :, 3].astype('u2') * np.asarray(mask).astype('u2') + 127) // 255).astype('u1')
            albedo = Image.fromarray(v)
        if albedo.getchannel('A').getextrema()[0] >= 250:
            continue
        if albedo.getchannel('A').getextrema()[1] < 128:
            raise ValueError('Source foliage has no visible coverage: ' + name)
        save_leaf_mips(albedo, albedo_path)
        raw = bytearray(albedo_path.read_bytes())
        if raw[84:88] == b'DXT5':
            raw[84:88] = b'DX10'
            albedo_path.write_bytes(raw[:128] + struct.pack('<5I', 78, 3, 0, 1, 0) + raw[128:])
        world = record['name']; primary_guid = 0x77559dca514b790f
        neutral={'1':('normal',(128,128,255,255)),'2':('gloss',(30,30,30,255)),'3':('spec',(8,8,8,255))}
        for slot,(semantic,colour) in neutral.items():
            if slot not in record['textures']:
                path=f'texture/{slug}/neutral_{semantic}.rpak';target=(assets/path).with_suffix('.dds')
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():save_mips(Image.new('RGBA',(4,4),colour),target)
                record['textures'][slot]=path;files[path]=dict(_type='txtr',_path=path,**{'$disableStreaming':True})
        emitted = {}
        def emit(g):
            if not g:
                return '0x0'
            if g in emitted:
                return emitted[g]
            a = next(a for a in native.assets if a['guid'] == g)
            spec, uber = native.material(a)
            suffix = '' if g == primary_guid else '_pass_' + hex(g)[2:]
            path = 'material/' + world + suffix + '_wld.rpak'
            emitted[g] = path
            spec.update(name=world+suffix, width=albedo.width, height=albedo.height, surfaceProp='grass',
                blendStates=spec['blendStates']+['0x0']*4, rasterizerFlags=hex(int(spec['rasterizerFlags'],16)&~4))
            spec['shaderSet'] = embed(int(spec['shaderSet'],16))
            spec['$textures'] = {slot:record['textures'][slot] for slot in spec['$textures']}
            for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
                spec[field] = emit(int(spec[field],16))
            target=assets/path; target.parent.mkdir(parents=True,exist_ok=True)
            target.with_suffix('.json').write_text(json.dumps(spec,indent=2)); target.with_suffix('.uber').write_bytes(uber)
            files[path] = dict(_type='matl',_path=path)
            return path
        emit(primary_guid)
        record.update(transparent=False, native_foliage_cutout=True, two_sided=True)
        repaired.append(dict(material=name, kind='native-cutout', coverage_preserved=True))
    # RePak can insert texture/shader dependencies when it first encounters a
    # material. Emit them first, and each material pass before its parent, so
    # the later explicit list does not attempt to insert the same GUID again.
    ordered=[f for f in files.values() if f['_type'] in ('txtr','shds')]
    visited=set();visiting=set()
    def order_material(path):
        if path in visited:return
        if path in visiting:raise ValueError('Cyclic material dependency: '+path)
        visiting.add(path)
        spec=json.loads((assets/path).with_suffix('.json').read_text())
        for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
            ref=spec.get(field)
            if ref in files and files[ref]['_type']=='matl':order_material(ref)
        visiting.remove(path);visited.add(path);ordered.append(files[path])
    for path,f in files.items():
        if f['_type']=='matl':order_material(path)
    manifest['files'] = ordered
    (out/'build.json').write_text(json.dumps(manifest,indent=2));(out/'mapping.json').write_text(json.dumps(mapping,indent=2))
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(out/'build.json')],capture_output=True,text=True)
    (out/'finish-build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    (out/'source-channel-repairs.json').write_text(json.dumps(repaired,indent=2))
    print(ident, len(repaired), 'source channel/cutout repairs',flush=True)


if __name__=='__main__':
    build(sys.argv[1])
