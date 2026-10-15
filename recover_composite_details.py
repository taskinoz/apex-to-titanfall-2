"""Append source props while preserving the tested scene and lighting charts.

Existing native render streams and source collision remain intact. Additional
receivers use unused tiles on the last lightmap page, ray-baked against both
the existing scene and additions. All source endpoints and boundaries remain.
"""
import collections,json,os,struct,sys,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from build_composite_map import DT
from apply_baked_lighting import tangents,encode_rgbm
from spatial_preview_meshes import partition
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from native_triangle_collision import encode,collision_grid
from read_prop_physics import read_phy,read_bvh
from audit_world_draw_budget import enforce_camera_bypass_budget
OUT=ROOT/'output/composite';WORK=OUT/'detail-recovery';MAP=OUT/'mp_arena_composite.bsp'
BACKUP=ROOT/'output/repair-backups/20261007-before-detail-recovery'
ARMS={1651,1652,1669,1670};POSTS={4960,4974,4994,4995}
JOB=np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')])

def smd_arm():
    folder=ROOT/'output/phase-runner/shared-assets/models/zipline_arm'
    lines=(folder/'zipline_arm_LOD0.smd').read_text().splitlines()
    start=lines.index('triangles')+1;end=lines.index('end',start)
    if (end-start)%4:raise ValueError('Incomplete source arm SMD')
    data=[]
    for at in range(start,end,4):
        if lines[at]!='zipline_arm':raise ValueError('Unexpected arm material')
        data.append([list(map(float,s.split()[1:9])) for s in lines[at+1:at+4]])
    return [np.asarray(data,'<f4')],[0],[['zipline_arm']],str(folder)

def collision(p,sections):
    mat=np.asarray(rotation(p['angles']));origin=np.asarray(p['origin'])
    if p['index'] in ARMS:
        # No compiled physics in this recovered single-material SMD export.
        # Use its exact closed render triangles, never a guessed bounding box.
        return np.concatenate(sections)[:,:,:3]@mat.T*p['scale']+origin,'Exact source SMD surface'
    if p['solid'] not in (2,6,7):return np.empty((0,3,3),'f4'),'Source non-solid'
    folder=Path(p['folder']);base=folder/folder.name
    if base.with_suffix('.phy').exists():pieces=read_phy(base.with_suffix('.phy'));method='IRPS surface'
    else:pieces,_=read_bvh(base.with_suffix('.rmdl'));method='BVH surface'
    faces=[[f[0],f[i],f[i+1]] for piece in pieces for f in piece for i in range(1,len(f)-1)]
    if not faces:raise ValueError('No decoded source collider')
    return np.asarray(faces,'<f4')@mat.T*p['scale']+origin,method

