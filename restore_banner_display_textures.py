"""Resident Northstar banner and frozen Apex display textures.

Keep native opaque world shaders and all PBR channels. Source emissive RGB is
combined into the display albedo in linear space: a static approximation, not
an animated/emissive shader port. Only banner UVs change; collision, geometry,
visibility, lightmaps and streaming columns must remain identical.
"""
import argparse, datetime, hashlib, io, json, os, shutil, struct, subprocess
from pathlib import Path
from recover_vertex_paint import ROOT, CONFIG, np
from extract_native_material import NativePak
from build_phase_runner_presentation import guid
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from optimize_portalfree_render import DT, material_name
from stage_vertex_paint_shader import write
from PIL import Image

BANNER='thunderdome_flex_screens_plastic_01_opaque'
DISPLAYS={
 'drop-off':('echo_big_screen_animation_01','caustic_big_screen_01_blue','composite_big_screen_01','composite_blue_light_02'),
 'phase-runner':('echo_big_screen_animation_01','caustic_big_screen_01_blue','tv_imc_screen_graphs_01','stasis_light_01_blue')}

def image_dds(path):
    data=bytearray(path.read_bytes())
    if data[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',data,128)[0]
        if fmt in (72,75,78,99):struct.pack_into('<I',data,128,fmt-1)
    return Image.open(io.BytesIO(data)).convert('RGBA')

def linear(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def srgb(x):return np.where(x<=.0031308,x*12.92,1.055*np.maximum(x,0)**(1/2.4)-.055)

def frozen_display(base,albedo,emissive):
    av=np.asarray(albedo).copy();ev=np.asarray(emissive)[:,:,:3]/255
    # This screen's source albedo is a neutral panel mask. Adding its nearly
    # white RGB clips every coloured graph; its emitted image is the artwork.
    if base=='tv_imc_screen_graphs_01':rgb=ev
    else:rgb=srgb(np.clip(linear(av[:,:,:3]/255)+linear(ev)*.75,0,1))
    av[:,:,:3]=np.rint(rgb*255).astype('u1')
    return Image.fromarray(av)

def source_folder(map_id,base):
    roots=[ROOT/'tools/composite-legion/exported_files/materials'] if map_id=='drop-off' else [ROOT/'tools/legion/exported_files/materials',ROOT/'output/phase-runner/common-assets/exported_files/materials',ROOT/'output/phase-runner/shared-assets/materials']
    for root in roots:
        for f in root.rglob(base+'_emissiveTexture.dds'):
            if (f.parent/(base+'_albedoTexture.dds')).exists():return f.parent
    raise ValueError('No source display channels: '+base)

def encode(path,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    cmd=[str(ROOT/'tools/directxtex/texconv.exe'),'-y','-f','BC7_UNORM_SRGB','-w','1024','-h','2048' if path.stem=='northstar-banner-v1' else '1024','-m','0','-dx10','-o',str(dest.parent),str(path)]
    result=subprocess.run(cmd,capture_output=True,text=True);result.check_returncode()
    generated=dest.parent/(path.stem+'.dds')
    if generated!=dest:os.replace(generated,dest)

def stage(map_id):
    package,mapname,_,_=CONFIG[map_id];mod=ROOT/'northstar'/package
    work=ROOT/'output/banner-display-repair'/map_id;work.mkdir(parents=True,exist_ok=True)
    if (work/'receipt.json').exists():raise ValueError('Already applied')
    backup=ROOT/'output/banner-display-repair/backups'/package
    def preserve(source,target):
        try:os.link(source,target)
        except OSError:shutil.copy2(source,target)
    if backup.exists() and any(p.is_file() for p in backup.rglob('*')):
        for p in mod.rglob('*'):
            if p.is_file():
                saved=backup/p.relative_to(mod)
                assert saved.exists() and hashlib.sha256(saved.read_bytes()).digest()==hashlib.sha256(p.read_bytes()).digest(),'Incomplete or changed backup'
    else:shutil.copytree(mod,backup,copy_function=preserve,dirs_exist_ok=True)
    mapfile=mod/'mod/maps'/(mapname+'.bsp');l=read_lumps(mapfile,range(128))
    source=NativePak(mod/'paks'/('composite_world.rpak' if map_id=='drop-off' else 'phase_runner_world.rpak'))
    materials={}
    for a in source.assets:
        if a['type']=='matl':
            spec,uber=source.material(a);materials[spec['name']]=(spec,uber)
    roots=[ROOT/'output/composite/materials/assets'] if map_id=='drop-off' else [ROOT/'output/phase-runner/balanced-materials/assets',ROOT/'output/phase-runner/world-materials/assets']
    texfiles={}
    for root in roots:
        for f in root.rglob('*.dds'):texfiles.setdefault(guid(f.relative_to(root).with_suffix('.rpak').as_posix()),f)
    native={a['guid'] for p in ('common','coliseum') for a in NativePak(ROOT/'inputs/tf2-rpak-work'/(p+'.raw.rpak')).assets}
    slug=map_id.replace('-','_')+'_banner_displays';assets=work/'assets';files=[];owned={};proof=[]
    tex=bytearray(l[2]);table=bytearray(l[0x2c]);strings=bytearray(l[0x2b]);sorts=bytearray(l[0x52]);mapping={};catalogue=[];by_name={}
    targets=set(DISPLAYS[map_id])|({BANNER} if map_id=='drop-off' else set())
    for ti in range(len(l[2])//36):
        name=material_name(l,ti);base=name.rsplit('/',1)[-1]
        if base not in targets:continue
        if name in by_name:
            mapping[ti]=by_name[name];continue
        original,uber=materials[name]
        if int(original['depthStencilFlags'],16)!=0x17:raise ValueError('Display is not opaque: '+name)
        png=ROOT/'art/northstar/northstar-banner-v1.png'
        entry={'material':name,'kind':'northstar-banner' if base==BANNER else 'frozen-source-emission'}
        if base!=BANNER:
            folder=source_folder(map_id,base);a=image_dds(folder/(base+'_albedoTexture.dds'));e=image_dds(folder/(base+'_emissiveTexture.dds')).resize(a.size,Image.Resampling.LANCZOS)
            png=work/(base+'.png');frozen_display(base,a,e).save(png)
            entry['source_channels']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder/(base+'_albedoTexture.dds'),folder/(base+'_emissiveTexture.dds'))}
        tpath='texture/'+slug+'/'+base+'_albedo.rpak';encode(png,(assets/tpath).with_suffix('.dds'));files.append({'_type':'txtr','_path':tpath,'$disableStreaming':True})
        newname=name+'_northstar_colour';mpath='material/'+newname+'_wld.rpak';cpath='material/'+newname+'_colpass_wld.rpak'
        for role,path,oldname in [('colpass',cpath,name+'_colpass'),('primary',mpath,name)]:
            spec,buffer=materials[oldname];spec=dict(spec);spec['name']=newname+('_colpass' if role=='colpass' else '');spec['blendStates']+=['0x0']*4
            channels={}
            for slot,value in spec['$textures'].items():
                if slot=='0':channels[slot]=tpath;continue
                g=int(value,16)
                if g not in texfiles:
                    if g not in native:raise ValueError('Missing PBR channel '+value)
                    channels[slot]=value;continue
                if g not in owned:
                    p='texture/'+slug+'/'+texfiles[g].stem+'.rpak';dest=(assets/p).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(texfiles[g],dest);files.append({'_type':'txtr','_path':p,'$disableStreaming':True});owned[g]=p
                channels[slot]=owned[g]
            spec['$textures']=channels
            if role=='primary':spec['$colpassMaterial']=cpath
            target=assets/path;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(spec,indent=2));target.with_suffix('.uber').write_bytes(buffer);files.append({'_type':'matl','_path':path});catalogue.append((spec['name'],guid(path)))
        row=bytearray(l[2][ti*36:(ti+1)*36]);struct.pack_into('<I',row,12,len(table)//4);table.extend(struct.pack('<I',len(strings)));strings.extend(newname.replace('/','\\').encode()+b'\0');mapping[ti]=len(tex)//36;by_name[name]=mapping[ti];tex.extend(row);proof.append(entry)
    if len(proof)!=len(targets):raise ValueError('Missing selected materials')
    vertices=np.frombuffer(l[0x49],DT).copy();indices=np.frombuffer(l[0x4f],'<u2');banner_ids=[]
    for row in struct.iter_unpack('<I3H6b2h2BHI',l[0x50]):
        si=row[-2];ti,_,_,_,base=struct.unpack_from('<3hHI',l[0x52],si*12)
        if material_name(l,ti).rsplit('/',1)[-1]==BANNER:
            banner_ids.extend((base+indices[row[0]:row[0]+row[1]*3].astype('u4')).tolist())
    if banner_ids:
        ids=np.unique(banner_ids);uv=vertices['uv'][ids].copy()
        vertices['uv'][ids,0]=np.clip((uv[:,0]-.529007077)/(.972563148-.529007077),0,1)
        vertices['uv'][ids,1]=np.clip((uv[:,1]-.001622021)/(1.998145461-.001622021),0,1)
        before=np.frombuffer(l[0x49],DT)
        for field in DT.names:
            if field!='uv':assert np.array_equal(before[field],vertices[field])
        assert np.array_equal(before['uv'][np.setdiff1d(np.arange(len(vertices)),ids)],vertices['uv'][np.setdiff1d(np.arange(len(vertices)),ids)])
    for i in range(len(sorts)//12):
        ti=struct.unpack_from('<h',sorts,i*12)[0]
        if ti in mapping:struct.pack_into('<h',sorts,i*12,mapping[ti])
    write(work/'build.json',{'version':7,'name':slug,'assetsDir':str(assets),'outputDir':str(work/'build'),'compressLevel':0,'keepDevOnly':True,'files':files})
    r=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(work/'build.json')],capture_output=True,text=True);(work/'build.log').write_text(r.stdout+r.stderr);r.check_returncode()
    built=work/'build'/(slug+'.rpak');pak=NativePak(built);known=native|{a['guid'] for a in source.assets}|{a['guid'] for a in pak.assets}
    for a in pak.assets:
        if a['type']=='matl':
            s,u=pak.material(a)
            for ref in [s['shaderSet'],*s['$textures'].values(),*[s[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]:
                assert not int(ref,16) or int(ref,16) in known,ref
    updates={2:tex,0x2b:strings,0x2c:table,0x52:sorts}
    if banner_ids:updates[0x49]=vertices.tobytes()
    temp=mapfile.with_suffix('.colour.bsp');compact(mapfile,temp,updates);new=read_lumps(temp,range(128));changed=[i for i in range(128) if new[i]!=l[i]]
    assert set(changed)<=set(updates)|{0x23},changed
    # Compaction relocates only GAME_LUMP absolute addresses.
    before=l[0x23];after=bytearray(new[0x23]);oldoff=struct.unpack_from('<I',mapfile.read_bytes(),16+0x23*16)[0];newoff=struct.unpack_from('<I',temp.read_bytes(),16+0x23*16)[0]
    for i in range(struct.unpack_from('<I',before)[0]):
        at=4+i*16;ptr,n=struct.unpack_from('<2I',after,at+8)
        if n:struct.pack_into('<I',after,at+8,ptr-newoff+oldoff)
    assert bytes(after)==before
    sidecar=mapfile.with_suffix('.stbsp');raw=sidecar.read_bytes();blocks=[]
    for i in range(6):
        o,n=struct.unpack_from('<2Q',raw,168+i*16);blocks.append(bytearray(raw[o:o+n*(24 if i in (1,4) else 1)]))
    for name,g in catalogue:blocks[1].extend(struct.pack('<2IQ2I',len(blocks[0]),0,g,0,0));blocks[0].extend(name.encode()+b'\0')
    header=bytearray(raw[:392]);cursor=392
    for i in (1,2,3,0,4,5):struct.pack_into('<2Q',header,168+i*16,cursor,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));cursor+=len(blocks[i])
    stemp=sidecar.with_suffix('.colour.stbsp');stemp.write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)))
    dest=mod/'paks'/(slug+'.rpak');dtemp=dest.with_suffix('.new.rpak');shutil.copy2(built,dtemp);os.replace(dtemp,dest);os.replace(stemp,sidecar);os.replace(temp,mapfile)
    cfg=json.loads((mod/'paks/rpak.json').read_text());cfg['Postload'][slug+'.rpak']='mp_coliseum.rpak';write(mod/'paks/rpak.json',cfg)
    receipt=dict(map=map_id,materials=proof,banner_vertices=len(set(banner_ids)),changed_lumps=changed,geometry_collision_visibility_lightmaps_preserved=True,streaming_columns_preserved=True,dependencies_resolved=True,additional_resident_bytes=built.stat().st_size,approximation='Source emissive RGB frozen into albedo, linear-space weight 0.75; existing PBR shaders retained')
    write(work/'receipt.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=CONFIG);stage(p.parse_args().map)
