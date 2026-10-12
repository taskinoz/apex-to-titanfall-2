"""Rebind only recovered glass faces over the confirmed 0.1.41 scene."""
import collections,json,os,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from extract_native_material import NativePak
from extract_world_glass_shader import extract
from inspect_console_uvs import source as console_source
from build_center_detail import add_texture_rows
from build_phase_runner_catwalks import mesh_faces,face_key,shadows
from optimize_portalfree_render import material_name
from repair_preview_index_padding import read_lumps,validate_index_padding
from repair_camera_visibility import build_camera_visibility
from compact_preview_bsp import compact
from audit_world_draw_budget import static_draw_key,enforce_camera_bypass_budget
from finalize_lighting_release import digest
P=ROOT/'output/phase-runner';SOURCE=P/'center-detail/mp_phase_runner.bsp'
OUT=P/'glass-console';TARGET=OUT/'mp_phase_runner.bsp';MATERIALS=P/'glass-console-materials'
BASE=ROOT/'northstar/PhaseRunner.Preview';PACKAGE=ROOT/'northstar/PhaseRunner.GlassConsoleRelease'
NAMES=('truck_mod_common_lrg_01_glass','s2s_bridge_glass_cracked_04','ts_window01_dark_cracked_bm')

def materials():
    assets=MATERIALS/'assets';manifest=dict(version=7,name='phase_runner_glass_console',keepDevOnly=True,
        assetsDir=str(assets),outputDir=str(MATERIALS/'build'),compressLevel=0,hasDynamicLibrary=False,files=[])
    shader=extract(assets/'shaderset/phase_runner_world_glass.msw')
    manifest['files'].append(dict(_type='shds',_path='shaderset/phase_runner_world_glass.rpak'))
    pak=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak')
    template,uber=pak.material(next(a for a in pak.assets if a['guid']==0x92b5ba61a3bf2e7a));mapping={}
    for name,opacity in zip(NAMES,(.35,.6,.42)):
        newname=name+'_transparent';folder=ROOT/'tools/legion/exported_files/materials'/name;textures={};channels={}
        for slot,semantic in ((0,'albedo'),(1,'normal'),(2,'gloss'),(3,'spec'),(13,'opacityMultiply')):
            source=folder/(name+'_'+semantic+'Texture.dds');path=f'texture/phase_runner_preview/{newname}_{semantic}.rpak'
            dest=(assets/path).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            textures[str(slot)]=path;channels[semantic]=str(source.relative_to(ROOT));manifest['files'].append(dict(_type='txtr',_path=path,**{'$disableStreaming':True}))
        h,w=struct.unpack_from('<2I',(folder/(name+'_albedoTexture.dds')).read_bytes(),12)
        world='world/phase_runner_preview/'+newname;path='material/'+world+'_wld.rpak'
        spec=dict(template);spec.update(name=world,width=w,height=h,shaderSet='shaderset/phase_runner_world_glass.rpak',
            blendStates=template['blendStates']+['0x0']*4,rasterizerFlags='0x2')
        spec['$textures']=textures
        buf=bytearray(uber);struct.pack_into('<6f',buf,0,1,0,-0.,1,0,0);struct.pack_into('<f',buf,108,opacity)
        dest=assets/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.with_suffix('.json').write_text(json.dumps(spec,indent=2));dest.with_suffix('.uber').write_bytes(buf)
        manifest['files'].append(dict(_type='matl',_path=path));mapping[newname]=dict(name=world,width=w,height=h,channels=channels,opacity=opacity,
            source_material=name,source_layer='primary',two_sided=True,depth_write=False)
    (MATERIALS/'build.json').write_text(json.dumps(manifest,indent=2));(MATERIALS/'mapping.json').write_text(json.dumps(mapping,indent=2))
    r=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(MATERIALS/'build.json')],capture_output=True,text=True);(MATERIALS/'build.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Glass RPak failed '+r.stdout[-1500:])
    new=NativePak(MATERIALS/'build/phase_runner_glass_console.rpak');known={a['guid'] for a in new.assets}
    for fn in ('common.raw.rpak','coliseum.raw.rpak'):known.update(a['guid'] for a in NativePak(ROOT/'inputs/tf2-rpak-work'/fn).assets)
    for a in new.assets:
        if a['type']!='matl':continue
        spec,buf=new.material(a)
        deps=[int(x,16) for x in [spec['shaderSet'],*spec['$textures'].values(),*[spec[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]]
        if any(g and g not in known for g in deps):raise ValueError('Missing glass dependencies')
        if spec['depthStencilFlags']!='0x7' or len(buf)!=224:raise ValueError('Invalid transparency')
    proof=dict(native_shader=shader,assets=len(new.assets),all_dependencies_present=True,all_textures_resident=True,
               native_world_glass_template=hex(0x92b5ba61a3bf2e7a),all_materials_depth_read_without_depth_write=True)
    (MATERIALS/'validation.json').write_text(json.dumps(proof,indent=2));return mapping,proof,new

def sidecar(pak):
    raw=bytearray(SOURCE.with_suffix('.stbsp').read_bytes());offsets=[struct.unpack_from('<2Q',raw,168+i*16) for i in range(6)]
    blocks=[bytes(raw[o:o+n*(24 if i in (1,4) else 1)]) for i,(o,n) in enumerate(offsets)]
    strings=bytearray(blocks[0]);infos=bytearray(blocks[1]);added=[]
    for a in pak.assets:
        if a['type']!='matl':continue
        spec,_=pak.material(a);infos.extend(struct.pack('<2IQ2I',len(strings),0,a['guid'],0,0));strings.extend(spec['name'].encode()+b'\0');added.append(spec['name'])
    blocks[0]=strings;blocks[1]=infos;header=raw[:392];cursor=392
    for i in (1,2,3,0,4,5):
        struct.pack_into('<2Q',header,168+i*16,cursor,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));cursor+=len(blocks[i])
    TARGET.with_suffix('.stbsp').write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)))
    return dict(added_materials=added,column_payloads_preserved=True)

