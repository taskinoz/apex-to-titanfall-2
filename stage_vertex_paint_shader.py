"""Bind recovered RGB paint to native Titanfall world shader variants.

Extract stock bytecode, including its input-layout flags, without rewriting
HLSL. Native COLOR is gamma-decoded before albedo modulation. Retain the tested
opaque material state, resident PBR channels, collision, lightmaps and meshes.
"""
import json,os,struct,subprocess,shutil
from pathlib import Path
from recover_vertex_paint import ROOT,CONFIG,eligible
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from build_phase_runner_presentation import guid
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from optimize_portalfree_render import material_name

def write(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,indent=2));os.replace(temp,path)

def extract_set(native,set_guid,path,slug):
    a=next(a for a in native.assets if a['guid']==set_guid);h=native.address(a['header'])
    vs,ps=struct.unpack_from('<2Q',native.data,h+72);vtex,ptex,samplers=struct.unpack_from('<3H',native.data,h+24);first,resources=struct.unpack_from('<2H',native.data,h+30)
    def get(g):
        for pak in (native,NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak'),NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')):
            asset=next((a for a in pak.assets if a['guid']==g),None)
            if asset:return shader(pak,asset)
        raise ValueError('Missing native shader bytecode '+hex(g))
    pixel,pp=get(ps);vertex,vp=get(vs)
    pg,vg=guid('shader/'+slug+'_pixel.rpak'),guid('shader/'+slug+'_vertex.rpak')
    data=b'MSW\x03\x01'+struct.pack('<2Q3H2B2I',pg,vg,ptex,vtex,samplers,first,resources,37,37+len(pixel))+pixel+vertex
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return {'native_set':hex(set_guid),'unchanged_bytecode':True,'pixel_variants':pp,'vertex_variants':vp}

