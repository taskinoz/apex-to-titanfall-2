"""Build an isolated, source-derived HDR lava candidate from accepted Overflow 0.4.1."""
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from prepare_anniversary_release import ROOT,digest,write
from new_arena_ports import folder

sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from PIL import Image
from extract_native_material import NativePak
from native_lava_emission import patch_msw,validate_pixel_shaders
from restore_banner_display_textures import image_dds
from bake_terrain_transitions import save_mips
from build_phase_runner_presentation import guid

OUT=ROOT/'output/overflow-lava-2026'
BASE=ROOT/'output/anniversary-2026/baseline/ArenaOverflow'
NAME='lava_river_aqueduct_01_bm'
NEW='world/overflow/'+NAME+'_hdr'


def variants(data):
    start=struct.unpack_from('<I',data,29)[0]
    for i in range(data[start+7]):
        at=start+16+i*24;size,relative=struct.unpack_from('<2I',data,at)
        if size<len(data):yield i,data[at+relative:at+relative+size]


def linear(rgb):return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
def encoded(rgb):return np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)


def verify_existing_assets(base,new):
    index={a['guid']:a for a in new.assets};materials=textures=0
    for a in base.assets:
        if a['guid'] not in index:raise ValueError('Original asset missing')
        other=index[a['guid']]
        if a['type']=='matl':
            if base.material(a)!=new.material(other):raise ValueError('Unrelated material changed')
            materials+=1
        elif a['type']=='txtr':
            h=base.address(a['header']);j=new.address(other['header'])
            n=struct.unpack_from('<I',base.data,h+24)[0]
            x=base.address(a['cpu']);y=new.address(other['cpu'])
            if base.data[h+16:h+36]!=new.data[j+16:j+36] or x is None or y is None or base.data[x:x+n]!=new.data[y:y+n]:
                raise ValueError('Original resident texture changed')
            textures+=1
    return dict(original_materials_unchanged=materials,original_textures_unchanged=textures,
                original_assets_present=len(base.assets),new_assets=len(new.assets)-len(base.assets))


