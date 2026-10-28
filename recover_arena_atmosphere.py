"""Native fog, campaign water and source-textured HDR glow for arena previews."""
import json,math,os,shutil,struct,subprocess,sys
from pathlib import Path
from new_arena_ports import CONFIG,ROOT,WORK,folder
from apex_material_constants import ApexMaterials
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from build_phase_runner_presentation import guid
from repair_environment_lighting import entities,text_entities
from compact_preview_bsp import compact
from restore_banner_display_textures import image_dds
from bake_terrain_transitions import save_mips
from PIL import Image


def vertex_tint(name,verified=False):
    # Terrain/blend shaders also store red/green in COLOR as layer weights.
    # Treat only explicitly named colour materials as RGB modulation.
    # These packs also use colour/palette weights on names ending in _vc.
    # Naming is only a candidate filter; require a reviewed shader mapping.
    return verified and any(s in name.lower() for s in ('_vc','vert_color','v_color')) and not name.lower().endswith('_bm')


def tint(values,field):
    if field not in values:return [1.,1.,1.]  # shader without this constant (resolved from a shared pack): neutral
    v=values[field]
    if len(v)!=4 or not all(math.isfinite(x) and 0<=x<=4096 for x in v[1:]):
        raise ValueError('Invalid reflected source tint')
    return v[1:]


class NativeMaterials:
    def __init__(self,out,slug,manifest):
        self.out=out;self.assets=out/'assets';self.slug=slug
        self.files={f['_path']:f for f in manifest['files']};self.sets={};self.proof=[]
        reference=WORK/'native-atmosphere'
        self.packs=[NativePak(p) for p in [reference/'sp_training.raw.rpak',reference/'sp_crashsite.raw.rpak',
            ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak',ROOT/'inputs/tf2-rpak-work/common.raw.rpak',ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak']]
        self.index={a['guid']:(p,a) for p in reversed(self.packs) for a in p.assets}
        owner,asset=self.index[0x92424EA716974A64]
        self.stock=owner.material(asset)[0]

    def material(self,g):
        p,a=self.index[g];return p.material(a)

    def shaderset(self,g):
        if g in self.sets:return self.sets[g]
        p,a=self.index[g];at=p.address(a['header']);vs,ps=struct.unpack_from('<2Q',p.data,at+72)
        vt,pt,samplers=struct.unpack_from('<3H',p.data,at+24);first,resources=struct.unpack_from('<2H',p.data,at+30)
        owner,asset=self.index[ps];pixel,pp=shader(owner,asset)
        owner,asset=self.index[vs];vertex,vp=shader(owner,asset)
        name=f'{self.slug}_native_{g:x}';path='shaderset/'+name+'.rpak';target=(self.assets/path).with_suffix('.msw')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b'MSW\x03\x01'+struct.pack('<2Q3H2B2I',guid('shader/'+name+'_pixel.rpak'),
            guid('shader/'+name+'_vertex.rpak'),pt,vt,samplers,first,resources,37,37+len(pixel))+pixel+vertex)
        self.files[path]=dict(_type='shds',_path=path);self.sets[g]=path
        self.proof.append(dict(native_shader_set=hex(g),unchanged_bytecode=True,pixel_variants=len(pp),vertex_variants=len(vp)))
        return path

    def texture(self,name,image=None,source=None):
        # Pack GUIDs ignore case; retail material keys keep authored case (bldg_wall_metal_IMC_01).
        path=f'texture/{self.slug}/{name.lower()}.rpak';target=(self.assets/path).with_suffix('.dds');target.parent.mkdir(parents=True,exist_ok=True)
        if source:
            im=image_dds(source)
            if max(im.size)>1024:im.thumbnail((1024,1024),Image.Resampling.LANCZOS)
            save_mips(im,target)
        else:save_mips(image,target)
        raw=bytearray(target.read_bytes())
        # Colour/emission textures are gamma encoded; data maps remain linear.
        if raw[84:88]==b'DXT5' and any(s in name for s in ('albedo','emissive')):
            raw[84:88]=b'DX10'
            target.write_bytes(raw[:128]+struct.pack('<5I',78,3,0,1,0)+raw[128:])
        elif raw[84:88]==b'DX10' and any(s in name for s in ('albedo','emissive')):
            f=struct.unpack_from('<I',raw,128)[0]
            if f in (71,74,77,98):struct.pack_into('<I',raw,128,f+1);target.write_bytes(raw)
        self.files[path]=dict(_type='txtr',_path=path,**{'$disableStreaming':True});return path

    def data_texture(self,name,source,format):
        # Preserve the campaign's two-channel normal/distortion encoding.
        # Decoding BC5 through an RGBA image leaves B=0 and changes the format.
        path=f'texture/{self.slug}/{name}.rpak';target=(self.assets/path).with_suffix('.dds');target.parent.mkdir(parents=True,exist_ok=True)
        cache=self.out/'native-data-conversion'/name;cache.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0','-f',format,
            '-dx10','-o',str(cache),str(source)],check=True,capture_output=True)
        shutil.copy2(cache/(source.stem+'.dds'),target)
        self.files[path]=dict(_type='txtr',_path=path,**{'$disableStreaming':True});return path

    def write(self,path,name,spec,uber,textures,colour=None,emission=None,paint=False,colpass=None):
        # Case-variant keys (retail authored case) can rewrite the same material: keep an already-built path.
        shader=spec['shaderSet'] if str(spec['shaderSet']).startswith('shaderset/') else self.shaderset(int(spec['shaderSet'],16))
        s=dict(spec);s.update(name=name,shaderSet=shader,
            **{'$textures':textures},blendStates=(spec['blendStates']+['0x0']*8)[:8])
        for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial'):
            s[field]=self.stock[field]
        s['$colpassMaterial']=colpass or '0x0'
        if paint:s['glueFlags2']=hex(int(s['glueFlags2'],16)|2)
        b=bytearray(uber)
        if len(b)!=224:raise ValueError('Unexpected native constant buffer')
        if colour is not None:struct.pack_into('<3f',b,96,*colour)
        if emission is not None:struct.pack_into('<3f',b,160,*emission)
        target=(self.assets/path);target.parent.mkdir(parents=True,exist_ok=True)
        target.with_suffix('.json').write_text(json.dumps(s,indent=2));target.with_suffix('.uber').write_bytes(b)
        self.files[path]=dict(_type='matl',_path=path)

    def finish(self,manifest):
        ordered=[f for f in self.files.values() if f['_type'] in ('txtr','shds')];visited=set()
        def visit(path):
            if path in visited:return
            visited.add(path);s=json.loads((self.assets/path).with_suffix('.json').read_text())
            for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
                if s.get(field) in self.files:visit(s[field])
            ordered.append(self.files[path])
        for path,f in self.files.items():
            if f['_type']=='matl':visit(path)
        manifest['files']=ordered;(self.out/'build.json').write_text(json.dumps(manifest,indent=2))
        run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(self.out/'build.json')],capture_output=True,text=True)
        (self.out/'atmosphere-build.log').write_text(run.stdout+run.stderr);run.check_returncode()


