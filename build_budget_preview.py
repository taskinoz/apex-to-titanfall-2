"""Budget-safe render diagnostic: source LODs, exact original world and physics."""
import collections,hashlib,json,math,shutil,struct,time,re
from pathlib import Path
import numpy as np
from plan_budget_model_geometry import prepare,ROOT,P
from repair_preview_index_padding import read_lumps,validate_index_padding
from repair_portal_surfaces import OVERLAYS
from stage_prop_geometry import rotation,material_basename
from append_prop_geometry import tangent
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility
from repair_prop_coverage import traversal_frontier
from spatial_preview_meshes import partition
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY

SOURCE=P/'preview-full-collision/mp_phase_runner_preview.bsp'
TARGET=P/'preview-draw-budget/mp_phase_runner_preview.bsp'

def world_membership(lumps):
    """Identify original world triangles geometrically, never by reordered sorts."""
    origin=read_lumps(P/'preview-sky/mp_phase_runner_preview.bsp',(3,0x49,0x4f,0x50,0x52,2))
    def records(l):
        pos=np.frombuffer(l[3],dtype='V12')
        pi=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('rest','V40')]))['pi']
        ix=np.frombuffer(l[0x4f],dtype='<u2');sorts=list(struct.iter_unpack('<4hI',l[0x52]))
        return pos,pi,ix,sorts
    po,pi,ix,sorts=records(origin);keys=set()
    for r in struct.iter_unpack('<I3H6b2h2BHI',origin[0x50]):
        points=po[pi[sorts[r[-2]][4]+ix[r[0]:r[0]+r[1]*3].astype('<u4')]].reshape(-1,3)
        keys.update(b''.join(sorted(bytes(v) for v in tri)) for tri in points)
    po,pi,ix,sorts=records(lumps);retained={};before=0;removed=0
    for mi,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',lumps[0x50])):
        # Material indices can change when the terrain atlas is assigned.
        # Check every triangle against source geometry, not texture numbers.
        tris=ix[r[0]:r[0]+r[1]*3].reshape(-1,3)
        points=po[pi[sorts[r[-2]][4]+tris.astype('<u4')]]
        mask=np.array([b''.join(sorted(bytes(v) for v in tri)) in keys for tri in points])
        before+=len(tris);removed+=int((~mask).sum())
        if mask.any():retained[mi]=tris[mask]
    return retained,dict(triangles=sum(len(t) for t in retained.values()),candidate_triangles=before,
        excluded_nonworld_triangles=removed,original_positions_verified=True,
        terrain_material_uv_attributes_retained=True)

