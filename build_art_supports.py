"""Restore omitted cargo/fence supports and repair pipe LODs and alpha road decals."""
import collections,io,json,os,re,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from PIL import Image
from read_vg_static import load
from plan_budget_model_geometry import model_sections
from simplify_preview_draw import simplifier
from build_center_detail import placement_sections,add_texture_rows,active
import build_center_detail as center
from build_phase_runner_catwalks import face_key,mesh_faces,retain_scene,shadows
import build_phase_runner_catwalks as lighting
from apply_baked_lighting import tangents
from prepare_dev_materials import stage
import prepare_dev_materials
from extract_native_material import NativePak
from bake_terrain_transitions import save_mips
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from optimize_portalfree_render import material_name
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from finalize_lighting_release import digest
P=ROOT/'output/phase-runner';SOURCE=P/'glass-console/mp_phase_runner.bsp';OUT=P/'art-supports';TARGET=OUT/'mp_phase_runner.bsp'
MATERIALS=P/'art-support-materials';BASE=ROOT/'northstar/PhaseRunner.Preview';PACKAGE=ROOT/'northstar/PhaseRunner.ArtSupportsRelease'
SUPPORTS=(8449,8450,8451,8452,8453,8454,8459,8460,8461,8462,8463,8464,8465,8466,13008,13009,13010,13011,13012,13013,13014,13015)
PIPES=(8483,8484);DECAL='decals_asphalt_road_dirty_01';NEWDECAL=DECAL+'_alpha'