def stage(map_id):
    package,mapname,_,_=CONFIG[map_id];mod=ROOT/'northstar'/package;work=ROOT/'output/comparison-repair'/map_id
    receipt=work/'shader.json'
    if receipt.exists():raise ValueError('Shader repair already applied')
    mapfile=mod/'mod/maps'/(mapname+'.bsp');l=read_lumps(mapfile,(2,0x2b,0x2c,0x52))
    material_pack='composite_world' if map_id=='drop-off' else 'phase_runner_world'
    source=NativePak(mod/'paks'/(material_pack+'.rpak'));stock=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak')
    slug=map_id.replace('-','_')+'_vertex_paint';assets=work/'shader-assets';files=[];shaderproof=[]
    for role,g in [('primary',0x6AFE220DA02633A0),('colpass',0x81F5BAC39D4DF3B1)]:
        path='shaderset/'+slug+'_'+role+'.rpak';shaderproof.append(extract_set(stock,g,(assets/path).with_suffix('.msw'),slug+'_'+role));files.append({'_type':'shds','_path':path})
    material_by_name={}
    for a in source.assets:
        if a['type']=='matl':
            spec,uber=source.material(a);material_by_name[spec['name']]=(spec,uber)
    texture_roots=([ROOT/'output/composite/materials/assets'] if map_id=='drop-off' else
                   [ROOT/'output/phase-runner/balanced-materials/assets',ROOT/'output/phase-runner/world-materials/assets'])
    source_textures={}
    for root in texture_roots:
        for f in root.rglob('*.dds'):
            key=guid(f.relative_to(root).with_suffix('.rpak').as_posix());source_textures.setdefault(key,f)
    own_textures={};native_textures={a['guid'] for p in ('common','coliseum') for a in NativePak(ROOT/'inputs/tf2-rpak-work'/(p+'.raw.rpak')).assets if a['type']=='txtr'}
    def resident_textures(spec):
        out={}
        for slot,value in spec['$textures'].items():
            g=int(value,16)
            if g not in source_textures:
                if g in native_textures:out[slot]=value;continue
                raise ValueError('No resident DDS for painted texture '+value)
            if g not in own_textures:
                path='texture/'+slug+'/'+source_textures[g].stem+'.rpak'
                dest=(assets/path).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source_textures[g],dest)
                files.append({'_type':'txtr','_path':path,'$disableStreaming':True});own_textures[g]=path
            out[slot]=own_textures[g]
        return out
    tex=bytearray(l[2]);table=bytearray(l[0x2c]);strings=bytearray(l[0x2b]);sorts=bytearray(l[0x52]);mapping={};material_guids=[]
    scope=json.loads((work/'vertex-paint.json').read_text())['materials'];by_name={}
    for ti in range(len(l[2])//36):
        name=material_name(l,ti).replace('\\','/');base=name.rsplit('/',1)[-1]
        if base not in scope or not scope[base]['matched_vertices']:continue
        original,uber=material_by_name[name]
        if int(original['depthStencilFlags'],16)!=0x17:continue
        if name in by_name:
            mapping[ti]=by_name[name];continue
        # This pass is opaque paint only; never reinterpret glass/overlay alpha.
        newname=name+'_paint';mpath='material/'+newname+'_wld.rpak';cpath='material/'+newname+'_colpass_wld.rpak'
        for role,path,oldname in [('colpass',cpath,name+'_colpass'),('primary',mpath,name)]:
            spec,buffer=material_by_name[oldname];spec=dict(spec)
            spec['name']=newname+('_colpass' if role=='colpass' else '')
            spec['shaderSet']='shaderset/'+slug+'_'+role+'.rpak';spec['glueFlags2']=hex(int(spec['glueFlags2'],16)|2)
            spec['$textures']=resident_textures(spec)
            spec['blendStates']=spec['blendStates']+['0x0']*4
            if role=='primary':spec['$colpassMaterial']=cpath
            target=(assets/path);target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(spec,indent=2));target.with_suffix('.uber').write_bytes(buffer)
            files.append({'_type':'matl','_path':path});material_guids.append((spec['name'],guid(path)))
        index=len(tex)//36;row=bytearray(l[2][ti*36:(ti+1)*36]);struct.pack_into('<I',row,12,len(table)//4);table.extend(struct.pack('<I',len(strings)));strings.extend(newname.replace('/','\\').encode()+b'\0');tex.extend(row)
        mapping[ti]=index;by_name[name]=index
    if not mapping:raise ValueError('No eligible native opaque paint material')
    for i in range(len(sorts)//12):
        ti=struct.unpack_from('<h',sorts,i*12)[0]
        if ti in mapping:struct.pack_into('<h',sorts,i*12,mapping[ti])
    manifest={'version':7,'name':slug,'keepDevOnly':True,'assetsDir':str(assets),'outputDir':str(work/'shader-build'),'compressLevel':0,'hasDynamicLibrary':False,'files':files}
    write(work/'shader-build.json',manifest)
    result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(work/'shader-build.json')],capture_output=True,text=True)
    (work/'shader-build.log').write_text(result.stdout+result.stderr);result.check_returncode()
    built=work/'shader-build'/(slug+'.rpak');pak=NativePak(built);known={a['guid'] for a in pak.assets}|{a['guid'] for a in source.assets}
    for name in ('common','coliseum','homestead'):known.update(a['guid'] for a in NativePak(ROOT/'inputs/tf2-rpak-work'/(name+'.raw.rpak')).assets)
    for a in pak.assets:
        if a['type']!='matl':continue
        s,u=pak.material(a);refs=[s['shaderSet'],*s['$textures'].values(),*[s[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]
        missing=[r for r in refs if int(r,16) and int(r,16) not in known]
        if missing:raise ValueError('Missing paint shader dependencies '+str(missing))
    temp=mapfile.with_suffix('.shader.bsp');compact(mapfile,temp,{2:tex,0x2b:strings,0x2c:table,0x52:sorts});old=read_lumps(mapfile,range(128));new=read_lumps(temp,range(128));changed=[i for i in range(128) if old[i]!=new[i]]
    assert set(changed)<={2,0x23,0x2b,0x2c,0x52},changed
    if 0x23 in changed:
        before_game=old[0x23];after_game=bytearray(new[0x23]);count=struct.unpack_from('<I',before_game)[0]
        old_offset=struct.unpack_from('<I',mapfile.read_bytes(),16+0x23*16)[0]
        new_offset=struct.unpack_from('<I',temp.read_bytes(),16+0x23*16)[0]
        for i in range(count):
            at=4+i*16;ptr,n=struct.unpack_from('<2I',after_game,at+8)
            if n:struct.pack_into('<I',after_game,at+8,ptr-new_offset+old_offset)
        assert bytes(after_game)==before_game,'Game-lump payload changed'
    os.replace(temp,mapfile)
    # Extend the resident material catalogue; do not alter streaming columns.
    sidecar=mapfile.with_suffix('.stbsp');raw=sidecar.read_bytes();blocks=[]
    for i in range(6):
        o,n=struct.unpack_from('<2Q',raw,168+i*16);blocks.append(bytearray(raw[o:o+n*(24 if i in (1,4) else 1)]))
    for name,g in material_guids:
        blocks[1].extend(struct.pack('<2IQ2I',len(blocks[0]),0,g,0,0));blocks[0].extend(name.encode()+b'\0')
    header=bytearray(raw[:392]);cursor=392
    for i in (1,2,3,0,4,5):
        struct.pack_into('<2Q',header,168+i*16,cursor,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));cursor+=len(blocks[i])
    temp=sidecar.with_suffix('.new.stbsp');temp.write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)));os.replace(temp,sidecar)
    dest=mod/'paks'/(slug+'.rpak');temp=dest.with_suffix('.new.rpak');temp.write_bytes(built.read_bytes());os.replace(temp,dest)
    cfg=json.loads((mod/'paks/rpak.json').read_text());cfg['Postload'][slug+'.rpak']='mp_coliseum.rpak';write(mod/'paks/rpak.json',cfg)
    proof={'map':map_id,'materials_rebound':len(mapping),'additional_materials':len(material_guids),'assets':len(pak.assets),'native_shader_sets':shaderproof,'all_dependencies_resolved':True,'material_states_and_pbr_channels_preserved':True,'geometry_collision_and_lightmaps_preserved':True,'changed_lumps':changed,'streaming_columns_preserved':True,'self_contained_resident_textures':len(own_textures)}
    write(receipt,proof);print('Bound',len(mapping),'opaque materials to native vertex-colour shader',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=CONFIG);stage(p.parse_args().map)