def plan():
    WORK.mkdir(exist_ok=True)
    scene=json.loads((OUT/'scene.json').read_text());audit=json.loads((OUT/'asset-audit.json').read_text())
    inventory={p['index']:p for p in json.loads((OUT/'source-inventory.json').read_text())['props']}
    present={p['index'] for p in scene['placements']};paths=audit['model_paths'];cache={};parts=[];physics=[];selected=[];skipped=[]
    material_roots=[ROOT/'tools/composite-legion/exported_files/materials',ROOT/'tools/legion/exported_files/materials']
    existing=json.loads((OUT/'materials/mapping.json').read_text())['materials']
    allowed=('security_fence_post','traffic_cone','traffic_barrel','traffic_tube','fusebox',
             'sign_plate','beacon_crane_wall_panel_corner','box_med_cardboard','plastic_pallet',
             'oxygen_tank','wire_ground_coils_02','office_keyboard','olympus_docks_gate_sign')
    candidates=[p for p in inventory.values() if p['index'] not in present and
                (p['index'] in ARMS or p['index'] in POSTS or
                 (any(w in p['model'].lower() for w in allowed) and abs(p['origin'][0])<4000 and -200<p['origin'][1]<7600))]
    def rank(p):
        if p['index'] in ARMS:return (0,p['index'])
        if p['index'] in POSTS:return (1,p['index'])
        if 'security_fence_post' in p['model']:return (2,p['index'])
        if 'oxygen_tank' in p['model']:return (4,p['index'])
        return (3,p['index'])
    used=0
    for p in sorted(candidates,key=rank):
        try:
            if p['index'] in ARMS:sec,slots,skins,folder=smd_arm();lod=0
            else:
                folder=paths.get(p['model'])
                if not folder:raise ValueError('Missing compiled export')
                if p['model'] not in cache:
                    f=Path(folder);levels=struct.unpack_from('<18Q',(f/(f.name+'.vg')).read_bytes(),16)[13]
                    lod=min(levels-1,4);raw,slots,skins=load(f,lod)
                    cache[p['model']]=([np.asarray(s,'<f4').reshape(-1,3,8) for s in raw],slots,skins,lod)
                sec,slots,skins,lod=cache[p['model']]
            skin=skins[min(p['skin'],len(skins)-1)]
            local=[]
            for s,slot in zip(sec,slots):
                if not len(s):continue
                name=skin[slot]
                if any(w in name for w in ('godray','ambient_occlusion','start_barrier','atmosphere','glow_overlay')):continue
                if not (existing.get(name,{}).get('recovered') or any((r/name/(name+'_albedoTexture.dds')).is_file() for r in material_roots)):
                    raise ValueError('Unrecovered material '+name)
                data=s.copy();mat=np.asarray(rotation(p['angles']));data[:,:,:3]=s[:,:,:3]@mat.T*p['scale']+p['origin'];data[:,:,3:6]=s[:,:,3:6]@mat.T;data[:,:,7]=1-s[:,:,7]
                local.append((name,data))
            count=sum(len(s) for name,s in local)
            if used+count>36000:raise ValueError('Recovery budget reserved at 36,000 additional triangles')
            row={**p,'lod':lod,'folder':folder,'triangles':count,'recovery':'Source SMD/QC' if p['index'] in ARMS else 'Source VG author LOD'}
            col,method=collision(row,sec)
            if not count:raise ValueError('No eligible visual sections')
            used+=count;parts.extend(local);physics.append(col);selected.append({**row,'collision_recovery':method,'collision_triangles':len(col)})
        except (ValueError,OSError,struct.error) as e:skipped.append(dict(index=p['index'],model=p['model'],reason=str(e)))
    if not ARMS|POSTS <= {p['index'] for p in selected}:raise ValueError('Required source anchors could not all be recovered')
    names=list(dict.fromkeys(name for name,data in parts));tri=np.concatenate([data for name,data in parts]);mi=np.concatenate([np.full(len(data),names.index(name),'i4') for name,data in parts])
    np.savez(WORK/'addition.npz',triangles=tri,material=mi,names=np.asarray(names),collision=np.concatenate(physics))
    report=dict(version='0.4.0',added_props=len(selected),added_triangles=used,placements=selected,skipped=skipped,
                source_anchor_indices=sorted(ARMS|POSTS),policy='Existing scene retained; source attachments first; recovered textures only; 36,000 additional triangle ceiling')
    (WORK/'plan.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(added_props=len(selected),added_triangles=used,model_counts=dict(collections.Counter(Path(p['model']).stem for p in selected))),indent=2),flush=True)

def snapshot():
    if BACKUP.exists():raise ValueError('Backup already exists; use it to roll back before applying again')
    BACKUP.mkdir(parents=True)
    for name in ('mp_arena_composite.bsp','mp_arena_composite.stbsp','scene.npz','scene.json','physics.npz','physics.json','source-build.json','materials/mapping.json','materials/build.json','materials/build/composite_world.rpak'):
        source=OUT/name;dest=BACKUP/name;dest.parent.mkdir(parents=True,exist_ok=True);os.link(source,dest)
    # RePak overwrites its destination, so detach it from both backup and mod.
    (OUT/'materials/build/composite_world.rpak').unlink()
    # These text configurations are also overwritten in place by RePak setup.
    # Detach them after snapshotting so historical snapshots stay immutable.
    for name in ('materials/mapping.json','materials/build.json'):
        path=OUT/name;temp=path.with_suffix('.detached.json');shutil.copy2(path,temp);os.replace(temp,path)

def stage_materials():
    a=np.load(WORK/'addition.npz');names=a['names'];mi=a['material'];a.close()
    scene=json.loads((OUT/'scene.json').read_text())
    for i,name in enumerate(names):scene['materials'][str(name)]=scene['materials'].get(str(name),0)+int((mi==i).sum())
    path=OUT/'scene.json';temp=path.with_suffix('.detail.json');temp.write_text(json.dumps(scene,indent=2));os.replace(temp,path)
    from prepare_composite_materials import prepare
    prepare()

def append(bake_base=None,index_fraction=.9,sun_executable=None,sun_direction=None):
    if (WORK/'result.json').exists():
        raise ValueError('Details already applied; restore the snapshot and clear the receipt before reapplying')
    a=np.load(WORK/'addition.npz');data=a['triangles'];mi=a['material'];names=list(a['names']);col=a['collision'];a.close()
    plan=json.loads((WORK/'plan.json').read_text());oldscene=json.loads((BACKUP/'scene.json').read_text())
    lids=(0,1,2,3,0xe,0x18,0x1e,0x2b,0x2c,0x36,0x42,0x44,0x45,0x49,0x4f,0x50,0x51,0x52,0x53,0x5c,0x60,0x61,0x62,0x64,0x69,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f,5)
    l=read_lumps(MAP,lids);buf={k:bytearray(v) for k,v in l.items()}
    mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
    native_names=[]
    for at in range(0,len(l[2]),36):
        st=struct.unpack_from('<I',l[2],at+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0]
        native_names.append(l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/'))
    first_tri=oldscene['triangles'];perpage=512*512;next_tri=first_tri
    reserved=np.zeros((512,512),bool)
    wall_scope=OUT/'local-repair/wall-scope.npz'
    if wall_scope.exists():
        scope=np.load(wall_scope);origins=scope['origins'];sizes=scope['sizes'];scope.close()
        for (x,y),size in zip(origins.astype(int),sizes):reserved[y//4:(y+size)//4,x//4:(x+size)//4]=True
    jobs=[];ordered=[];casters=[]
    for ti,name in enumerate(names):
        rec=mapping[name];native=rec['name'];alpha=rec['transparent']
        if native in native_names:material=native_names.index(native)
        else:
            material=len(native_names);native_names.append(native);st=len(buf[0x2c])//4
            buf[0x2c].extend(struct.pack('<I',len(buf[0x2b])));buf[0x2b].extend(native.replace('/','\\').encode()+b'\0')
            buf[2].extend(struct.pack('<3f6I',0,0,0,st,1024,1024,0,0,0xa00|(0x10 if alpha else 0)))
        selected=data[mi==ti]
        for at in range(0,len(selected),10000):
            src=selected[at:at+10000];n=len(src);p=src[:,:,:3];normal=src[:,:,3:6];uv=src[:,:,6:8];tan,mirror=tangents(p,normal,uv)
            normal=normal/np.maximum(np.linalg.norm(normal,axis=2,keepdims=True),1e-12)
            pi=len(buf[3])//12;ni=len(buf[0x1e])//12;base=len(buf[0x49])//44
            buf[3].extend(p.astype('<f4').tobytes());nb=np.empty((n*6,3),'<f4');nb[::2]=normal.reshape(-1,3);nb[1::2]=tan.reshape(-1,3);buf[0x1e].extend(nb.tobytes())
            records=np.zeros(n*3,DT);records['pi']=np.arange(pi,pi+n*3);records['ni']=np.arange(ni,ni+n*6,2);records['uv']=uv.reshape(-1,2);records['color']=255;records['tangent']=np.arange(ni+1,ni+n*6,2,dtype=np.uint32)|(mirror.reshape(-1).astype('u4')<<31)
            if src.shape[2]>=12:records['color']=np.rint(np.clip(src[:,:,8:12],0,255)).astype('u1').reshape(-1,4)
            ids=np.arange(next_tri,next_tri+n);page=ids//perpage;tile=ids%perpage
            if np.any(page!=3):raise ValueError('Additional charts must fit unused fourth page')
            if reserved[tile//512,tile%512].any():raise ValueError('Additional charts overlap reserved high-resolution walls; allocate different free atlas space')
            cuv=np.stack((tile%512,tile//512),1)[:,None,:]*4+np.array([[.5,.5],[3.2,.5],[.5,3.2]])
            records['light'][:,:2]=(cuv/2048).reshape(-1,2);buf[0x49].extend(records.tobytes())
            job=np.zeros(n,JOB);job['p']=p;job['n']=normal;job['uv']=cuv;job['page']=0;jobs.append(job);ordered.append(src);casters.append(np.full(n,not alpha,'u1'));next_tri+=n
            local=np.arange(n*3,dtype='<u2').reshape(-1,3);front=np.sum(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])*normal.sum(1),axis=1)>0;local[front]=local[front][:,[0,2,1]]
            si=len(buf[0x52])//12;buf[0x52].extend(struct.pack('<3hHI',material,3,-1,n*3-1,base))
            for ixids in partition(p.mean(1),np.arange(n),limit=512):
                ix=local[ixids];pts=p[ixids].reshape(-1,3);lo=pts.min(0)-.02;hi=pts.max(0)+.02;c=(lo+hi)/2;e=(hi-lo)/2
                buf[0x50].extend(struct.pack('<I3H6b2h2BHI',len(buf[0x4f])//2,len(ix),int(ix.min()),int(ix.max()-ix.min()),2,-1,-1,-1,-1,-1,-1,-1,255,255,si,0x100a00|(0x10 if alpha else 0)));buf[0x4f].extend(ix.tobytes())
                if len(ix)&1:buf[0x4f].extend(struct.pack('<3H',*[int(ix[-1,-1])]*3))
                buf[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
            if not alpha:
                buf[0x7f].extend(struct.pack('<2I2h',len(buf[0x7c])//12,n,1,-1));buf[0x7c].extend(p.astype('<f4').tobytes());buf[0x7e].extend(local.tobytes())
    ordered=np.concatenate(ordered);jobs=np.concatenate(jobs);casts=np.concatenate(casters)
    # Only new triangles receive raster jobs; all existing visible triangles
    # remain occluders. Their off-page UVs cause no receiver texels to be baked.
    bake_base=Path(bake_base) if bake_base else OUT
    oldtri=np.fromfile(bake_base/'bake-triangles.bin','<f4').reshape(-1,3,3);oldcast=np.fromfile(bake_base/'bake-casters.bin','u1')
    if len(oldtri)!=first_tri:raise ValueError('Bake caster snapshot does not cover the current scene')
    source=np.load(BACKUP/'scene.npz');sn=source['names'];smi=source['material'];source.close()
    # Earlier incremental bakes retain their original ordering and already
    # suppress temporary covers. Only the baseline bake is material-grouped.
    if bake_base==OUT:
        source_order=np.concatenate([np.flatnonzero(smi==i) for i in range(len(sn))]);barriers=np.array(['start_barrier' in str(name).lower() for name in sn])[smi][source_order];oldcast[barriers]=0
    oldjobs=np.zeros(len(oldtri),JOB);oldjobs['uv']=-10
    np.concatenate((oldtri,ordered[:,:,:3])).astype('<f4').tofile(WORK/'bake-triangles.bin')
    np.concatenate((oldjobs,jobs)).tofile(WORK/'bake-jobs.bin');np.concatenate((oldcast,casts)).tofile(WORK/'bake-casters.bin')
    # The retained bakers were linked against this MinGW runtime. Git's own
    # mingw64 libstdc++ on PATH fails to load them (0xC0000139).
    env=dict(os.environ);mingw=Path('C:/ProgramData/mingw64/mingw64/bin')
    if mingw.is_dir():env['PATH']=str(mingw)+os.pathsep+env.get('PATH','')
    for exe,args in [(sun_executable or 'bake_phase_environment.exe',[WORK/'bake-triangles.bin',WORK/'bake-jobs.bin',WORK/'sun.bin',2048,2048,1,WORK/'bake-casters.bin',*(sun_direction or [])]),
                     ('bake_interior_lighting.exe',[WORK/'bake-triangles.bin',WORK/'bake-jobs.bin',OUT/'fixtures.bin',WORK/'local.bin',2048,2048,1,WORK/'bake-casters.bin'])]:
        subprocess.run([str(ROOT/'tools'/exe),*map(str,args)],check=True,env=env)
    patch_lightmaps(buf,jobs)
    append_collision(buf,col)
    count=len(buf[0x50])//28;struct.pack_into('<2I',buf[0xe],24,0,count)
    buf[0x77],buf[0x78],buf[0x79]=map(bytearray,build_camera_visibility(buf[0x51],np.arange(count,dtype='<u2').tobytes()))
    struct.pack_into('<3I',buf[0x7b],0,count,count,count)
    shadow_count=len(buf[0x7f])//12
    for at in (0,36):struct.pack_into('<i',buf[5],at+20,shadow_count)
    struct.pack_into('<i',buf[5],36+8,shadow_count)
    buf.update(reorder(buf)[0]);validate_index_padding(buf[0x50],buf[0x4f],buf[0x52])
    temp=MAP.with_suffix('.details.bsp');compact(MAP,temp,buf);proof=enforce_camera_bypass_budget(temp)
    if proof['native_padded_indices']>=3145728*index_fraction or proof['static_batch_runs']>=512:raise ValueError('Conservative budget exceeded')
    os.replace(temp,MAP)
    persist_scene(data,mi,names,plan)
    previous=json.loads((BACKUP/'source-build.json').read_text())['version']
    plan.update(draw_budget=proof,lighting='New 4x4 charts ray-baked against the full scene; old charts and character probes retained at append time',previous_version=previous)
    (WORK/'result.json').write_text(json.dumps(plan,indent=2))
    print(json.dumps(dict(added_props=plan['added_props'],added_triangles=plan['added_triangles'],draw_budget=proof),indent=2),flush=True)

def patch_lightmaps(buf,jobs):
    from light_composite import LOCAL
    from scipy.ndimage import distance_transform_edt
    values=np.fromfile(WORK/'sun.bin','<f4').reshape(2048,2048,5);local=np.fromfile(WORK/'local.bin',LOCAL).reshape(2048,2048)
    mask=np.fromfile(WORK/'sun.bin.mask','u1').reshape(2048,2048)
    # Expand each triangle's own baked texels only within its 4x4 chart.
    old_sky=np.frombuffer(buf[0x62],'u1').reshape(4,2,2048,2048,4)
    for job in jobs:
        x=int(job['uv'][0,0]//4)*4;y=int(job['uv'][0,1]//4)*4
        # Geometric receiver occupies six texels; extend nearest valid inside
        # the same chart, keeping unrelated and old chart texels unchanged.
        valid=mask[y:y+4,x:x+4].astype(bool)
        if not valid.any():raise ValueError('New chart has no baked receiver pixels')
        nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True)
        v=values[y:y+4,x:x+4][tuple(nearest)];loc=local[y:y+4,x:x+4][tuple(nearest)]
        ambient=np.array([.09,.10,.12])*(.65+.35*np.maximum(v[...,1,None],0))+loc['fill']
        old_sky[3,0,y:y+4,x:x+4]=encode_rgbm(ambient)
        bent=np.empty((4,4,4),'u1');bent[...,:3]=np.rint(np.clip((v[...,2:5]+1)/2.007874,0,1)*255).astype('u1');bent[...,3]=255;old_sky[3,1,y:y+4,x:x+4]=bent
        offset=3*(2048*2048*8+1024*1024*4);ids=np.ndarray((2048,2048),'<u4',buffer=buf[0x69],offset=offset);vis=np.ndarray((2048,2048,4),'u1',buffer=buf[0x69],offset=offset+2048*2048*4)
        ids[y:y+4,x:x+4]=loc['ids'];vis[y:y+4,x:x+4]=loc['vis'];vis[y:y+4,x:x+4,0]=np.rint(v[...,0]*255).astype('u1')

def append_collision(buf,col):
    # Primitives already disabled in the grid (e.g. replaced source colliders)
    # must stay disabled: only previously active and newly appended ones are gridded.
    from build_center_detail import active
    grid=({k:bytes(buf[k]) for k in (0x57,0x59)} if 0x57 in buf and 0x59 in buf else __import__('repair_preview_index_padding').read_lumps(MAP,(0x57,0x59)))
    previously=active(grid);first_new=len(buf[0x45])//44
    good=np.linalg.norm(np.cross(col[:,1]-col[:,0],col[:,2]-col[:,0]),axis=1)>1e-5;col=col[good]
    centers=col.mean(1);order=np.lexsort((centers[:,2],centers[:,1],centers[:,0]));col=col[order]
    encoded,bounds=encode([col[i:i+96] for i in range(0,len(col),96)])
    vertexbase=len(buf[3])//12;wordbase=len(buf[0x42])//4;nodebase=len(buf[0x44])//16
    # Header encoders are relocatable, including node/triangle stream offsets.
    for at in range(0,len(encoded[0x45]),44):
        header=list(struct.unpack_from('<6h4i4f',encoded[0x45],at));header[6]+=vertexbase;header[7]+=wordbase;header[8]+=nodebase
        buf[0x45].extend(struct.pack('<6h4i4f',*header))
    for key in (3,0x42,0x44,0x60):buf[key].extend(encoded[key])
    # Rebuild the spatial grid over every old and appended triangle header.
    allbounds=[]
    positions=np.frombuffer(buf[3],'<f4').reshape(-1,3);words=np.frombuffer(buf[0x42],'<u4')
    for h in struct.iter_unpack('<6h4i4f',buf[0x45]):
        w=words[h[7]:h[7]+h[4]];ix=w&1023
        faces=positions[h[6]+np.stack((ix,ix+(w>>10&127),ix+(w>>17&127)),1)]
        allbounds.append((faces.min((0,1)).tolist(),faces.max((0,1)).tolist()))
    brush=[]
    for r in struct.iter_unpack('<3f2BH3fI',buf[0x5c]):brush.append(([r[i]-r[i+6] for i in range(3)],[r[i]+r[i+6] for i in range(3)]))
    keep_b=[i for i in range(len(brush)) if (0,i) in previously]
    keep_t=[i for i in range(len(allbounds)) if (0x40,i) in previously or i>=first_new]
    if len(keep_b)==len(brush) and len(keep_t)==len(allbounds):buf.update(collision_grid(brush,allbounds))
    else:
        from extend_prop_collision import pack_grid
        g=pack_grid([brush[i] for i in keep_b]+[allbounds[i] for i in keep_t]);off=len(keep_b);p=bytearray(g[0x59]);sets=bytearray(g[0x57])
        def remap(word):
            k=(word>>8)&65535
            return (keep_b[k]<<8)|(word&255) if k<off else (0x40<<24)|(keep_t[k-off]<<8)|(word&255)
        for at in range(0,len(p),4):struct.pack_into('<I',p,at,remap(struct.unpack_from('<I',p,at)[0]))
        for at in range(0,len(sets),8):
            if struct.unpack_from('<H',sets,at+2)[0]==1:struct.pack_into('<I',sets,at+4,remap(struct.unpack_from('<I',sets,at+4)[0]))
        g[0x59]=p;g[0x57]=sets;buf.update(g)
    report=json.loads((OUT/'physics.json').read_text());report.update(triangles=report['triangles']+len(col),triangle_headers=len(buf[0x45])//44,detail_collision_triangles=len(col))
    report['owners'].extend(dict(index=p['index'],model=p['model'],method=p['collision_recovery'],brushes=0,headers=(p['collision_triangles']+95)//96) for p in json.loads((WORK/'plan.json').read_text())['placements'] if p['collision_triangles'])
    temp=OUT/'physics.detail.json';temp.write_text(json.dumps(report,indent=2));os.replace(temp,OUT/'physics.json')
    # Keep canonical cache positions indexed exactly as in the current BSP.
    old=np.load(OUT/'physics.npz');changes={int(k):old[k] for k in old.files};old.close()
    for key in (3,0x42,0x44,0x45,0x55,0x56,0x57,0x58,0x59,0x5a,0x60,0x61):
        if key in buf:changes[key]=np.frombuffer(buf[key],'u1')
    temp=OUT/'physics.detail.npz';np.savez(temp,**{str(k):v for k,v in changes.items()});os.replace(temp,OUT/'physics.npz')

def persist_scene(data,mi,names,plan):
    old=np.load(BACKUP/'scene.npz');tri=old['triangles'];oldmi=old['material'];oldnames=list(old['names']);old.close()
    newnames=oldnames+[n for n in names if n not in oldnames];newmi=np.asarray([newnames.index(names[i]) for i in mi],'i4')
    temp=OUT/'scene.detail.npz';np.savez(temp,triangles=np.concatenate((tri,data)),material=np.concatenate((oldmi,newmi)),names=np.asarray(newnames));os.replace(temp,OUT/'scene.npz')
    scene=json.loads((OUT/'scene.json').read_text());added={p['index'] for p in plan['placements']};scene['placements'].extend(plan['placements']);scene['omitted']=[p for p in scene['omitted'] if p['index'] not in added];scene['props']=len(scene['placements']);scene['triangles']+=len(data)
    scene[WORK.name.replace('-','_')]=dict(added_props=plan['added_props'],added_triangles=len(data),plan=(WORK.relative_to(OUT)/'result.json').as_posix())
    temp=OUT/'scene.detail.json';temp.write_text(json.dumps(scene,indent=2));os.replace(temp,OUT/'scene.json')

if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'plan'
    if action=='plan':plan()
    elif action=='materials':snapshot();stage_materials()
    elif action=='append':append()
    else:raise ValueError('Unknown action')
