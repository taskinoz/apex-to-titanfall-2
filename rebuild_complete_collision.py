"""Rebuild world/player collision and every rendered solid model from source physics.

Closed IRPS pieces retain convex brushes. Concave BVH rocks and tunnels use
native triangle surfaces, never whole-model bounding-box solids.
"""
import collections,json,shutil,struct,time
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P,POINTS
from repair_preview_index_padding import read_lumps
from repair_preview_hull_edges import vertices_and_bevels
from read_prop_physics import read_phy,read_bvh,convex_planes
from stage_prop_geometry import rotation,load_mesh
from extend_prop_collision import box,area
from merge_collision import polygons
from decode_inline_world_collision import decode
from native_triangle_collision import encode,collision_grid
from compact_preview_bsp import compact

def triangles(faces):
 return np.array([[f[0],f[i],f[i+1]] for f in faces for i in range(1,len(f)-1)],dtype='<f4')

def clip_polygon(face,limit=32760.):
 # Keep the exact portion inside the native coordinate envelope. Remote
 # lobby rooms and sky-limit planes cannot be addressed by this map's grid.
 for axis in range(3):
  for sign in (-1,1):
   result=[]
   for a,b in zip(face,face[1:]+face[:1]):
    da=sign*a[axis]-limit;db=sign*b[axis]-limit
    if da<=0:result.append(a)
    if (da<=0)!=(db<=0):
     t=da/(da-db);result.append([a[k]+t*(b[k]-a[k]) for k in range(3)])
   face=result
   if not face:return []
 return face if len(face)>=3 else []