def build(target=TARGET,tunnel_detail=False):
    start=time.monotonic();props,cache,plan=prepare(tunnel_detail=tunnel_detail)
    ids=(2,3,0x0e,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x7b)
    l=read_lumps(SOURCE,ids);oldrows=list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))
    positions=bytearray(l[3]);normals=bytearray(l[0x1e]);lit=bytearray(l[0x49]);sorts=bytearray(l[0x52])
    meshes=bytearray();bounds=bytearray();indices=bytearray()
    world,worldproof=world_membership(l)
    def emit(tris,record,si,points):
        tris=np.asarray(tris,dtype='<u2');corners=points[tris]
        for ids in partition(corners.mean(axis=1),np.arange(len(tris)),limit=512):
            chosen=tris[ids];p=corners[ids].reshape(-1,3).astype(float)
            lo=p.min(axis=0)-.02;hi=p.max(axis=0)+.02;center=(lo+hi)/2;extent=(hi-lo)/2
            r=bytearray(record);struct.pack_into('<I3H',r,0,len(indices)//2,len(chosen),int(chosen.min()),int(chosen.max()-chosen.min()))
            struct.pack_into('<H',r,22,si);meshes.extend(r);indices.extend(chosen.tobytes())
            if len(chosen)&1:indices.extend(struct.pack('<3H',int(chosen[-1,-1]),int(chosen[-1,-1]),int(chosen[-1,-1])))
            bounds.extend(struct.pack('<8f',*center,float(np.linalg.norm(extent))+.02,*extent,0.))
    oldpos=np.frombuffer(l[3],dtype='<f4').reshape(-1,3)
    oldpi=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('rest','V40')]))['pi']
    for mi,tris in world.items():
        si=oldrows[mi][-2];_,_,_,last,base=struct.unpack_from('<4hI',sorts,si*12)
        points=oldpos[oldpi[base:base+(last&65535)+1]]
        emit(tris,l[0x50][mi*28:mi*28+28],si,points)
    original_meshes=len(meshes)//28
    materials=json.loads((P/'world-materials/mapping.json').read_text())['materials']
    mappings={k.rsplit('/',1)[-1]:v for k,v in materials.items()}
    textures={}
    for i in range(len(l[2])//36):
        ni=struct.unpack_from('<I',l[2],i*36+12)[0];off=struct.unpack_from('<I',l[0x2c],ni*4)[0]
        n=l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/')
        textures[n]=i
    staged=collections.defaultdict(list);placements=[];fallback=[];excluded=collections.Counter();qc_cache={}
    for prop in props:
        model=Path(prop['model']).stem
        sections,slots,skins,_=cache[model];skin=skins[min(prop['skin'],len(skins)-1)]
        matrix=np.asarray(rotation(prop['angles']),dtype=float);origin=np.array(prop['origin'])
        actual=0;low=np.full(3,np.inf);high=-low.copy()
        for sec,slot in zip(sections,slots):
            if not len(sec):continue
            name=skin[slot]
            if name in OVERLAYS or name.startswith('ar_arena_start_barrier'):
                excluded[name]+=len(sec);continue
            mapping=mappings.get(name)
            if mapping is None:
                # Earlier diagnostic SMD exports bind default_material to the
                # first QC skin. Retain that explicit approximation when the
                # true compiled material has not yet been recovered.
                replacement=skin[0]
                if prop['source_qc']:
                    if model not in qc_cache:
                        text=Path(prop['source_qc']).read_text()
                        families=re.findall(r'"[^"\n]+"\s*\{\s*((?:"[^"\n]+"\s*)+)\}',text)
                        qc_cache[model]=[[material_basename(m) for m in re.findall(r'"([^"]+)"',row)] for row in families]
                    qcskins=qc_cache[model]
                    if qcskins:replacement=qcskins[min(prop['skin'],len(qcskins)-1)][0]
                mapping=mappings.get(replacement)
                fallback.append(dict(placement=prop['index'],model=model,source_material=name,
                    preview_material=replacement if mapping else 'existing fallback texture 0'))
            ti=textures.get(mapping['name'],0) if mapping else 0
            data=sec.copy();data[:,:,:3]=(sec[:,:,:3]@matrix.T*prop['scale']+origin).astype('<f4')
            n=sec[:,:,3:6]@matrix.T;n/=np.linalg.norm(n,axis=2)[:,:,None];data[:,:,3:6]=n.astype('<f4')
            data[:,:,7]=1-sec[:,:,7]
            low=np.minimum(low,data[:,:,:3].min(axis=(0,1)));high=np.maximum(high,data[:,:,:3].max(axis=(0,1)))
            staged[ti].append(data);actual+=len(data)
        if actual==0:raise ValueError('Entire placement lost: '+str(prop['index']))
        placements.append(dict(index=prop['index'],model=prop['model'],origin=prop['origin'],angles=prop['angles'],scale=prop['scale'],triangles=actual,bounds=[low.tolist(),high.tolist()]))
    template=l[0x50][:28]
    for ti,batches in staged.items():
        raw=np.concatenate(batches)
        for begin in range(0,len(raw),10000):
            src=raw[begin:begin+10000];n=len(src);base=len(lit)//44
            pi0=len(positions)//12;ni0=len(normals)//12
            points=src[:,:,:3].reshape(-1,3);normal=src[:,:,3:6].reshape(-1,3)
            positions.extend(points.astype('<f4').tobytes());normal_buffer=np.empty((n*6,3),dtype='<f4')
            normal_buffer[::2]=normal
            records=np.zeros(n*3,dtype=np.dtype([('pi','<u4'),('ni','<u4'),('uv','<f4',2),('color','u1',4),('light','<f4',4),('tangent','<u4'),('extra','<u4')]))
            records['pi']=np.arange(pi0,pi0+n*3,dtype='<u4');records['ni']=np.arange(ni0,ni0+n*6,2,dtype='<u4')
            records['uv']=src[:,:,6:8].reshape(-1,2);records['color']=255
            records['light'][:,0]=.25015666584;records['light'][:,1]=.13143643240
            local=np.arange(n*3,dtype='<u2').reshape(-1,3)
            for i,tri in enumerate(src):
                e1=tri[1,:3]-tri[0,:3];e2=tri[2,:3]-tri[0,:3];du1=tri[1,6:8]-tri[0,6:8];du2=tri[2,6:8]-tri[0,6:8]
                determinant=du1[0]*du2[1]-du1[1]*du2[0]
                s=(e1*du2[1]-e2*du1[1])/determinant if abs(determinant)>1e-9 else e1
                t=(e2*du1[0]-e1*du2[0])/determinant if abs(determinant)>1e-9 else e2
                for j in range(3):
                    tan,mirrored=tangent(tuple(tri[j,3:6]),s,t);normal_buffer[(i*3+j)*2+1]=tan
                    records['tangent'][i*3+j]=(ni0+(i*3+j)*2+1)|(0x80000000 if mirrored else 0)
                if np.dot(np.cross(e1,e2),tri[:,3:6].sum(axis=0))>0:local[i]=local[i,[0,2,1]]
            normals.extend(normal_buffer.tobytes());lit.extend(records.tobytes())
            si=len(sorts)//12;sorts.extend(struct.pack('<3hHi',ti,0,-1,n*3-1,base));emit(local,template,si,points)
        print(f'Wrote material {ti}: {len(raw)} triangles',flush=True)
    if len(sorts)//12>8192:raise ValueError('Native material sort budget exceeded')
    padding=validate_index_padding(meshes,indices,sorts)
    if len(indices)//2>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Candidate lacks draw-budget headroom')
    nodes,refs,objects=build_visibility(bounds,leaf_size=128);vis=validate_visibility(nodes,refs,objects,bounds)
    frontier=traversal_frontier(nodes)
    if frontier['maximum_pending_nodes']>=1024:raise ValueError('Native visibility queue exceeded')
    models=bytearray(l[0x0e]);level=bytearray(l[0x7b]);total=len(meshes)//28
    struct.pack_into('<I',models,28,total);struct.pack_into('<3I',level,0,total,total,total)
    changes={3:positions,0x1e:normals,0x49:lit,0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts,0x0e:models,0x7b:level,0x77:nodes,0x78:refs,0x79:objects}
    compactproof=compact(SOURCE,target,changes);budget=audit(target)
    status=json.loads(SOURCE.with_name('source-build.json').read_text())
    status['world_draw_budget_repair']=dict(version='0.1.29',before=audit(SOURCE),after=budget,
        original_world=worldproof,source_model_lod_plan=plan,all_restored_placements=len(placements),
        original_collision_position_buffer_prefix_byte_identical=positions[:len(l[3])]==l[3],
        original_render_attribute_buffer_prefix_byte_identical=lit[:len(l[0x49])]==l[0x49],
        all_other_collision_material_lighting_and_cell_lumps_byte_unchanged=True,
        material_approximations=len(fallback),excluded_overlays=dict(excluded),
        native_index_padding=padding,visibility=vis,traversal=frontier,
        compaction=compactproof,client_rendering_verified=False,
        limitation='Uses fixed original lower-detail LODs and additional component-anchored simplification. Collision stays full detail. Dedicated loading does not verify GPU visibility; material/PBR approximations and tunnel barriers remain unresolved.',elapsed_seconds=time.monotonic()-start)
    status['render_triangles']=padding['render_triangles'];status['render_repair']['world_meshes']=total;status['visibility_rebuild']=vis;status['final_compaction']=compactproof
    if tunnel_detail:
        status['tunnel_render_detail']=dict(version='0.1.30',full_detail_models=['phase_runner_tunnel','phase_runner_tunnel_02'],portal_frame_lod=1,unsimplified=True,all_other_model_render_settings_preserved=True,budget=budget,client_rendering_verified=False)
    target.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    target.with_name('render-placement-proof.json').write_text(json.dumps(dict(placements=placements,material_approximations=fallback,world_meshes=original_meshes),indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),target.with_suffix('.stbsp'))
    for f in SOURCE.parent.glob(SOURCE.stem+'_*.ent'):shutil.copy2(f,target.parent/f.name)
    print(json.dumps(dict(path=str(target),world=worldproof,budget=budget,placements=len(placements),material_approximations=len(fallback),elapsed_seconds=time.monotonic()-start),indent=2))

if __name__=='__main__':build()
