"""Replace only the two prototype paths with lit, colliding industrial catwalks."""
import collections,json,math,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
import xatlas
from scipy.ndimage import distance_transform_edt
from optimize_portalfree_render import DT,material_name,CAMERA_MIN,CAMERA_MAX,LOCAL_PAD
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from native_triangle_collision import encode
from repair_tunnel_passages import remap_grid
from rebuild_local_visibility import make_tree
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from apply_baked_lighting import encode_rgbm,tangents
from apply_interior_lighting import LOCAL_DTYPE

P=ROOT/'output/phase-runner'
SOURCE=P/'preview-portalfree-optimized/mp_phase_runner_preview.bsp'
TARGET=P/'phase-runner-catwalks/mp_phase_runner.bsp'
BAKE=P/'catwalk-lighting'
OLD_REPORT=P/'preview-tunnel-walkways/tunnel-walkways.json'

def face_key(face):return b''.join(sorted(bytes(p) for p in np.asarray(face,dtype='<f4').view('V12').reshape(3)))

def mesh_faces(l):
    v=np.frombuffer(l[0x49],DT);p=np.frombuffer(l[3],'<f4').reshape(-1,3)
    ix=np.frombuffer(l[0x4f],'<u2');sorts=list(struct.iter_unpack('<3hHI',l[0x52]))
    for mi,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
        raw=ix[r[0]:r[0]+r[1]*3].reshape(-1,3);ids=sorts[r[-2]][4]+raw.astype('<u4')
        yield mi,r,raw,ids,p[v['pi'][ids]]

def old_path_keys():
    report=json.loads(OLD_REPORT.read_text());old=read_lumps(OLD_REPORT.with_name('mp_phase_runner_preview.bsp'),(3,0x49,0x4f,0x50,0x52))
    keys=collections.Counter(face_key(t) for mi,r,raw,ids,tri in mesh_faces(old) if mi>=report['first_mesh'] for t in tri)
    if sum(keys.values())!=report['triangles']:raise ValueError('Old walkway provenance differs')
    return keys,report

def new_geometry(routes):
    faces=[];uv=[];kind=[];details=[]
    def quad(q,mat,width,height):
        q=np.array(q,dtype='<f4');u=np.array([[0,0],[width/64,0],[width/64,height/64],[0,height/64]],dtype='<f4')
        for ids in ((0,1,2),(0,2,3)):faces.append(q[list(ids)]);uv.append(u[list(ids)]);kind.append(mat)
    def box(a,b,halfwidth,height,mat):
        a=np.array(a);b=np.array(b);d=b-a;side=np.array([-d[1],d[0],0.]);side/=np.linalg.norm(side)
        q=np.array([a-side*halfwidth,b-side*halfwidth,b+side*halfwidth,a+side*halfwidth]);bottom=q-[0,0,height]
        length=np.linalg.norm(d)
        quad(q,mat,length,halfwidth*2);quad(bottom[::-1],mat,length,halfwidth*2)
        for j in range(4):k=(j+1)%4;quad([q[j],bottom[j],bottom[k],q[k]],mat,np.linalg.norm(q[k]-q[j]),height)
    for ri,r in enumerate(routes):
        p=np.array(r['points']);t=np.gradient(p,axis=0);side=np.column_stack((-t[:,1],t[:,0],np.zeros(len(t))));side/=np.linalg.norm(side,axis=1)[:,None]
        left=p+side*40;right=p-side*40
        for i in range(len(p)-1):
            q=np.array([left[i],right[i],right[i+1],left[i+1]]);bottom=q-[0,0,4];length=np.linalg.norm(p[i+1]-p[i])
            quad(q,0,80,length);quad(bottom[::-1],1,80,length)
            for j,k in ((3,0),(1,2)):quad([q[j],bottom[j],bottom[k],q[k]],1,length,4)
        for j in (0,-1):
            q=np.array([left[j],right[j],right[j]-[0,0,4],left[j]-[0,0,4]])
            quad(q[::-1] if j==0 else q,1,80,4)
        distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        samples=np.linspace(64,distance[-1]-64,max(2,math.ceil((distance[-1]-128)/96)+1))
        rp=np.array([[np.interp(s,distance,p[:,k]) for k in range(3)] for s in samples])
        rt=np.gradient(rp,axis=0);rs=np.column_stack((-rt[:,1],rt[:,0],np.zeros(len(rt))));rs/=np.linalg.norm(rs,axis=1)[:,None]
        for sign in (-1,1):
            edge=rp+rs*sign*37
            for i in range(len(edge)-1):
                for z in (22,42):box(edge[i]+[0,0,z],edge[i+1]+[0,0,z],1.5,3,2)
                box(edge[i]-[0,0,1],edge[i+1]-[0,0,1],2,9,1)
            for c,s in zip(edge,rs):
                along=np.array([s[1],-s[0],0.]);box(c-along*1.5+[0,0,42],c+along*1.5+[0,0,42],1.5,42,2)
        for c,s in zip(rp,rs):box(c-s*38-[0,0,4],c+s*38-[0,0,4],2,8,1)
        details.append(dict(route=ri,rail_station_points=rp.tolist(),rail_sides=rs.tolist(),stations=len(rp),length=float(distance[-1]),
            clear_width=71,deck_width=80,deck_thickness=4,top_rail_height=42,rail_spacing_max=96,open_entry_exit_length=64))
    f=np.asarray(faces,'<f4');u=np.asarray(uv,'<f4');k=np.array(kind,np.int32)
    n=np.cross(f[:,1]-f[:,0],f[:,2]-f[:,0]);ok=np.linalg.norm(n,axis=1)>1e-5
    return f[ok],u[ok],k[ok],details