def texture(project,name,image):
    path='texture/overflow_lava/'+name+'.rpak';dest=(project/'assets'/path).with_suffix('.dds')
    dest.parent.mkdir(parents=True,exist_ok=True);save_mips(image,dest)
    raw=bytearray(dest.read_bytes())
    if raw[84:88]==b'DXT5':
        raw[84:88]=b'DX10';raw=raw[:128]+struct.pack('<5I',78,3,0,1,0)+raw[128:]
    elif raw[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',raw,128)[0]
        if fmt in (71,74,77,98):struct.pack_into('<I',raw,128,fmt+1)
    dest.write_bytes(raw);return path


def build():
    if digest(folder('overflow')/'materials/build/overflow_world.rpak')!=digest(BASE/'paks/overflow_world.rpak'):
        raise ValueError('Working world baseline differs from accepted 0.4.1')
    project=OUT/'material-project';assets=project/'assets';assets.mkdir(parents=True,exist_ok=True)
    source=folder('overflow')/'materials/assets/shaderset'
    original=(source/'overflow_native_bm.msw').read_bytes()
    hdr=next(variants((source/'overflow_native_bc654af817a04c94.msw').read_bytes()))[1]
    patched,proof=patch_msw(original,hdr)
    validate_pixel_shaders([dx for i,dx in variants(patched)])
    patched=bytearray(patched)
    struct.pack_into('<2Q',patched,5,guid('shader/overflow_lava_hdr_pixel.rpak'),guid('shader/overflow_lava_hdr_vertex.rpak'))
    shader='shaderset/overflow_lava_hdr.rpak';path=(assets/shader).with_suffix('.msw');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(patched)
    files=[dict(_type='shds',_path=shader)]
    pak=NativePak(BASE/'paks/overflow_world.rpak');materials={}
    for a in pak.assets:
        if a['type']=='matl':
            spec,uber=pak.material(a)
            if spec['name'] in ('world/overflow/'+NAME,'world/overflow/'+NAME+'_colpass'):materials[spec['name']]=(spec,uber)
    if len(materials)!=2:raise ValueError('Missing accepted main/colour-pass lava materials')
    src=folder('overflow')/'legion/exported_files/materials'/NAME
    albedo=image_dds(src/(NAME+'_albedoTexture.dds')).convert('RGBA');albedo.thumbnail((1024,1024),Image.Resampling.LANCZOS)
    bindings={'0':texture(project,'source_albedo',albedo)}
    for layer,slot in [('', '4'),('2','27')]:
        e=image_dds(src/(NAME+'_emissive'+layer+'Texture.dds')).convert('RGB').resize(albedo.size,Image.Resampling.LANCZOS)
        m=image_dds(src/(NAME+'_emissiveMultiply'+layer+'Texture.dds')).convert('RGB').resize(albedo.size,Image.Resampling.LANCZOS)
        radiance=linear(np.asarray(e,dtype='f4')/255)*(np.asarray(m,dtype='f4')/255)
        image=Image.fromarray(np.rint(np.clip(encoded(radiance),0,1)*255).astype('u1')).convert('RGBA')
        bindings[slot]=texture(project,'source_layer'+(layer or '1')+'_emissive',image)
    files.extend(dict(_type='txtr',_path=p,**{'$disableStreaming':True}) for p in bindings.values())
    from apex_material_constants import ApexMaterials
    values,_=ApexMaterials(folder('overflow')/'paks/mp_rr_aqueduct.rpak').constants(NAME)
    tint0=values['c_depthBlendScalarAndL0_emissiveTint'][1:]
    tint1=values['c_L1_perfGlossAndL1_emissiveTint'][1:]
    if tint0!=tint1 or tint0!=[10.,10.,10.]:raise ValueError('Source lava tint contract changed')
    for suffix in ('_colpass',''):
        spec,uber=materials['world/overflow/'+NAME+suffix]
        spec=dict(spec,name=NEW+suffix,shaderSet=shader)
        spec['blendStates']=(spec['blendStates']+['0x0']*8)[:8]
        spec['$textures']={**spec['$textures'],**bindings}
        spec['$colpassMaterial']='material/'+NEW+'_colpass_wld.rpak' if not suffix else '0x0'
        b=bytearray(uber);struct.pack_into('<3f',b,160,*tint0)
        path='material/'+NEW+suffix+'_wld.rpak';dest=assets/path;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.with_suffix('.json').write_text(json.dumps(spec,indent=2));dest.with_suffix('.uber').write_bytes(b)
        files.append(dict(_type='matl',_path=path))
    manifest=dict(name='overflow_lava_hdr',assetsDir=str(assets.resolve()),outputDir=str((project/'build').resolve()),files=files)
    # Use the existing project's proven RePak option spelling and version.
    original_manifest=json.loads((folder('overflow')/'materials/build.json').read_text())
    manifest={**original_manifest,**manifest}
    (project/'build.json').write_text(json.dumps(manifest,indent=2))
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(project/'build.json')],capture_output=True,text=True)
    (project/'build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    # Keep source textures and new materials in one world pack. Cross-pack
    # forward references must not depend on the order of sibling Postload jobs.
    full=OUT/'full-world';full_assets=full/'assets';full_assets.mkdir(parents=True,exist_ok=True)
    for source_assets in (folder('overflow')/'materials/assets',assets):
        for srcfile in source_assets.rglob('*'):
            if not srcfile.is_file():continue
            destfile=full_assets/srcfile.relative_to(source_assets);destfile.parent.mkdir(parents=True,exist_ok=True)
            if destfile.exists():destfile.unlink()
            try:os.link(srcfile,destfile)
            except OSError:shutil.copy2(srcfile,destfile)
    full_manifest={**original_manifest,'name':'overflow_world','assetsDir':str(full_assets.resolve()),
                   'outputDir':str((full/'build').resolve()),'files':original_manifest['files']+files}
    (full/'build.json').write_text(json.dumps(full_manifest,indent=2))
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(full/'build.json')],capture_output=True,text=True)
    (full/'build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    unchanged=verify_existing_assets(pak,NativePak(full/'build/overflow_world.rpak'))
    write(OUT/'original-assets-validation.json',unchanged)
    package=OUT/'candidate/ArenaOverflow'
    if not package.exists():shutil.copytree(BASE,package)
    # Copy-on-replace: never write through a staged/runtime hardlink.
    dest=package/'paks/overflow_world.rpak';temp=dest.with_suffix('.rpak.copying');shutil.copy2(full/'build/overflow_world.rpak',temp);temp.replace(dest)
    old_extra=package/'paks/overflow_lava_hdr.rpak'
    if old_extra.exists():old_extra.unlink()
    config=json.loads((BASE/'paks/rpak.json').read_text())
    (package/'paks/rpak.json').write_text(json.dumps(config,indent=2)+'\n')
    info=json.loads((package/'mod.json').read_text());info['Version']='0.4.2';(package/'mod.json').write_text(json.dumps(info,indent=2)+'\n')
    from repair_preview_index_padding import read_lumps
    from compact_preview_bsp import compact
    work=OUT/'map';work.mkdir(exist_ok=True);bsp=BASE/'mod/maps/mp_overflow.bsp'
    l=read_lumps(bsp,(0x2b,0x2c));strings=bytearray(l[0x2b]);table=bytearray(l[0x2c]);changed=0
    for i in range(0,len(table),4):
        at=struct.unpack_from('<I',table,i)[0];name=strings[at:strings.index(0,at)].decode().replace('\\','/')
        if name=='world/overflow/'+NAME:
            struct.pack_into('<I',table,i,len(strings));strings.extend(NEW.encode()+b'\0');changed+=1
    if changed!=1:raise ValueError('Expected one material-name remap')
    compact(bsp,work/'mp_overflow.bsp',{0x2b:strings,0x2c:table})
    (work/'source-build.json').write_text('{}')
    from build_preview_stbsp import build as stbsp
    stbsp(work,full,'mp_overflow','overflow_world',extra_paks=[p for p in (BASE/'paks').glob('*.rpak') if p.name!='overflow_world.rpak'])
    for name in ('mp_overflow.bsp','mp_overflow.stbsp'):
        dest=package/'mod/maps'/name;temp=dest.with_suffix(dest.suffix+'.copying');shutil.copy2(work/name,temp);temp.replace(dest)
    before=read_lumps(bsp,tuple(range(128)));after=read_lumps(work/'mp_overflow.bsp',tuple(range(128)))
    altered=[i for i in before if before[i]!=after[i]]
    if set(altered)-{0x23,0x2b,0x2c}:raise ValueError('Unexpected geometry/collision/lighting change: '+str(altered))
    write(OUT/'build-validation.json',dict(version='0.4.2',shader_variants=proof,driver_shader_creation=True,
        source_emission_tint=tint0,changed_bsp_lumps=altered,geometry_collision_lighting_preserved=True,
        baseline_world_sha256=digest(BASE/'paks/overflow_world.rpak'),candidate_bsp_sha256=digest(package/'mod/maps/mp_overflow.bsp'),
        limitations=['Source scrolling/distortion not reconstructed','Emission multiply detail frozen into the two source emissive maps']))
    print('HDR lava candidate built with source tint and preserved native blending',flush=True)


if __name__=='__main__':build()