def fog(ident):
    out=folder(ident);path=out/(CONFIG[ident]['target']+'.bsp');scene=json.loads((out/'scene.json').read_text())
    source=next(e for e in scene['source_entities'] if e.get('classname')=='env_fog_controller')
    supported={k:v for k,v in source.items() if k.startswith('fog') or k in ('forceontosky','use_angles','angles','minfadetime')}
    # This global controller's editor origin is remote from gameplay. Heights
    # are authored fog coordinates (also in the old training source), not the
    # editor-room origin or the static-prop recenter offset.
    supported.update(classname='env_fog_controller',spawnclass='reFog',origin='0 0 0',spawnflags='1',
        targetname=ident.replace('-','_')+'_source_fog',fogenable='1')
    rows=[e for e in entities(path) if e.get('classname')!='env_fog_controller'];rows.append(supported)
    temp=path.with_suffix('.fog.bsp');compact(path,temp,{0:text_entities(rows)});os.replace(temp,path)
    return dict(source=source,native=supported,unsupported_volumetric_keys=[k for k in source if k.startswith('vl_')],
        adaptation='Global native fog controller; source height/distance/colour fields retained, editor origin relocated')


def water(builder,mapping):
    r=mapping['materials']['d_skybox_water_01'];path='material/'+r['name']+'_wld.rpak';cpath='material/'+r['name']+'_colpass_wld.rpak'
    # The Gauntlet shader consumes world lightmaps. The BT opaque preset's
    # first variant relies on model lighting and made this world proxy dark.
    spec,uber=builder.material(0xeb406521a867045b)
    opaque,_=builder.material(0x7193aff894c20c14);spec['blendStates']=opaque['blendStates'];spec['blendStateMask']=opaque['blendStateMask']
    native=WORK/'native-atmosphere/legion/exported_files/materials/water_wild_01_opaque'
    textures={'0':r['textures']['0']}
    for slot,name in [('1','water_wild_01_opaque_nml.dds'),('2','100_gloss_flat_gls.dds'),('3','25_spec_flat_spc.dds'),
                      ('15','water_wild_01_opaque_nml.dds'),('18','water_distortion_02_nml.dds'),('19','water_distortion_02_nml.dds')]:
        format='BC5_UNORM' if slot in ('1','15','18','19') else 'BC4_UNORM' if slot=='2' else 'BC7_UNORM'
        textures[slot]=builder.data_texture('campaign_water_'+name.split('.')[0],native/name,format)
    # The recovered sky UV spans kilometres. Adapt the campaign's tiling to
    # visible water ripples, rather than stretching one river tile over it.
    u=bytearray(uber)
    for at,scale in ((0,32),(24,16),(48,24)):struct.pack_into('<4f',u,at,scale,0,0,scale)
    struct.pack_into('<f',u,108,1)
    child,cuber=builder.material(int(opaque['$colpassMaterial'],16))
    builder.write(cpath,r['name']+'_colpass',child,cuber,textures,[1,1,1])
    builder.write(path,r['name'],spec,u,textures,[1,1,1],colpass=cpath)
    r.update(textures=textures,native_campaign_water=True,static_glow_ambient=[.6,.62,.65])
    return dict(material='d_skybox_water_01',kind='Native Gauntlet opaque water adaptation, BT-7274 wave maps, Apex backdrop albedo',
        non_solid=True,source_wave_parity=False,new_reflection_capture=False)