def adjust_support_diagnostics():
    # Restored fences intersect four old test starts. End targets and physics
    # are unchanged; raise only the diagnostic starts above the fence.
    script=PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut';s=script.read_text()
    original=(BASE/'mod/scripts/vscripts/_phase_runner_preview.nut').read_text()
    ends=re.search(r'array<vector> propEnds = \[(.*?)\]',original).group(1)
    match=re.search(r'array<vector> propStarts = \[(.*?)\]',s);starts=match.group(1)
    rows=list(re.finditer(r'<([^>]+)>',starts));original_rows=re.findall(r'<([^>]+)>',re.search(r'array<vector> propStarts = \[(.*?)\]',original).group(1));end_rows=re.findall(r'<([^>]+)>',ends);proof=[]
    for index in reversed((223,224,225,226)):
        start=[float(v) for v in original_rows[index].split(',')];end=[float(v) for v in end_rows[index].split(',')]
        raised=start.copy();raised[2]=max(start[2],end[2])+512
        row=rows[index];starts=starts[:row.start()]+'< '+', '.join(f'{v:.6f}' for v in raised)+' >'+starts[row.end():]
        proof.append(dict(index=index,old_start=start,start=raised,end=end,original_target_preserved=True,reason='Old diagnostic start intersects restored fence; raise start only.'))
    s=s[:match.start(1)]+starts+s[match.end(1):];script.write_text(s)
    report=json.loads((OUT/'art-supports.json').read_text());report['native_probe_adjustments']=sorted(proof,key=lambda p:p['index'])
    for path in (OUT/'art-supports.json',PACKAGE/'art-supports.json'):path.write_text(json.dumps(report,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());status['art_supports_release']=report;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    return proof

def source_geometry():
    props=json.loads((P/'static-props.json').read_text());data=[];materials=[];placements=[];cache={};old=collections.Counter();fn=simplifier()
    for index in SUPPORTS+PIPES:
        p=props[index];n=Path(p['model']).stem;lod=2 if 'wheeled' in n else 1 if 'tortus' in n else 0
        if n not in cache:cache[n]=load(ROOT/'tools/legion/exported_files/models'/n,lod)
        first=sum(len(a) for a in data)
        for mat,a in placement_sections(p,*cache[n]):data.append(a);materials.extend([mat]*len(a))
        placements.append(dict(index=index,model=p['model'],origin=p['origin'],angles=p['angles'],scale=p['scale'],skin=p['skin'],source_lod=lod,first_triangle=first,triangles=sum(len(a) for a in data)-first,solid_mode=p['solid_mode']))
        if index in PIPES:
            sections=model_sections(p,2,fn,.25,2.)
            for mat,a in placement_sections(p,*sections[:3]):old.update(face_key(t) for t in a[:,:,:3])
    return np.concatenate(data).astype('<f4'),np.array(materials),placements,old,[props[i] for i in SUPPORTS]

def prepare_materials():
    MATERIALS.mkdir(parents=True,exist_ok=True);prepare_dev_materials.PROJECT=MATERIALS
    assets=MATERIALS/'assets';manifest=dict(version=7,name='phase_runner_art_supports',keepDevOnly=True,assetsDir=str(assets),outputDir=str(MATERIALS/'build'),compressLevel=0,hasDynamicLibrary=False,files=[]);mapping={}
    for name in ('freight_tortus_main_01_v1','sewers_wall_01','slum_trim_girdering_01'):
        folder=ROOT/'tools/legion/exported_files/materials'/name
        channels={s:folder/(name+'_'+s+'Texture.dds') for s in ('albedo','normal','gloss','spec')}
        if not channels['spec'].exists():
            fallback=MATERIALS/'neutral_dielectric_spec.dds';save_mips(Image.new('RGBA',(4,4),(8,8,8,255)),fallback);channels['spec']=fallback
        stage(name,channels,'Original source channels; neutral dielectric specular only where no labelled source specular was recovered',manifest,mapping)
    native=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak');spec,uber=native.material(next(a for a in native.assets if a['guid']==0x92b5ba61a3bf2e7a))
    current=NativePak(BASE/'paks/phase_runner_glass_console.rpak');shader=next(a['guid'] for a in current.assets if a['type']=='shds')
    folder=ROOT/'tools/legion/exported_files/materials'/DECAL;textures={}
    for slot,semantic in ((0,'albedo'),(1,'normal'),(2,'gloss'),(3,'spec'),(13,'opacity')):
        path=f'texture/phase_runner_preview/{NEWDECAL}_{semantic}.rpak';dest=(assets/path).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True)
        if semantic=='opacity':
            raw=bytearray((folder/(DECAL+'_albedoTexture.dds')).read_bytes())
            if raw[84:88]==b'DX10':
                fmt=struct.unpack_from('<I',raw,128)[0]
                if fmt in (72,75,78,99):struct.pack_into('<I',raw,128,fmt-1)
            alpha=Image.open(io.BytesIO(raw)).convert('RGBA').getchannel('A');ones=Image.new('L',alpha.size,255)
            save_mips(Image.merge('RGBA',(alpha,alpha,alpha,ones)),dest)
        elif semantic=='spec':save_mips(Image.new('RGBA',(4,4),(0,0,0,255)),dest)
        else:shutil.copy2(folder/(DECAL+'_'+semantic+'Texture.dds'),dest)
        textures[str(slot)]=path;manifest['files'].append(dict(_type='txtr',_path=path,**{'$disableStreaming':True}))
    world='world/phase_runner_preview/'+NEWDECAL;path='material/'+world+'_wld.rpak';new=dict(spec)
    new.update(name=world,width=2048,height=2048,shaderSet=hex(shader),rasterizerFlags='0x16',surfaceProp='default',blendStates=spec['blendStates']+['0x0']*4);new['$textures']=textures
    buf=bytearray(uber);struct.pack_into('<6f',buf,0,1,0,-0.,1,0,0);struct.pack_into('<f',buf,108,1.)
    target=assets/path;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(new,indent=2));target.with_suffix('.uber').write_bytes(buf);manifest['files'].append(dict(_type='matl',_path=path))
    mapping[NEWDECAL]=dict(name=world,width=2048,height=2048,provenance='Recovered road albedo alpha in native opacityMultiplyTexture slot 13; native decal raster depth bias; nonreflective specular')
    (MATERIALS/'build.json').write_text(json.dumps(manifest,indent=2));(MATERIALS/'mapping.json').write_text(json.dumps(mapping,indent=2))
    r=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(MATERIALS/'build.json')],capture_output=True,text=True);(MATERIALS/'build.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Support RPak failed')
    pak=NativePak(MATERIALS/'build/phase_runner_art_supports.rpak');known={a['guid'] for a in pak.assets}
    for p in (ROOT/'inputs/tf2-rpak-work/common.raw.rpak',ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak',BASE/'paks/phase_runner_glass_console.rpak'):known.update(a['guid'] for a in NativePak(p).assets)
    for a in pak.assets:
        if a['type']!='matl':continue
        s,b=pak.material(a)
        for v in list(s['$textures'].values())+[s[k] for k in ('shaderSet','$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]:
            if int(v,16) and int(v,16) not in known:raise ValueError('Missing material dependency '+v)
    return mapping,pak

def sidecar(pak):
    raw=bytearray(SOURCE.with_suffix('.stbsp').read_bytes());off=[struct.unpack_from('<2Q',raw,168+i*16) for i in range(6)];blocks=[bytes(raw[o:o+n*(24 if i in (1,4) else 1)]) for i,(o,n) in enumerate(off)]
    strings=bytearray(blocks[0]);infos=bytearray(blocks[1]);added=[]
    for a in pak.assets:
        if a['type']!='matl':continue
        s,_=pak.material(a)
        if s['name'].endswith('_colpass'):continue
        infos.extend(struct.pack('<2IQ2I',len(strings),0,a['guid'],0,0));strings.extend(s['name'].encode()+b'\0');added.append(s['name'])
    blocks[0]=strings;blocks[1]=infos;header=raw[:392];at=392
    for i in (1,2,3,0,4,5):struct.pack_into('<2Q',header,168+i*16,at,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));at+=len(blocks[i])
    TARGET.with_suffix('.stbsp').write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)));return added

