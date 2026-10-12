"""Recover missing source texture channels without rebuilding existing materials."""
import json, shutil, struct, collections
from pathlib import Path
from extract_native_material import NativePak

ROOT=Path(__file__).resolve().parent
P=ROOT/'output/phase-runner'
PROJECT=P/'dev-materials'

def stage(name, channels, provenance, manifest, mapping):
    pak=NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
    templates=[]
    for guid in (0x1F8E00B988C71BBB,0x92424EA716974A64):
        templates.append(pak.material(next(a for a in pak.assets if a['guid']==guid)))
    assets=PROJECT/'assets'; textures={}; sizes={}
    for slot,semantic in enumerate(('albedo','normal','gloss','spec')):
        source=Path(channels[semantic]); raw=source.read_bytes()
        if raw[:4]!=b'DDS ':raise ValueError('Expected DDS '+str(source))
        height,width=struct.unpack_from('<2I',raw,12); sizes[semantic]=[width,height]
        path=f'texture/phase_runner_preview/{name}_{semantic}.rpak'
        target=(assets/path).with_suffix('.dds');target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);textures[str(slot)]=path
        manifest['files'].append({'_type':'txtr','_path':path,'$disableStreaming':True})
    world=f'world/phase_runner_preview/{name}'; primary=f'material/{world}_wld.rpak';color=f'material/{world}_colpass_wld.rpak'
    for path,(template,buffer) in zip((color,primary),templates):
        new=dict(template);new['blendStates']=template['blendStates']+['0x0']*4
        new['name']=world+('_colpass' if path==color else '')
        new['width'],new['height']=sizes['albedo'];new['$textures']=dict(template['$textures'])|textures
        if path==primary:new['$colpassMaterial']=color
        target=assets/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.with_suffix('.json').write_text(json.dumps(new,indent=2));target.with_suffix('.uber').write_bytes(buffer)
        manifest['files'].append({'_type':'matl','_path':path})
    mapping[name]=dict(name=world,width=sizes['albedo'][0],height=sizes['albedo'][1],
        channels={k:str(v.relative_to(ROOT)) for k,v in channels.items()},provenance=provenance)

def prepare():
    shutil.copytree(P/'world-materials/assets',PROJECT/'assets',dirs_exist_ok=True)
    manifest=json.loads((P/'world-materials/build.json').read_text());manifest['assetsDir']=str(PROJECT/'assets');manifest['outputDir']=str(PROJECT/'build')
    recovered={};legion=ROOT/'tools/legion/exported_files'
    channels=dict(albedo=legion/'images/0x386cb750af398a6a.dds',normal=legion/'images/0x4bb097f2155e482e.dds',
        gloss=legion/'images/0x55eb53793a40a6e1.dds',spec=legion/'materials/white_floor_tile_mendoko_02_colpass/0x1cd2b9f508f46a7e.dds')
    stage('white_floor_tile_mendoko',channels,'Exact Apex material GUID texture bindings',manifest,recovered)
    for name in ('s2s_roof_panel_01','barrel_latch_blue'):
        channels={s:legion/f'materials/{name}/{name}_{suffix}.dds' for s,suffix in zip(('albedo','normal','gloss','spec'),('col','nml','gls','spc'))}
        stage(name,channels,'Matching Titanfall roof source' if name.startswith('s2s') else 'Exact Apex barrel source with shader-labelled channels',manifest,recovered)
    manifest['files']=list({f['_path']:f for f in manifest['files']}.values())
    (PROJECT/'build.json').write_text(json.dumps(manifest,indent=2))
    (PROJECT/'recovered.json').write_text(json.dumps(recovered,indent=2))
    counts=collections.Counter();shaders=set()
    for path in (PROJECT/'assets/material').rglob('*.json'):
        spec=json.loads(path.read_text())
        if spec['name'].endswith('_colpass'):continue
        counts['primary_materials']+=1;shaders.add(spec['shaderSet'])
        for slot,semantic in enumerate(('albedo','normal','gloss','specular')):
            recovered_channel=spec['$textures'].get(str(slot),'').startswith('texture/phase_runner_preview/')
            counts[semantic+('_recovered' if recovered_channel else '_native_fallback')]+=1
    audit=dict(counts=dict(counts),shader_sets=sorted(shaders),
        material_rpak_unchanged=False,existing_materials_preserved=True,normal_encoding_not_modified=True,
        new_materials=list(recovered),native_bindings=dict(albedo=0,normal=1,gloss=2,specular=3))
    (PROJECT/'pbr-audit.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(recovered,indent=2))

if __name__=='__main__':prepare()
