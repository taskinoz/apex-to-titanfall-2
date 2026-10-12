"""Restore source center props and authored Nessie LOD0 over confirmed 0.1.40."""
import collections,json,os,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from read_vg_static import load
from plan_budget_model_geometry import model_sections
from simplify_preview_draw import simplifier
from stage_prop_geometry import rotation,transform
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from build_phase_runner_catwalks import face_key,mesh_faces,retain_scene,shadows
import build_phase_runner_catwalks as baking
from apply_baked_lighting import tangents
from repair_camera_visibility import build_camera_visibility
from repair_playable_visibility import CAMERA_MIN,CAMERA_MAX
from repair_world_batch_order import reorder
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from read_prop_physics import read_phy,convex_planes
from repair_preview_hull_edges import vertices_and_bevels
from repair_tunnel_passages import remap_grid
from prepare_dev_materials import stage
import prepare_dev_materials
from extract_native_material import NativePak
from finalize_lighting_release import digest
P=ROOT/'output/phase-runner'
SOURCE=P/'batch-ordered/mp_phase_runner.bsp'
OUT=P/'center-detail';TARGET=OUT/'mp_phase_runner.bsp'
BASE=ROOT/'northstar/PhaseRunner.Preview';PACKAGE=ROOT/'northstar/PhaseRunner.CenterDetailRelease'
MATERIALS=P/'center-detail-materials'
TRUCK='veh_land_msc_truck_mod_police_lrg_01_closed_static'

def placement_sections(prop,sections,slots,skins):
    matrix=np.asarray(rotation(prop['angles']),dtype=float);origin=np.array(prop['origin']);skin=skins[prop['skin']]
    output=[]
    for section,slot in zip(sections,slots):
        if not len(section):continue
        data=np.asarray(section,dtype='<f4').copy();data[:,:,:3]=(data[:,:,:3]@matrix.T*prop['scale']+origin).astype('<f4')
        norm=data[:,:,3:6]@matrix.T;norm/=np.linalg.norm(norm,axis=2)[:,:,None];data[:,:,3:6]=norm;data[:,:,7]=1-data[:,:,7]
        # Match the retained scene's positive geometric normals before native
        # winding conversion. The same swap applies to all corner attributes.
        cross=np.cross(data[:,1,:3]-data[:,0,:3],data[:,2,:3]-data[:,0,:3]);reverse=(cross*data[:,:,3:6].sum(1)).sum(1)<0
        data[reverse]=data[reverse][:,[0,2,1]]
        output.append((skin[slot],data))
    return output

def select():
    props=json.loads((P/'static-props.json').read_text());candidates=json.loads((ROOT/'logs/center-detail-candidates.json').read_text())
    selected={p['index'] for p in candidates['missing'] if '/rocks/icelandic_rockcluster_' in p['model'] or Path(p['model']).stem==TRUCK}
    selected.add(7806);chosen=[p for p in props if p['index'] in selected]
    if len(chosen)!=210:raise ValueError('Unexpected source selection')
    prepared={};geometry=[];materials=[];placements=[]
    for p in chosen:
        name=Path(p['model']).stem;lod=0 if 'nessy' in name or p['index']==16850 else 2 if name==TRUCK else 3;key=name+':lod'+str(lod)
        if key not in prepared:prepared[key]=load(ROOT/'tools/legion/exported_files/models'/name,lod)
        sections,slots,skins=prepared[key];first=len(geometry);start=sum(len(s) for s in geometry)
        for mat,data in placement_sections(p,sections,slots,skins):geometry.append(data);materials.extend([mat]*len(data))
        count=sum(len(s) for s in geometry[first:])
        placements.append(dict(index=p['index'],model=p['model'],origin=p['origin'],angles=p['angles'],scale=p['scale'],skin=p['skin'],
            source_lod=lod,first_triangle=start,triangles=count,solid_mode=p['solid_mode']))
    data=np.concatenate(geometry).astype('<f4');report=dict(placements=placements,models={k:sum(len(s) for s in v[0]) for k,v in prepared.items()},new_triangles=len(data))
    old=model_sections(next(p for p in props if p['index']==7806),2,simplifier(),ratio=.25,error=2.)
    oldgeometry=placement_sections(next(p for p in props if p['index']==7806),*old[:3])
    keys=collections.Counter(face_key(t) for mat,s in oldgeometry for t in s[:,:,:3])
    if sum(keys.values())!=59:raise ValueError('Nessie simplification provenance changed')
    return data,np.array(materials),chosen,keys,report