def build():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    if json.loads((BASE/'mod.json').read_text())['Version']!='0.1.42' or digest(BASE/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Unexpected baseline')
    data,mats,placements,oldkeys,props=source_geometry();np.savez(OUT/'source-geometry.npz',data=data,materials=mats);mapping,pak=prepare_materials();print(f'Prepared {len(data)} source triangles for {len(placements)} placements.',flush=True)
    ids=(1,2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x64,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x5d,0x5e,0x5f,0x57,0x59,0x7c,0x7e,0x7f)
    l=read_lumps(SOURCE,ids);retained,scene,casters,history,removed=retain_scene(l,oldkeys);decalkeys=collections.Counter();cursor=0
    for proof in history:
        mi=proof['source_mesh'];flags=struct.unpack_from('<I',l[0x50],mi*28+24)[0];si=struct.unpack_from('<H',l[0x50],mi*28+22)[0];ti=struct.unpack_from('<h',l[0x52],si*12)[0];name=material_name(l,ti);n=len(proof['retained_triangles'])
        if flags&0x10 or name.endswith('/'+DECAL):casters[cursor:cursor+n]=0
        cursor+=n
    for mi,r,raw,vi,tri in mesh_faces(l):
        ti=struct.unpack_from('<h',l[0x52],r[-2]*12)[0]
        if material_name(l,ti).endswith('/'+DECAL):decalkeys.update(face_key(t) for t in tri)
    lighting.BAKE=P/'art-support-lighting';lightuv,page,norm,light,lightreport=lighting.bake_catwalks(scene,casters,data[:,:,:3],corner_normals=data[:,:,3:6])
    texchanges,texids=add_texture_rows(l,mapping);struct.pack_into('<I',texchanges[2],texids[NEWDECAL]*36+32,0xa10)
    buffers={i:bytearray(retained.get(i,l[i])) for i in (3,0x1e,0x49,0x4f,0x50,0x51,0x52,0xe,0x7b)};buffers.update(texchanges)
    decal_sorts={};decal_meshes=[]
    for mi in range(len(buffers[0x50])//28):
        at=mi*28;si=struct.unpack_from('<H',buffers[0x50],at+22)[0];ti=struct.unpack_from('<h',l[0x52],si*12)[0]
        if not material_name(l,ti).endswith('/'+DECAL):continue
        if si not in decal_sorts:
            s=bytearray(l[0x52][si*12:si*12+12]);struct.pack_into('<h',s,0,texids[NEWDECAL]);decal_sorts[si]=len(buffers[0x52])//12;buffers[0x52].extend(s)
        struct.pack_into('<H',buffers[0x50],at+22,decal_sorts[si]);flags=struct.unpack_from('<I',buffers[0x50],at+24)[0];struct.pack_into('<I',buffers[0x50],at+24,flags|0x10);decal_meshes.append(mi)
    normals=data[:,:,3:6];tan,mirror=tangents(data[:,:,:3],normals,data[:,:,6:8]);oldpages=len(l[0x53])//8;first_new=len(buffers[0x50])//28
    for mat in np.unique(mats):
        if mat not in texids:raise ValueError('Missing exact source material '+mat)
        for pg in np.unique(page[mats==mat]):
            selection=np.flatnonzero((mats==mat)&(page==pg))
            for begin in range(0,len(selection),10000):
                sel=selection[begin:begin+10000];base=len(buffers[0x49])//44;si=len(buffers[0x52])//12
                for ti in sel:
                    for j in range(3):
                        pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12;buffers[3].extend(data[ti,j,:3].tobytes());buffers[0x1e].extend(np.array([normals[ti,j],tan[ti,j]],'<f4').tobytes());buffers[0x49].extend(struct.pack('<2I2f4B4f2I',pi,ni,*data[ti,j,6:8],255,255,255,255,*lightuv[ti,j],0,0,(ni+1)|(int(mirror[ti,j])<<31),0))
                buffers[0x52].extend(struct.pack('<3hHI',texids[mat],oldpages+int(pg),-1,len(sel)*3-1,base))
                for at in range(0,len(sel),256):
                    chosen=sel[at:at+256];raw=np.arange(at*3,(at+len(chosen))*3,dtype='<u2').reshape(-1,3)[:,[0,2,1]];first=len(buffers[0x4f])//2;buffers[0x4f].extend(raw.tobytes())
                    if len(chosen)&1:buffers[0x4f].extend(struct.pack('<3H',*[int(raw[-1,-1])]*3))
                    record=bytearray(l[0x50][:28]);struct.pack_into('<I3H',record,0,first,len(chosen),int(raw.min()),int(raw.max()-raw.min()));struct.pack_into('<H',record,22,si);struct.pack_into('<I',record,24,0x100a00);buffers[0x50].extend(record)
                    xyz=data[chosen,:,:3];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;buffers[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    buffers.update({i:l[i]+light[i] for i in (0x53,0x62,0x69)});collision=[]
    for name in sorted({Path(p['model']).stem for p in props}):
        center.TRUCK=name;cchanges,proof=center.truck_collision({**l,**buffers},props);buffers.update(cchanges);collision.append(proof)
    schanges,sproof=shadows(l,oldkeys+decalkeys,data[:,:,:3]);buffers.update(schanges)
    count=len(buffers[0x50])//28;struct.pack_into('<I',buffers[0xe],28,count);nodes,refs,obj=build_camera_visibility(buffers[0x51],struct.pack('<'+'H'*count,*range(count)));buffers.update({0x77:nodes,0x78:refs,0x79:obj})
    ordered,order,inverse=reorder({**l,**buffers});buffers.update(ordered);validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52]);compact(SOURCE,TARGET,buffers);budget=enforce_camera_bypass_budget(TARGET)
    if budget['static_batch_runs']>=512 or budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.95:raise ValueError('Draw safety margin exceeded')
    added=sidecar(pak);report=dict(version='0.1.43',source_version='0.1.42',restored_placements=22,rebuilt_pipe_placements=2,source_placements=placements,removed_old_pipe_triangles=removed,new_triangles=len(data),
        road_decal_triangles_rebound=sum(decalkeys.values()),decal_meshes=[inverse[i] for i in decal_meshes],source_albedo_alpha_restored=True,native_decal_raster_depth_bias=True,collision=collision,
        existing_active_collision_preserved=True,light_bake=lightreport,shadow=sproof,budget=budget,new_meshes=[inverse[i] for i in range(first_new,count)],
        retained_meshes=[dict(**h,new_mesh=inverse[i]) for i,h in enumerate(history)],resident_added_materials=added,client_appearance_verified=False,
        source_positions_rotations_scales_and_uvs_preserved=True,existing_lightmap_payloads_and_character_lighting_preserved=True,new_connected_portals=0,elapsed_seconds=time.monotonic()-start)
    (OUT/'art-supports.json').write_text(json.dumps(report,indent=2))
    for f in BASE.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True);actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else TARGET.with_suffix('.stbsp') if rel.as_posix()=='mod/maps/mp_phase_runner.stbsp' else f
        if dest.exists():dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    shutil.copy2(MATERIALS/'build/phase_runner_art_supports.rpak',PACKAGE/'paks/phase_runner_art_supports.rpak');cfg=json.loads((PACKAGE/'paks/rpak.json').read_text());cfg['Postload']['phase_runner_art_supports.rpak']='mp_coliseum.rpak';(PACKAGE/'paks/rpak.json').write_text(json.dumps(cfg,indent=2))
    mod=json.loads((PACKAGE/'mod.json').read_text());mod.update(Version='0.1.43',Description='Phase Runner with original freight/fence supports, full-detail pipe pieces and alpha road markings.');(PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());status['art_supports_release']=report;status['render_triangles']=budget['real_triangles'];status['render_repair']['world_meshes']=count;status['world_draw_budget_repair']['after']=budget;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2));shutil.copy2(OUT/'art-supports.json',PACKAGE/'art-supports.json')
    script=PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut';s=script.read_text();s=s.replace('\t\tPhaseRunner_CenterTruckChecks()','\t\tPhaseRunner_CenterTruckChecks()\n\t\tPhaseRunner_ArtSupportChecks()',1)
    probes=[p for group in collision for p in group['probes']]
    def vec(p):return '< '+', '.join(f'{v:.6f}' for v in p)+' >'
    s+='\nvoid function PhaseRunner_ArtSupportChecks()\n{\n\tarray<vector> starts = [ '+', '.join(vec(p['start']) for p in probes)+' ]\n\tarray<vector> ends = [ '+', '.join(vec(p['end']) for p in probes)+' ]\n\tint hits = 0\n\tfor ( int i = 0; i < starts.len(); i++ )\n\t{\n\t\tTraceResults r = TraceHull( starts[i], ends[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n\t\tif ( r.fraction < 1.0 && !r.startSolid )\n\t\t\thits++\n\t}\n\tprintl( "Phase Runner art support checks: " + hits + "/" + starts.len() + " passed" )\n}\n';script.write_text(s)
    adjust_support_diagnostics()
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_placements','retained_meshes','new_meshes','collision')},indent=2),flush=True)
if __name__=='__main__':build()