UNRESOLVED_WHITE_MEAN=200
UNRESOLVED_WHITE_TINT=.55


class RetailConstants:
    """Material constants for current Apex (Oodle packs) from RSX exports: the material's .rsx.json names its
    shader set; the set's .msw lists its shader GUIDs (offset 5); the exported raw shader (.fxc DXBC) carrying
    CBufUberStatic gives the field layout (apex_material_constants.reflect); the exported .uber gives the values.
    Materials whose shaders are unavailable fall back to neutral tints."""
    NEUTRAL={'c_zUpBlendingVertexAlphaAndL0_albedoTint':[0.,1.,1.,1.],'c_depthBlendScalarAndL0_emissiveTint':[0.,1.,1.,1.]}
    def __init__(self,materials,legion=None,shaders=None,exports=None):
        self.materials=set(materials);self.legion=legion;self.shaders=shaders;self.exports=exports;self.layouts={};self.reflected=0
    def layout(self,shaderset):
        from apex_material_constants import reflect
        if shaderset not in self.layouts:
            self.layouts[shaderset]=None
            msw=self.shaders/'shaderset'/(shaderset+'.msw') if self.shaders else None
            if msw and msw.exists():
                raw=msw.read_bytes()
                for guid in struct.unpack_from('<2Q',raw,5):
                    # RSX omits leading zeroes in raw shader filenames. The
                    # fixed-width lookup missed those exports. RDEF reflection
                    # can recover supported shaders; DXIL-only exports still
                    # require a separate reflection implementation.
                    directory=self.shaders/'shader'
                    files=set(directory.glob('0x%016X_*.fxc'%guid))
                    files.update(directory.glob(f'0x{guid:X}_*.fxc'))
                    for fxc in sorted(files):
                        try:self.layouts[shaderset]=reflect(fxc.read_bytes());break
                        except ValueError:continue
                    if self.layouts[shaderset]:break
        return self.layouts[shaderset]
    def constants(self,name):
        meta=self.legion/name/(name+'.rsx.json') if self.legion else None
        if meta and meta.exists():
            m=json.loads(meta.read_text());fields=self.layout(m['spec'].get('shaderSet',''))
            uber=self.exports/m['source']/(m['source']+'.uber') if self.exports else None
            if fields and uber and uber.exists():
                cpu=uber.read_bytes();values={}
                for n,(offset,count) in fields.items():
                    if count%4==0 and offset+count<=len(cpu):values[n]=list(struct.unpack_from('<'+'f'*(count//4),cpu,offset))
                if 'c_zUpBlendingVertexAlphaAndL0_albedoTint' in values:
                    self.reflected+=1
                    for k,v in self.NEUTRAL.items():values.setdefault(k,v)
                    return values,fields
        return dict(self.NEUTRAL),{k:(0,16) for k in self.NEUTRAL}


def retail_constants(ident,materials):
    from new_arena_ports import RETAIL
    src=RETAIL/CONFIG[ident]['source']
    return RetailConstants(materials,folder(ident)/'legion/exported_files/materials',src/'rsx-shaders',
                           src/'rsx-export/exported_files/material')


def build(ident):
    out=folder(ident);receipt=out/'atmosphere-materials.json'
    if receipt.exists():raise ValueError('Atmosphere already applied; restore before-0.3.0 to rebuild')
    mats=out/'materials';manifest=json.loads((mats/'build.json').read_text());mapping=json.loads((mats/'mapping.json').read_text())
    retail=CONFIG[ident].get('retail')
    source=retail_constants(ident,mapping['materials']) if retail else ApexMaterials(out/'paks'/(CONFIG[ident]['source']+'.rpak'))
    builder=NativeMaterials(mats,ident.replace('-','_'),manifest)
    # Retail maps: *_vert_color/_vc scene colours are real paint (not blend weights), so paint them.
    paint=lambda name:vertex_tint(name,verified=bool(retail))
    root=out/'legion/exported_files/materials';rows=[];skipped=[]
    for name,r in mapping['materials'].items():
        if r.get('frozen_lava_layers'):continue
        if ident=='firing-range' and name=='d_skybox_water_01':continue
        p=root/name
        if name not in source.materials or not p.exists():continue
        try:values,fields=source.constants(name)
        except (KeyError,ValueError) as error:
            # Shader set outside the map pack and the shared packs: neutral tint, dimmed for near-white
            # albedos (Thermal Station building_walls_metal_03, mean 221) that blow out under native exposure.
            albedo_path=p/(name+'_albedoTexture.dds')
            if not albedo_path.exists():
                skipped.append(dict(material=name,reason='Source shader reflection unavailable: '+str(error)));continue
            import numpy as _np
            bright=float(_np.asarray(image_dds(albedo_path).convert('L').resize((64,64))).mean())
            scale=UNRESOLVED_WHITE_TINT if bright>UNRESOLVED_WHITE_MEAN else 1.
            values={'c_zUpBlendingVertexAlphaAndL0_albedoTint':[0.,scale,scale,scale],'c_depthBlendScalarAndL0_emissiveTint':[0.,1.,1.,1.]}
            fields={k:(0,16) for k in values}
            skipped.append(dict(material=name,reason='Source shader reflection unavailable: '+str(error),
                                fallback_albedo_tint=scale,albedo_mean=round(bright,1)))
        colour=tint(values,'c_zUpBlendingVertexAlphaAndL0_albedoTint')
        emit=tint(values,'c_depthBlendScalarAndL0_emissiveTint')
        cap=CONFIG[ident].get('emission_cap',{}).get(name)
        if cap is not None:emit=[min(v,cap) for v in emit]  # per-map review: whole-surface emission that Apex masks
        path='material/'+r['name']+'_wld.rpak';cpath='material/'+r['name']+'_colpass_wld.rpak'
        albedo=p/(name+'_albedoTexture.dds');emissive=p/(name+'_emissiveTexture.dds')
        if not albedo.exists():continue
        # Restore original pixels, removing the previous baked-in emission.
        textures=dict(r['textures']);textures['0']=builder.texture(name+'_albedo',source=albedo)
        r['textures']['0']=textures['0']
        unlit=name in ('party_crashers_signs_ad_atlas_01_opaque','olympus_signs_ad_atlas_01_opaque','oasis_signs_ad_atlas_01')
        if not r['transparent'] and not r.get('native_foliage_cutout'):
            if emissive.exists():
                # Campaign world shader includes normal/spec/gloss, emission,
                # and native COLOR variants. Keep the source light's RGB tint.
                spec,uber=builder.material(0xb3f8d91ef031a62)
                textures['4']=builder.texture(name+'_emissive',source=emissive)
                textures['11']=builder.texture('neutral_ao',image=Image.new('RGBA',(4,4),(255,255,255,255)))
                for slot,semantic,c in [('1','normal',(128,128,255,255)),('2','gloss',(30,30,30,255)),('3','spec',(8,8,8,255))]:
                    textures.setdefault(slot,builder.texture('neutral_'+semantic,image=Image.new('RGBA',(4,4),c)))
                child,cuber=builder.material(int(spec['$colpassMaterial'],16))
                builder.write(cpath,r['name']+'_colpass',child,cuber,textures,colour,emit,paint=paint(name))
                builder.write(path,r['name'],spec,uber,textures,colour,emit,paint=paint(name),colpass=cpath)
                r.pop('static_glow_ambient',None);kind='Native HDR emission with source mask/tint and PBR'
            elif unlit:
                spec,uber=builder.material(0xd93184c122ff87e4)
                bind={'0':textures['0'],'4':builder.texture('black_emissive',image=Image.new('RGBA',(4,4),(0,0,0,255)))}
                builder.write(path,r['name'],spec,uber,bind,colour,[0,0,0]);kind='Native unlit source advertisement atlas'
            else:
                # Vertex RGB was present in the BSP but ignored by the generic
                # opaque template. Use the previously tested native paint set.
                for slot,semantic,c in [('1','normal',(128,128,255,255)),('2','gloss',(30,30,30,255)),('3','spec',(8,8,8,255))]:
                    if slot not in textures:textures[slot]=builder.texture('neutral_'+semantic,image=Image.new('RGBA',(4,4),c))
                spec=json.loads((mats/'assets'/path).with_suffix('.json').read_text());uber=(mats/'assets'/path).with_suffix('.uber').read_bytes()
                child=json.loads((mats/'assets'/cpath).with_suffix('.json').read_text());cuber=(mats/'assets'/cpath).with_suffix('.uber').read_bytes()
                if paint(name):
                    spec['shaderSet']=hex(0x6AFE220DA02633A0);child['shaderSet']=hex(0x81F5BAC39D4DF3B1)
                builder.write(cpath,r['name']+'_colpass',child,cuber,textures,colour,paint=paint(name))
                builder.write(path,r['name'],spec,uber,textures,colour,paint=paint(name),colpass=cpath)
                kind='Native vertex paint with source albedo tint/PBR' if paint(name) else 'Source albedo tint/PBR; blend weights excluded from RGB tint'
            rows.append(dict(material=name,kind=kind,source_albedo_tint=colour,source_emissive_tint=emit,
                constant_offsets={k:fields[k] for k in ('c_zUpBlendingVertexAlphaAndL0_albedoTint','c_depthBlendScalarAndL0_emissiveTint') if k in fields}))
            r['native_source_channels']=kind
            r['textures']=bind if kind.startswith('Native unlit') else textures
        else:
            # Alpha/cutout shaders keep their validated coverage behavior. The
            # frozen emission approximation remains only on these surfaces.
            if emissive.exists():
                from restore_banner_display_textures import frozen_display
                a=image_dds(albedo);e=image_dds(emissive).resize(a.size,Image.Resampling.LANCZOS)
                textures['0']=builder.texture(name+'_albedo',image=frozen_display(name,a,e));r['textures']['0']=textures['0']
    if ident=='firing-range':
        rows.append(water(builder,mapping))
    builder.finish(manifest);(mats/'mapping.json').write_text(json.dumps(mapping,indent=2))
    # Only the water proxy retains a constant ambient chart. Real emission is
    # now computed by native HDR shaders rather than multiplied into albedo.
    if ident=='firing-range':
        from light_new_arena_ports import glow
        glow(ident)
    fog_record=fog(ident)
    receipt.write_text(json.dumps(dict(materials=rows,skipped=skipped,shaders=builder.proof,fog=fog_record,
        source_texture_cap=1024,limitations=['Alpha emission remains frozen','Source volumetric scattering and animated advertisements not reproduced']),indent=2))
    from build_preview_stbsp import build as stbsp
    stbsp(out,mats,CONFIG[ident]['target'],ident.replace('-','_')+'_world')
    print(ident,len(rows),'native material repairs and source fog',flush=True)


if __name__=='__main__':build(sys.argv[1])