def new_materials():
    MATERIALS.mkdir(parents=True,exist_ok=True);prepare_dev_materials.PROJECT=MATERIALS
    manifest=dict(version=7,name='phase_runner_detail',keepDevOnly=True,assetsDir=str(MATERIALS/'assets'),
        outputDir=str(MATERIALS/'build'),compressLevel=0,hasDynamicLibrary=False,files=[])
    mapping={}
    for name in ('truck_mod_police_lrg_01','truck_mod_common_lrg_01','truck_mod_common_lrg_01_glass'):
        folder=ROOT/'tools/legion/exported_files/materials'/name
        channels={semantic:folder/(name+'_'+semantic+'Texture.dds') for semantic in ('albedo','normal','gloss','spec')}
        stage(name,channels,'Original closed static truck material, exact recovered Apex channels',manifest,mapping)
    (MATERIALS/'build.json').write_text(json.dumps(manifest,indent=2));(MATERIALS/'mapping.json').write_text(json.dumps(mapping,indent=2))
    result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(MATERIALS/'build.json')],capture_output=True,text=True)
    (MATERIALS/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Detail RPak build failed')
    custom=NativePak(MATERIALS/'build/phase_runner_detail.rpak');native=[NativePak(ROOT/'inputs/tf2-rpak-work'/name) for name in ('common.raw.rpak','coliseum.raw.rpak')]
    known={a['guid'] for p in [custom]+native for a in p.assets};missing=set();count=0
    for a in custom.assets:
        if a['type']!='matl':continue
        spec,uber=custom.material(a)
        if a['version']!=12 or len(uber)!=224:raise ValueError('Wrong detail shader encoding')
        for v in list(spec['$textures'].values())+[spec[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial','shaderSet')]:
            guid=int(v,16)
            if guid and guid not in known:missing.add(hex(guid))
        count+=1
    if missing:raise ValueError('Missing detail dependencies '+str(missing))
    proof=dict(native_v12_verified=True,materials=count,assets=len(custom.assets),all_dependencies_present=True,missing_external_guids=[],
        channels=['albedo','normal','gloss','specular'],textures_resident=True)
    (MATERIALS/'validation.json').write_text(json.dumps(proof,indent=2))
    return mapping,proof

def add_texture_rows(l,mapping):
    tex=bytearray(l[2]);table=bytearray(l[0x2c]);names=bytearray(l[0x2b]);byname={}
    for i,row in enumerate(struct.iter_unpack('<3f6I',tex)):
        no=struct.unpack_from('<I',table,row[3]*4)[0];name=names[no:names.index(0,no)].decode().replace('\\','/');byname[name.rsplit('/',1)[-1]]=i
    for name,entry in mapping.items():
        if name in byname:raise ValueError('Duplicate new material name')
        ti=len(tex)//36;ni=len(table)//4;table.extend(struct.pack('<I',len(names)));names.extend(entry['name'].replace('/','\\').encode()+b'\0')
        tex.extend(struct.pack('<3f6I',0,0,0,ni,entry['width'],entry['height'],0,0,0xa00));byname[name]=ti
    return {2:tex,0x2b:names,0x2c:table},byname

def active(l):
    words=[w for w, in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
    return {(w>>24,(w>>8)&65535) for w in words}

def truck_collision(l,props):
    ids=(1,0x5c,0x5d,0x5e,0x5f);buffers={i:bytearray(l[i]) for i in ids};first=len(l[0x5c])//32
    records=[];owners=[];probes=[]
    for prop in props:
        if Path(prop['model']).stem!=TRUCK:continue
        base=ROOT/'tools/legion/exported_files/models'/TRUCK/TRUCK
        pieces=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]);matrix=rotation(prop['angles']);begin=len(buffers[0x5c])//32
        for piece in pieces:
            convex=convex_planes([[transform(v,matrix,prop['origin'],prop['scale']) for v in face] for face in piece])
            if convex is None:raise ValueError('Non-convex truck physics')
            points,cuts=convex;points=np.array(points);lo=points.min(0);hi=points.max(0)
            cuts=[q for q in cuts if not any(abs(abs(v)-1)<1e-7 for v in q[:3])];_,extra=vertices_and_bevels(lo,hi,cuts)
            c=((lo+hi)/2).astype('<f4');need=np.maximum(abs(lo-c),abs(hi-c));e=np.nextafter(need.astype('<f4'),np.float32(np.inf));at=len(buffers[0x5c])//32;offset=len(buffers[0x5d])//2
            if at>=65535 or len(cuts)+len(extra)>255:raise ValueError('Brush capacity exceeded')
            if len(buffers[1])//16!=1+offset:raise ValueError('Plane/brush offset encoding changed')
            buffers[0x5c].extend(struct.pack('<3f2BH3fI',*c,len(cuts),len(cuts)+len(extra),at,*e,offset))
            for q in cuts+extra:buffers[1].extend(struct.pack('<4f',*q));buffers[0x5d].extend(bytes(2))
            buffers[0x5e].extend(struct.pack('<'+'H'*(6+len(cuts)+len(extra)),*([0]*6+[1]*len(cuts)+[0x4001]*len(extra))))
            buffers[0x5f].extend(bytes(32*(6+len(cuts)+len(extra))));records.append(((c-e).tolist(),(c+e).tolist()))
        owners.append(dict(index=prop['index'],model=prop['model'],first_brush=begin,brushes=len(pieces),method='original_IRPS_convex_with_sweep_bevels'))
        end=np.mean([v for piece in pieces for face in piece for v in face],axis=0)
        end=np.array(transform(end,matrix,prop['origin'],prop['scale']));start=end.copy();start[2]=max(hi[2]+200,end[2]+500)
        probes.append(dict(source_prop=prop['index'],start=start.tolist(),end=end.tolist()))
    original=active(l);bb=[];bi=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',buffers[0x5c])):
        if i>=first or (0,i) in original:c=np.array(r[:3]);e=np.array(r[6:9]);bb.append(((c-e).tolist(),(c+e).tolist()));bi.append(i)
    p=np.frombuffer(l[3],'<f4').reshape(-1,3);tb=[];ti=[]
    for i,h in enumerate(struct.iter_unpack('<6h4i4f',l[0x45])):
        if (0x40,i) in original:v=p[h[6]:h[6]+h[3]];tb.append((v.min(0).tolist(),v.max(0).tolist()));ti.append(i)
    buffers.update(remap_grid(bb,tb,bi,ti))
    if active(buffers)!=original|{(0,i) for i in range(first,len(buffers[0x5c])//32)}:raise ValueError('Existing active collision changed')
    return buffers,dict(owners=owners,first_new_brush=first,new_brushes=len(buffers[0x5c])//32-first,probes=probes,
        existing_active_collision_exactly_retained=True,decorative_rockclusters_retain_authored_nonsolid_setting=True)

def update_stbsp():
    sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
    from bsp_tool.extensions.stbsp import StreamBsp
    raw=bytearray(SOURCE.with_suffix('.stbsp').read_bytes());offsets=[struct.unpack_from('<2Q',raw,168+i*16) for i in range(6)]
    blocks=[bytes(raw[o:o+n*(24 if i in (1,4) else 1)]) for i,(o,n) in enumerate(offsets)]
    string=bytearray(blocks[0]);infos=bytearray(blocks[1]);pak=NativePak(MATERIALS/'build/phase_runner_detail.rpak');added=[]
    for asset in pak.assets:
        if asset['type']!='matl':continue
        spec,_=pak.material(asset);name=spec['name']
        if name.endswith('_colpass'):continue
        infos.extend(struct.pack('<2IQ2I',len(string),0,asset['guid'],0,0));string.extend(name.encode()+b'\0');added.append(name)
    blocks[0]=string;blocks[1]=infos;cursor=392;header=raw[:392]
    for i in (1,2,3,0,4,5):
        count=len(blocks[i])//24 if i in (1,4) else len(blocks[i]);struct.pack_into('<2Q',header,168+i*16,cursor,count);cursor+=len(blocks[i])
    path=TARGET.with_suffix('.stbsp');path.write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)))
    before=StreamBsp.from_file(str(SOURCE.with_suffix('.stbsp')));after=StreamBsp.from_file(str(path))
    if len(after.material_infos)!=len(before.material_infos)+len(added) or after.column_data!=before.column_data:raise ValueError('Resident sidecar differs unexpectedly')
    return dict(added_materials=added,materials=len(after.material_infos),native_version='8.0',column_payload_preserved=True,all_new_textures_resident=True)

def package(report):
    for source in BASE.rglob('*'):
        if not source.is_file():continue
        rel=source.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else TARGET.with_suffix('.stbsp') if rel.as_posix()=='mod/maps/mp_phase_runner.stbsp' else source
        if dest.exists():
            if os.path.samefile(actual,dest):continue
            dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    shutil.copy2(MATERIALS/'build/phase_runner_detail.rpak',PACKAGE/'paks/phase_runner_detail.rpak')
    config=json.loads((PACKAGE/'paks/rpak.json').read_text());config['Postload']['phase_runner_detail.rpak']='mp_coliseum.rpak';(PACKAGE/'paks/rpak.json').write_text(json.dumps(config,indent=2))
    mod=json.loads((PACKAGE/'mod.json').read_text());mod['Version']='0.1.41';mod['Description']='Phase Runner with original center trucks, rock clusters and full-detail Nessie.';(PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    status=json.loads((BASE/'build-status.json').read_text());status['center_detail_release']=report;status['render_triangles']=report['budget']['real_triangles'];status['render_repair']['world_meshes']=report['budget']['meshes'];status['world_draw_budget_repair']['after']=report['budget']
    status['streaming_sidecar'].update(report['resident_sidecar']);(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2));(OUT/'source-build.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(OUT/'center-detail.json',PACKAGE/'center-detail.json');shutil.copy2(MATERIALS/'validation.json',PACKAGE/'center-detail-material-validation.json')
    script=PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut';text=script.read_text();text=text.replace('\t\tPhaseRunner_CatwalkChecks()','\t\tPhaseRunner_CatwalkChecks()\n\t\tPhaseRunner_CenterTruckChecks()',1)
    def vec(p):return '< '+', '.join(f'{v:.6f}' for v in p)+' >'
    import re
    # The old Nessie hull test started inside the newly restored truck. Preserve
    # its end target, move only this diagnostic start above the original hood.
    ends=re.search(r'array<vector> propEnds = \[(.*?)\]',text).group(1);end=[float(v) for v in re.findall(r'<([^>]+)>',ends)[213].split(',')]
    start=end.copy();start[2]+=500
    match=re.search(r'array<vector> propStarts = \[(.*?)\]',text);starts=match.group(1);rows=list(re.finditer(r'<([^>]+)>',starts));row=rows[213]
    fixed=starts[:row.start()]+vec(start)+starts[row.end():];text=text[:match.start(1)]+fixed+text[match.end(1):]
    report['native_probe_adjustment']=dict(index=213,original_target_preserved=True,start=start,end=end,reason='Original diagnostic start intersects restored truck; new start is above the original Nessie target.')
    (PACKAGE/'center-detail.json').write_text(json.dumps(report,indent=2));(OUT/'center-detail.json').write_text(json.dumps(report,indent=2));status['center_detail_release']=report
    (PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2));(OUT/'source-build.json').write_text(json.dumps(status,indent=2))
    text+='\nvoid function PhaseRunner_CenterTruckChecks()\n{\n\tarray<vector> starts = [ '+', '.join(vec(p['start']) for p in report['collision']['probes'])+' ]\n\tarray<vector> ends = [ '+', '.join(vec(p['end']) for p in report['collision']['probes'])+' ]\n\tint hits = 0\n\tfor ( int i = 0; i < starts.len(); i++ )\n\t{\n\t\tTraceResults r = TraceHull( starts[i], ends[i], < -16, -16, 0 >, < 16, 16, 72 >, null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n\t\tif ( r.fraction < 1.0 && !r.startSolid )\n\t\t\thits++\n\t}\n\tprintl( "Phase Runner center truck checks: " + hits + "/" + starts.len() + " passed" )\n}\n'
    script.write_text(text)

def build():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    if json.loads((BASE/'mod.json').read_text())['Version']!='0.1.40' or digest(BASE/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Confirmed baseline mismatch')
    data,materials,props,keys,selection=select();np.savez(OUT/'center-geometry.npz',data=data,materials=materials)
    (OUT/'old-nessie-keys.json').write_text(json.dumps([k.hex() for k in keys],indent=2));print(json.dumps(selection['models']),flush=True)
    mapping,material_proof=new_materials()
    ids=(1,2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x64,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x5d,0x5e,0x5f,0x57,0x59,0x7c,0x7e,0x7f)
    l=read_lumps(SOURCE,ids);retained,scene,casters,retained_map,removed=retain_scene(l,keys)
    print(f'Retained {len(scene)} original triangles, removed only {removed} old Nessie faces; adding {len(data)} source faces.',flush=True)
    baking.BAKE=P/'center-detail-lighting';lightuv,page,_,light,lightreport=baking.bake_catwalks(scene,casters,data[:,:,:3],corner_normals=data[:,:,3:6])
    texchanges,texids=add_texture_rows(l,mapping);buffers={i:bytearray(retained.get(i,l[i])) for i in (3,0x1e,0x49,0x4f,0x50,0x51,0x52,0xe,0x7b)};buffers.update(texchanges)
    normals=data[:,:,3:6];tan,mirror=tangents(data[:,:,:3],normals,data[:,:,6:8]);first_new=len(buffers[0x50])//28;oldpages=len(l[0x53])//8;new_meshes=[]
    for mat in np.unique(materials):
        if mat not in texids:raise ValueError('Missing recovered material '+mat)
        for pg in np.unique(page[materials==mat]):
            selection_ids=np.flatnonzero((materials==mat)&(page==pg))
            # One shared material sort per 10k-triangle vertex block, so hundreds
            # of spatial meshes do not consume hundreds of native draw batches.
            for begin in range(0,len(selection_ids),10000):
                sel=selection_ids[begin:begin+10000];base=len(buffers[0x49])//44;si=len(buffers[0x52])//12
                for ti in sel:
                    for j in range(3):
                        pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12;buffers[3].extend(data[ti,j,:3].tobytes());buffers[0x1e].extend(np.array([normals[ti,j],tan[ti,j]],'<f4').tobytes())
                        buffers[0x49].extend(struct.pack('<2I2f4B4f2I',pi,ni,*data[ti,j,6:8],255,255,255,255,*lightuv[ti,j],0,0,(ni+1)|(int(mirror[ti,j])<<31),0))
                buffers[0x52].extend(struct.pack('<3hHI',texids[mat],oldpages+int(pg),-1,len(sel)*3-1,base))
                for at in range(0,len(sel),256):
                    chosen=sel[at:at+256];raw=np.arange(at*3,(at+len(chosen))*3,dtype='<u2').reshape(-1,3)[:,[0,2,1]];first=len(buffers[0x4f])//2;buffers[0x4f].extend(raw.tobytes())
                    if len(chosen)&1:buffers[0x4f].extend(struct.pack('<3H',*[int(raw[-1,-1])]*3))
                    record=bytearray(l[0x50][:28]);struct.pack_into('<I3H',record,0,first,len(chosen),int(raw.min()),int(raw.max()-raw.min()));struct.pack_into('<H',record,22,si);new_meshes.append(len(buffers[0x50])//28);buffers[0x50].extend(record)
                    xyz=data[chosen,:,:3];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;buffers[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    buffers.update({i:l[i]+light[i] for i in (0x53,0x62,0x69)});cchanges,cproof=truck_collision(l,props);buffers.update(cchanges)
    schanges,sproof=shadows(l,keys,data[:,:,:3]);buffers.update(schanges)
    count=len(buffers[0x50])//28;struct.pack_into('<I',buffers[0xe],28,count);struct.pack_into('<3I',buffers[0x7b],0,count,count,count)
    # Preserve the confirmed full camera domain; ordering is still material/channel.
    nodes,refs,objects=build_camera_visibility(buffers[0x51],struct.pack('<'+'H'*count,*range(count)),CAMERA_MIN,CAMERA_MAX)
    buffers.update({0x77:nodes,0x78:refs,0x79:objects});ochanges,order,inverse=reorder({**l,**buffers});buffers.update(ochanges)
    validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52]);proof=compact(SOURCE,TARGET,buffers);budget=enforce_camera_bypass_budget(TARGET)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.9:raise ValueError('New detail leaves less than 10 percent native index headroom')
    sidecar=update_stbsp()
    report=dict(version='0.1.41',source_version='0.1.40',source_geometry=selection,removed_old_nessie_triangles=removed,new_nessie_triangles=1442,
        restored_trucks=3,restored_rockclusters=206,new_meshes=[inverse[i] for i in new_meshes],
        retained_meshes=[dict(source_mesh=m['source_mesh'],new_mesh=inverse[i],retained_triangles=m['retained_triangles']) for i,m in enumerate(retained_map)],
        light_bake=lightreport,collision=cproof,shadow=sproof,resident_sidecar=sidecar,material_validation=material_proof,budget=budget,
        original_camera_domain_preserved=True,new_portal_connections=0,unrelated_lighting_and_character_probes_preserved=True,
        original_truck_position_rotation_scale_preserved=True,compaction=proof,client_geometry_verified=False,elapsed_seconds=time.monotonic()-start,
        limitation='Small rocks keep their original non-solid setting. Existing surface/probe lightmaps are retained; new source props have separate sun/sky/local lightmaps and current shadow geometry. Final appearance needs an in-game check.')
    (OUT/'center-detail.json').write_text(json.dumps(report,indent=2));package(report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_geometry','retained_meshes','compaction','new_meshes')},indent=2),flush=True)
if __name__=='__main__':build()