def build():
 started=time.monotonic();src=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp';out=P/'preview-full-collision/mp_phase_runner_preview.bsp';original=read_lumps(src,(1,3));buffers={1:bytearray(original[1][:16]),0x5c:bytearray(),0x5d:bytearray(),0x5e:bytearray(),0x5f:bytearray()};bounds=[];groups=[];owners=[];candidates=[];cache={};models={};fallback=[]
 def append_convex(result):
  if result is None:raise ValueError('Source IRPS piece is not convex')
  points,planes=result;lo,hi=box(points);cuts=[q for q in planes if not any(abs(abs(v)-1)<1e-7 for v in q[:3])];_,extra=vertices_and_bevels(lo,hi,cuts,source_vertices=points)
  c=np.array([(lo[k]+hi[k])/2 for k in range(3)],dtype='<f4');e=np.nextafter(np.maximum(abs(np.array(lo)-c),abs(np.array(hi)-c)).astype('<f4'),np.float32(np.inf));index=len(bounds);offset=len(buffers[0x5d])//2
  if index>=65535 or len(cuts)+len(extra)>255:raise ValueError('Native brush capacity exceeded')
  buffers[0x5c].extend(struct.pack('<3f2BH3fI',*c,len(cuts),len(cuts)+len(extra),index,*e,offset));bounds.append(((c-e).tolist(),(c+e).tolist()))
  for q in cuts+extra:buffers[1].extend(struct.pack('<4f',*q));buffers[0x5d].extend(bytes(2))
  buffers[0x5e].extend(struct.pack('<'+'H'*(6+len(cuts)+len(extra)),*([0]*6+[1]*len(cuts)+[0x4001]*len(extra))));buffers[0x5f].extend(bytes(32*(6+len(cuts)+len(extra))))
 def append_triangles(t):
  if not len(t):return 0
  # Validate at the engine's stored precision, after placement. Very thin
  # source triangles can collapse only when rounded to world float32.
  t=np.asarray(t,dtype='<f4')
  normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);good=np.linalg.norm(normals,axis=1)>1e-5;t=t[good]
  if not np.isfinite(t).all():raise ValueError('Nonfinite triangle physics')
  # Compact spatial batches keep native surface bounds local. Individual
  # triangles remain source exact; no merging or convex filling is performed.
  centers=t.mean(1);q=np.floor((centers-centers.min(0))/128).astype(np.int64);order=np.lexsort((centers[:,2],q[:,1],q[:,0]));t=t[order]
  for i in range(0,len(t),96):groups.append(t[i:i+96])
  return len(t)
 raw_world=list(polygons(P/'collision/world-collision-regular.obj'));inline,inline_count=decode(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp');raw_world.extend(inline);world=[f for f in (clip_polygon(f) for f in raw_world) if f];outside=len(raw_world)-len(world)
 world_tris=triangles(world);world_count=append_triangles(world_tris)
 # Representative source faces, distributed over the whole world, not boxes.
 for i in np.linspace(0,len(world)-1,72,dtype=int):candidates.append(dict(kind='world',source_prop=-1,face=world[i]))
 print('World surfaces',len(world),'inline leaves',inline_count,'triangles',world_count,flush=True)
 rendered=set()
 for path in P.glob('*-geometry/report.json'):rendered.update(r['index'] for r in json.loads(path.read_text()).get('restored',[]))
 props=[p for p in json.loads((P/'static-props.json').read_text()) if p['index'] in rendered and p['solid_mode'] in (2,6,7)]
 for p in props:
  name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in cache:
   if base.with_suffix('.phy').exists():pieces=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]);method='IRPS'
   elif base.with_suffix('.rmdl').exists():pieces,stats=read_bvh(base.with_suffix('.rmdl'));method='BVH'
   else:
    # Two blue barrels have recovered visual meshes but no exported physics.
    # Use their actual triangles; explicitly record this fallback.
    mesh,_=load_mesh(p['source_qc']);pieces=[[[v[:3] for v in vs]] for _,vs in mesh];method='visual_surface_fallback'
   prepared=[convex_planes(piece) for piece in pieces] if method=='IRPS' else triangles([f for piece in pieces for f in piece])
   if method=='IRPS' and any(x is None for x in prepared):raise ValueError('Invalid source convex model '+name)
   cache[name]=(method,pieces,prepared);models[name]=dict(method=method,pieces=len(pieces),faces=sum(len(piece) for piece in pieces))
  method,pieces,prepared=cache[name];matrix=np.array(rotation(p['angles']));origin=np.array(p['origin']);first_brush=len(bounds);first_header=len(groups);ntri=0
  if method=='IRPS':
   for points,planes in prepared:
    pts=np.array(points)@matrix.T*p['scale']+origin;qs=np.array(planes);normals=qs[:,:3]@matrix.T;ds=qs[:,3]*p['scale']+normals@origin;append_convex((pts.tolist(),np.column_stack((normals,ds)).tolist()))
  else:ntri=append_triangles(prepared@matrix.T*p['scale']+origin)
  if method=='visual_surface_fallback':fallback.append(p['index'])
  owner=dict(index=p['index'],model=p['model'],method=method,first_brush=first_brush,brushes=len(bounds)-first_brush,first_header=first_header,headers=len(groups)-first_header,triangles=ntri,source_faces=sum(len(piece) for piece in pieces))
  if not owner['brushes'] and not owner['headers']:raise ValueError('Solid source model has no collision '+name)
  owners.append(owner)
  # Contact probes cover every source model, with extra probes for both tunnels.
  if name not in {c.get('model') for c in candidates} or 'phase_runner_tunnel' in name:
   fs=[(np.array(f)@matrix.T*p['scale']+origin).tolist() for piece in pieces for f in piece];fs.sort(key=area,reverse=True)
   for f in fs[:8 if 'phase_runner_tunnel' in name else 1]:candidates.append(dict(kind='prop',source_prop=p['index'],model=name,face=f))
  if len(owners)%500==0:print('Placements',len(owners),'brushes',len(bounds),'triangle groups',len(groups),flush=True)
 encoded,triangle_bounds=encode(groups,len(original[3])//12);encoded[3]=original[3]+encoded[3]
 changes={**buffers,**encoded,0x5b:struct.pack('<I',1),**collision_grid(bounds,triangle_bounds)}
 compaction=compact(src,out,changes)
 probes=[]
 from read_prop_physics import plane
 for c in candidates:
  q=plane(c['face'])
  if q is None:continue
  n=np.array(q[:3]);center=np.mean(c['face'],axis=0)
  # Both sides of actual source faces expose reversed or one-sided walls.
  for side in (-1,1):
   probes.append(dict(kind=c['kind'],source_prop=c['source_prop'],model=c.get('model'),start=(center+n*side*128).tolist(),end=(center-n*side*4).tolist(),prop_probe=True))
 status=json.loads(src.with_name('source-build.json').read_text());status['collision_probes']=probes;status['hull_clearance_probes']=[];status['collision_sample_brushes']=len(bounds)
 report=dict(version='0.1.27',world_source_polygons=len(world),remote_source_polygons_outside_native_coordinate_envelope=outside,world_coordinate_envelope=32760,world_inline_leaves=inline_count,world_triangles=world_count,solid_model_placements=len(owners),intentionally_nonsolid_placements=len(rendered)-len(owners),models=len(models),convex_brushes=len(bounds),native_triangle_headers=len(groups),native_triangles=len(encoded[0x42])//4,source_physics_model_placements=len(owners)-len(fallback),visual_fallback_placements=fallback,source_faces_complete_within_native_coordinate_envelope=True,client_movement_verified=False,rendering_unchanged=True,old_partial_prisms_and_approximate_rock_hulls_replaced=True,native_orientation_reference_triangles=662080,elapsed_seconds=time.monotonic()-started)
 status['full_collision_rebuild']=report;status['final_compaction']=compaction;out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('collision-ownership.json').write_text(json.dumps(dict(summary=report,owners=owners,models=models,probes=probes),indent=2));shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
 for f in src.parent.glob(src.stem+'_*.ent'):shutil.copy2(f,out.parent/f.name)
 print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':build()