def build():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    if json.loads((BASE/'mod.json').read_text())['Version']!='0.1.41' or digest(BASE/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Baseline changed')
    mapping,proof,pak=materials();print('Native world-glass shaders and 15 resident source textures built.',flush=True)
    l=read_lumps(SOURCE,(2,3,5,0xe,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x7b,0x7c,0x7e,0x7f))
    changes,byname=add_texture_rows(l,mapping)
    for n in mapping:struct.pack_into('<I',changes[2],byname[n]*36+32,0xa10)
    expected=console_source();lookup={k:mat for k,(mat,data,index) in expected.items() if mat in NAMES};keys=collections.Counter(lookup.keys())
    arr=np.load(P/'center-detail/center-geometry.npz');truck=arr['data'][arr['materials']==NAMES[0],:,:3]
    for t in truck:k=face_key(t);lookup[k]=NAMES[0];keys[k]+=1
    if len(truck)!=82 or sum(keys.values())!=394:raise ValueError('Unexpected exact glass surfaces')
    records=[];bounds=[];ix=bytearray();sorts=bytearray(l[0x52]);sortmap={};found=collections.Counter();history=[]
    for mi,r,raw,ids,tri in mesh_faces(l):
        groups=collections.OrderedDict()
        for j,t in enumerate(tri):
            mat=lookup.get(face_key(t));groups.setdefault(mat,[]).append(j)
            if mat:found[mat]+=1
        for mat,selection in groups.items():
            row=bytearray(l[0x50][mi*28:mi*28+28]);selected=raw[selection];flat=selected.ravel()
            struct.pack_into('<I3H',row,0,len(ix)//2,len(selection),int(flat.min()),int(flat.max()-flat.min()));ix.extend(flat.tobytes())
            if len(selection)&1:ix.extend(struct.pack('<3H',*[int(flat[-1])]*3))
            if mat:
                key=(r[-2],mat)
                if key not in sortmap:
                    s=bytearray(l[0x52][r[-2]*12:r[-2]*12+12]);struct.pack_into('<h',s,0,byname[mat+'_transparent']);sortmap[key]=len(sorts)//12;sorts.extend(s)
                struct.pack_into('<H',row,22,sortmap[key]);struct.pack_into('<I',row,24,r[-1]|0x10)
            if len(selection)==len(tri):box=l[0x51][mi*32:mi*32+32]
            else:
                xyz=tri[selection];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;box=struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0)
            records.append(bytes(row));bounds.append(box);history.append(dict(old_mesh=mi,faces=selection,glass=mat))
    if sum(found.values())!=sum(keys.values()):raise ValueError('Source glass did not match')
    order=sorted(range(len(records)),key=lambda i:(bool(struct.unpack_from('<I',records[i],24)[0]&0x10),static_draw_key(records[i])))
    opaque=sum(not bool(struct.unpack_from('<I',r,24)[0]&0x10) for r in records)
    changes.update({0x50:b''.join(records[i] for i in order),0x51:b''.join(bounds[i] for i in order),0x4f:ix,0x52:sorts})
    count=len(records);model=bytearray(l[0xe]);struct.pack_into('<I',model,28,count);level=bytearray(l[0x7b]);struct.pack_into('<3I',level,0,opaque,opaque,count);changes.update({0xe:model,0x7b:level})
    refs=struct.pack('<'+'H'*count,*range(count));nodes,refs,obj=build_camera_visibility(changes[0x51],refs);changes.update({0x77:nodes,0x78:refs,0x79:obj})
    shadow_changes,shadow_proof=shadows(l,keys,np.empty((0,3,3),dtype='<f4'));changes.update(shadow_changes)
    validate_index_padding(changes[0x50],changes[0x4f],changes[0x52]);compaction=compact(SOURCE,TARGET,changes);budget=enforce_camera_bypass_budget(TARGET)
    if budget['static_batch_runs']>=512:raise ValueError('Batch margin exceeded')
    stb=sidecar(pak)
    report=dict(version='0.1.42',source_version='0.1.41',source_surfaces_rebound=dict(found),opaque_meshes=opaque,transparent_meshes=count-opaque,
        native_partition_boundaries=[opaque,opaque,count],budget=budget,resident_sidecar=stb,materials=proof,shadow=shadow_proof,
        original_geometry_uvs_normals_lightmaps_and_collision_preserved=True,new_connected_portals=0,client_appearance_verified=False,
        limitation='Apex two-layer console glass uses its recovered primary layer. Existing baked lightmaps remain intact; glass is removed only from live opaque shadow casters.',
        elapsed_seconds=time.monotonic()-start,compaction=compaction)
    (OUT/'glass-console.json').write_text(json.dumps(report,indent=2));(OUT/'mesh-provenance.json').write_text(json.dumps([history[i] for i in order]))
    for f in BASE.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else TARGET.with_suffix('.stbsp') if rel.as_posix()=='mod/maps/mp_phase_runner.stbsp' else f
        if dest.exists():dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    shutil.copy2(MATERIALS/'build/phase_runner_glass_console.rpak',PACKAGE/'paks/phase_runner_glass_console.rpak')
    config=json.loads((PACKAGE/'paks/rpak.json').read_text());config['Postload']['phase_runner_glass_console.rpak']='mp_coliseum.rpak';(PACKAGE/'paks/rpak.json').write_text(json.dumps(config,indent=2))
    mod=json.loads((PACKAGE/'mod.json').read_text());mod.update(Version='0.1.42',Description='Phase Runner with native transparent truck and console glass.');(PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());status['glass_console_release']=report;status['world_draw_budget_repair']['after']=budget;status['render_repair']['world_meshes']=count;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(OUT/'glass-console.json',PACKAGE/'glass-console.json');print(json.dumps({k:v for k,v in report.items() if k not in ('materials','compaction')},indent=2),flush=True)
if __name__=='__main__':build()