def retain_scene(l,keys):
    remaining=keys.copy();meshes=bytearray();indices=bytearray();bounds=bytearray();scene=[];caster=[];mapping=[];removed=0
    for mi,r,raw,ids,tri in mesh_faces(l):
        take=[]
        for j,t in enumerate(tri):
            key=face_key(t)
            if remaining[key]>0:remaining[key]-=1;removed+=1
            else:take.append(j)
        if not take:continue
        selected=raw[take];record=bytearray(l[0x50][mi*28:mi*28+28]);first=len(indices)//2;flat=selected.ravel()
        struct.pack_into('<I3H',record,0,first,len(take),int(flat.min()),int(flat.max()-flat.min()));meshes.extend(record);indices.extend(flat.tobytes())
        if len(take)&1:indices.extend(struct.pack('<3H',*[int(flat[-1])]*3))
        if len(take)==len(tri):bounds.extend(l[0x51][mi*32:mi*32+32])
        else:
            xyz=tri[take];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;bounds.extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
        mapping.append(dict(source_mesh=mi,retained_triangles=take))
        scene.extend(tri[take][:,[0,2,1]])
        sort=struct.unpack_from('<h',l[0x52],r[-2]*12)[0];caster.extend([not material_name(l,sort).endswith('/phase_runner_sky')]*len(take))
    if any(remaining.values()) or removed!=sum(keys.values()):raise ValueError('Old path not matched exactly')
    return {0x50:meshes,0x4f:indices,0x51:bounds},np.asarray(scene,'<f4'),np.asarray(caster,np.uint8),mapping,removed

def bake_catwalks(scene,casters,newtri,corner_normals=None,new_casters=None):
    BAKE.mkdir(parents=True,exist_ok=True);norm=np.cross(newtri[:,1]-newtri[:,0],newtri[:,2]-newtri[:,0]);norm/=np.linalg.norm(norm,axis=1)[:,None]
    normals=np.broadcast_to(norm[:,None,:],newtri.shape) if corner_normals is None else np.asarray(corner_normals,dtype='<f4')
    if normals.shape!=newtri.shape or not np.all(np.isfinite(normals)) or not np.allclose(np.linalg.norm(normals,axis=2),1,atol=1e-5):
        raise ValueError('Invalid authored corner normals')
    points=newtri.reshape(-1,3);attrs=np.column_stack((points,normals.reshape(-1,3)))
    _,first,inverse=np.unique(np.round(attrs*10000).astype(np.int64),axis=0,return_index=True,return_inverse=True)
    atlas=xatlas.Atlas();atlas.add_mesh(points[first],inverse.reshape(-1,3).astype(np.uint32),normals=attrs[first,3:].astype(np.float32))
    chart=xatlas.ChartOptions();chart.max_iterations=1;pack=xatlas.PackOptions();pack.resolution=512;pack.texels_per_unit=.035;pack.padding=2;pack.rotate_charts=True
    atlas.generate(chart,pack);vm,fi,uv=atlas[0]
    if not np.array_equal(vm[fi],inverse.reshape(-1,3)):raise ValueError('New atlas reordered corners')
    page=np.empty(len(newtri),np.int32)
    for i in range(atlas.chart_count):c=atlas.get_mesh_chart(0,i);page[np.array(c.faces,dtype=np.int64)]=c.atlas_index
    # Pack the small charts into 1024 pages, preserving their original gutters.
    faceuv=(uv[fi]+np.stack((page%2,(page%4)//2),axis=1)[:,None,:])/2;page=page//4;w=atlas.width*2;h=atlas.height*2;pages=(atlas.atlas_count+3)//4
    if max(w,h)>2048 or pages>8:raise ValueError('Catwalk lightmap budget exceeded')
    added_mask=np.ones(len(newtri),np.uint8) if new_casters is None else np.asarray(new_casters,np.uint8)
    if added_mask.shape!=(len(newtri),) or not np.all((added_mask==0)|(added_mask==1)):raise ValueError('Invalid new shadow caster mask')
    alltri=np.concatenate((scene,newtri));alltri.tofile(BAKE/'triangles.bin');mask=np.r_[casters,added_mask];mask.tofile(BAKE/'casters.bin')
    jd=np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')]);jobs=np.zeros(len(alltri),jd)
    jobs['page']=-1;jobs['p']=alltri;jobs['p'][len(scene):]=newtri;jobs['n'][len(scene):]=normals;jobs['uv'][len(scene):]=faceuv*np.array([w,h]);jobs['page'][len(scene):]=page
    jobs.tofile(BAKE/'jobs.bin');np.savez(BAKE/'atlas.npz',uv=faceuv,page=page,width=w,height=h,pages=pages)
    commands=[('sun',ROOT/'tools/bake_phase_environment.exe',[BAKE/'triangles.bin',BAKE/'jobs.bin',BAKE/'sun.bin',w,h,pages,BAKE/'casters.bin']),
      ('local',ROOT/'tools/bake_interior_lighting.exe',[BAKE/'triangles.bin',BAKE/'jobs.bin',P/'interior-lighting/lights.bin',BAKE/'local.bin',w,h,pages,BAKE/'casters.bin'])]
    for name,exe,args in commands:
        with (BAKE/(name+'.log')).open('w') as out:subprocess.run([str(exe),*map(str,args)],stdout=out,stderr=subprocess.STDOUT,check=True)
        print((BAKE/(name+'.log')).read_text(),flush=True)
    sunlight=np.fromfile(BAKE/'sun.bin','<f4').reshape(pages,h,w,5);valid=np.fromfile(BAKE/'sun.bin.mask',np.uint8).reshape(pages,h,w).astype(bool)
    local=np.fromfile(BAKE/'local.bin',LOCAL_DTYPE).reshape(pages,h,w);headers=bytearray();sky=bytearray();rtl=bytearray();lit=0
    for k in range(pages):
        if not valid[k].any():raise ValueError('Empty new lightmap page')
        nearest=distance_transform_edt(~valid[k],return_distances=False,return_indices=True);values=sunlight[k][tuple(nearest)];lv=local[k][tuple(nearest)]
        ambient=np.array([.025,.027,.032])*(.4+.6*np.maximum(values[...,1,None],0))+lv['fill'];a=encode_rgbm(ambient);b=np.empty((h,w,4),np.uint8)
        b[...,:3]=np.rint(np.clip((values[...,2:5]+1)/2.007874,0,1)*255).astype(np.uint8);b[...,3]=255;sky.extend(a.tobytes());sky.extend(b.tobytes())
        ids=np.full((h,w),0x00ffffc0,'<u4');vis=np.zeros((h,w,4),np.uint8);vis[...,0]=np.rint(np.clip(values[...,0],0,1)*255).astype(np.uint8)
        active=lv['vis'][...,1:].any(-1);ids[active]=(ids[active]&0xff00003f)|(lv['ids'][active]&0x00ffffc0);vis[...,1:][active]=lv['vis'][...,1:][active]
        rtl.extend(ids.tobytes());rtl.extend(vis.tobytes());rtl.extend(bytes((w//2)*(h//2)*4));headers.extend(struct.pack('<I2H',1,w,h));lit+=int((active&valid[k]).sum())
    return faceuv,page,norm,{0x53:headers,0x62:sky,0x69:rtl},dict(pages=pages,width=w,height=h,valid_luxels=int(valid.sum()),local_lit_luxels=lit,
        old_lightmaps_byte_preserved=True,static_sun_sky_and_existing_30_point_lights_baked=True)

def visibility(l,bounds,routes):
    boxes=[];envelopes=[]
    for r in routes:
        p=np.array(r['points']);envelopes.append((p.min(0)-[320,320,512],p.max(0)+[320,320,384]))
    lo=np.min([e[0] for e in envelopes],axis=0);hi=np.max([e[1] for e in envelopes],axis=0)
    sorts=list(struct.iter_unpack('<3hHI',l[0x52]));sky=[]
    for mi,(m,r) in enumerate(zip(struct.iter_unpack('<8f',bounds),struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))):
        low=np.minimum(np.array(m[:3])-m[4:7]-LOCAL_PAD,lo);high=np.maximum(np.array(m[:3])+m[4:7]+LOCAL_PAD,hi)
        if material_name(l,sorts[r[-2]][0]).endswith('/phase_runner_sky'):
            sky.append(mi);low=np.minimum(low,CAMERA_MIN);high=np.maximum(high,CAMERA_MAX)
        boxes.append((low.tolist(),high.tolist()))
    nodes,refs,objects=make_tree(boxes,leaf_size=64);changes={0x77:b''.join(nodes),0x78:struct.pack('<'+'H'*len(refs),*refs),0x79:objects}
    return changes,dict(**validate_visibility(changes[0x77],changes[0x78],changes[0x79],bounds),
        all_objects_protected_for_both_tunnel_routes=True,shared_guard=[lo.tolist(),hi.tolist()],sky_meshes=sky,new_portal_connections=0,
        limitation='More conservative traversal while inside either tunnel; frame rate and client rendering need verification.')

def collision(l,newtri,report,position_offset):
    encoded,bounds=encode([newtri[i:i+96] for i in range(0,len(newtri),96)],position_offset)
    oldheaders=list(struct.iter_unpack('<6h4i4f',l[0x45]));first=len(oldheaders)
    for at in range(0,len(encoded[0x45]),44):
        struct.pack_into('<i',encoded[0x45],at+16,struct.unpack_from('<i',encoded[0x45],at+16)[0]+len(l[0x42])//4)
        struct.pack_into('<i',encoded[0x45],at+20,struct.unpack_from('<i',encoded[0x45],at+20)[0]+len(l[0x44])//16)
    words=[w for w, in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
    active={(w>>24,(w>>8)&65535) for w in words};disabled=set(range(report['first_header'],report['first_header']+report['headers']))
    if not {(0x40,i) for i in disabled}<=active:raise ValueError('Original path collision not active')
    brushbounds=[];brushids=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
        if (0,i) in active:c=np.array(r[:3]);e=np.array(r[6:9]);brushbounds.append(((c-e).tolist(),(c+e).tolist()));brushids.append(i)
    p=np.frombuffer(l[3],'<f4').reshape(-1,3);tribounds=[];headerids=[]
    for i,h in enumerate(oldheaders):
        if (0x40,i) in active and i not in disabled:v=p[h[6]:h[6]+h[3]];tribounds.append((v.min(0).tolist(),v.max(0).tolist()));headerids.append(i)
    tribounds.extend(bounds);headerids.extend(range(first,first+len(bounds)))
    changes=remap_grid(brushbounds,tribounds,brushids,headerids)
    changes.update({i:l[i]+encoded[i] for i in (0x42,0x44,0x45,0x60)})
    return changes,encoded[3],dict(disabled_old_path_headers=sorted(disabled),new_first_header=first,new_headers=len(bounds),
        render_matches_new_collision_exactly=True,unrelated_collision_records_byte_preserved=True,unrelated_active_colliders_preserved=True)

def shadows(l,keys,newtri):
    p=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);ix=np.frombuffer(l[0x7e],'<u2');tri=[];at=0;removed=0
    for base,count,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
        if (opaque,sort)!=(1,-1):raise ValueError('Unsupported shadow type')
        for t in p[base+ix[at:at+count*3].astype('<u4')].reshape(-1,3,3):
            if face_key(t) in keys:removed+=1
            else:tri.append(t)
        at+=count*3
    if removed!=sum(keys.values()):raise ValueError('Old path shadow geometry mismatch')
    tri=np.concatenate((np.array(tri,'<f4'),newtri[:,[0,2,1]]));verts=bytearray();indices=bytearray();meshes=bytearray()
    for first in range(0,len(tri),16000):
        p=tri[first:first+16000].reshape(-1,3);_,keep,inverse=np.unique(p.view('V12').ravel(),return_index=True,return_inverse=True)
        meshes.extend(struct.pack('<2I2h',len(verts)//12,len(p)//3,1,-1));verts.extend(p[keep].tobytes());indices.extend(inverse.astype('<u2').tobytes())
    env=bytearray(l[5]);count=len(meshes)//12;struct.pack_into('<i',env,20,count);struct.pack_into('<i',env,44,count);struct.pack_into('<i',env,56,count)
    return {5:env,0x7c:verts,0x7e:indices,0x7f:meshes},dict(removed_old_path_triangles=removed,new_shadow_meshes=count,new_shadow_triangles=len(tri))

def build():
    start=time.monotonic();TARGET.parent.mkdir(parents=True,exist_ok=True)
    l=read_lumps(SOURCE,(2,3,5,0x1e,0x2b,0x2c,0xe,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x57,0x59,0x7c,0x7e,0x7f))
    keys,oldreport=old_path_keys();routes=oldreport['routes'];newtri,uv,kinds,details=new_geometry(routes)
    np.savez(TARGET.with_name('catwalk-geometry.npz'),triangles=newtri,uv=uv,kinds=kinds)
    changes,scene,casters,mapping,removed=retain_scene(l,keys)
    print(f'Replaced old path {removed} triangles; new catwalk {len(newtri)} triangles',flush=True)
    lightuv,page,norm,light,lightreport=bake_catwalks(scene,casters,newtri)
    buffers={i:bytearray(changes.get(i,l[i])) for i in (3,0x1e,0x49,0x4f,0x50,0x51,0x52,0xe,0x7b)}
    texids=[]
    for name in ('boomtown_solid_grate_01','trim_metal_01','trim_metal_01_yellow'):
        texids.append(next(i for i in range(len(l[2])//36) if material_name(l,i).endswith('/'+name)))
    n=np.broadcast_to(norm[:,None,:],newtri.shape);tan,mirror=tangents(newtri,n,uv);first_new_mesh=len(buffers[0x50])//28;oldpages=len(l[0x53])//8
    for mat in range(3):
        for pg in np.unique(page[kinds==mat]):
            selection=np.flatnonzero((kinds==mat)&(page==pg))
            for at in range(0,len(selection),128):
                sel=selection[at:at+128];base=len(buffers[0x49])//44;first=len(buffers[0x4f])//2
                for ti in sel:
                    for j in range(3):
                        pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12;buffers[3].extend(newtri[ti,j].tobytes());buffers[0x1e].extend(np.array([norm[ti],tan[ti,j]],'<f4').tobytes())
                        buffers[0x49].extend(struct.pack('<2I2f4B4f2I',pi,ni,*uv[ti,j],255,255,255,255,*lightuv[ti,j],0,0,(ni+1)|(int(mirror[ti,j])<<31),0))
                raw=np.arange(len(sel)*3,dtype='<u2').reshape(-1,3)[:,[0,2,1]];buffers[0x4f].extend(raw.tobytes())
                if len(sel)&1:buffers[0x4f].extend(struct.pack('<3H',*[int(raw[-1,-1])]*3))
                r=bytearray(l[0x50][:28]);struct.pack_into('<I3H',r,0,first,len(sel),0,len(sel)*3-1);struct.pack_into('<H',r,22,len(buffers[0x52])//12);buffers[0x50].extend(r)
                buffers[0x52].extend(struct.pack('<3hHI',texids[mat],oldpages+int(pg),-1,len(sel)*3-1,base));xyz=newtri[sel];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;buffers[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    newcol,colpos,colreport=collision(l,newtri,oldreport,len(buffers[3])//12);buffers[3].extend(colpos);buffers.update(newcol)
    buffers.update({i:l[i]+light[i] for i in (0x53,0x62,0x69)})
    count=len(buffers[0x50])//28;struct.pack_into('<I',buffers[0xe],28,count);struct.pack_into('<3I',buffers[0x7b],0,count,count,count)
    merged={**l,**buffers};vchanges,vproof=visibility(merged,buffers[0x51],routes);buffers.update(vchanges)
    schanges,sproof=shadows(l,keys,newtri);buffers.update(schanges)
    validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52]);compaction=compact(SOURCE,TARGET,buffers);budget=audit(TARGET)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Catwalk draw budget exceeded')
    report=dict(version='0.1.37',map_name='mp_phase_runner',source_version='0.1.36',removed_old_path_triangles=removed,new_catwalk_triangles=len(newtri),
        first_new_mesh=first_new_mesh,new_meshes=count-first_new_mesh,deck_material=texids[0],frame_material=texids[1],rail_material=texids[2],
        routes=routes,catwalk_details=details,collision=colreport,light_bake=lightreport,visibility=vproof,shadow=sproof,budget=budget,
        retained_source_meshes=mapping,compaction=compaction,elapsed_seconds=time.monotonic()-start,client_rendering_verified=False)
    status=json.loads(SOURCE.with_name('source-build.json').read_text());status['catwalk_release']=report;status['render_triangles']=budget['real_triangles'];status['render_repair']['world_meshes']=count;status['world_draw_budget_repair']['after']=budget;status['visibility_rebuild']=vproof
    # The old path report is historical provenance, not the new traversal surface.
    status['tunnel_walkways']['replaced_by']='catwalk_release, version 0.1.37'
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2));TARGET.with_name('catwalks.json').write_text(json.dumps(report,indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    for f in SOURCE.parent.glob(SOURCE.stem+'_*.ent'):shutil.copy2(f,TARGET.parent/f.name.replace(SOURCE.stem,TARGET.stem))
    print(json.dumps({k:v for k,v in report.items() if k not in ('routes','retained_source_meshes','compaction')},indent=2),flush=True)

if __name__=='__main__':build()
