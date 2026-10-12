"""Reclaim enclosed solids, restore original prop physics and bound VIS traversal."""
import collections,json,shutil,struct,time
from pathlib import Path
import numpy as np
from compact_preview_bsp import compact
from extend_prop_collision import box,pack_grid
from preview_visibility import build_visibility,validate_visibility
from read_prop_physics import read_phy,convex_planes
from repair_preview_hull_edges import vertices_and_bevels
from repair_preview_index_padding import read_lumps
from stage_prop_geometry import rotation,transform
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

def traversal_frontier(nodes):
 rows=list(struct.iter_unpack('<3f2BH3f2H',nodes));queue=collections.deque([0]);peak=1;visited=0
 while queue:
  n=rows[queue.popleft()];visited+=1;queue.extend(range(n[9],n[9]+n[3]));peak=max(peak,len(queue))
 return dict(nodes=visited,maximum_pending_nodes=peak)

def build():
 start=time.monotonic();src=P/'preview-signed-rocks/mp_phase_runner_preview.bsp';out=P/'preview-prop-coverage/mp_phase_runner_preview.bsp'
 l=read_lumps(src,(1,0x51,0x5c,0x5d,0x5e,0x5f,0x77));rows=list(struct.iter_unpack('<3f2BH3fI',l[0x5c]));oldplanes=np.frombuffer(l[1],dtype='<f4').reshape(-1,4)
 audit=json.loads((P/'collision-capacity-audit.json').read_text());removed={int(i):owner for i,owner in audit['redundant_world_brushes'].items()};props={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
 # Independently recheck the containment proof against the immutable input.
 for i,owner in removed.items():
  if i>=63436 or owner in removed:raise ValueError('Invalid containment owner')
  a,b=rows[i],rows[owner];ac,ae=np.array(a[:3]),np.array(a[6:9]);bc,be=np.array(b[:3]),np.array(b[6:9]);q=oldplanes[1+b[9]:1+b[9]+b[4]].astype(float)
  if np.any(abs(ac-bc)+ae>be) or np.any(q[:,:3]@ac+abs(q[:,:3])@ae>q[:,3]-.0004):raise ValueError('A removed world brush is not wholly enclosed')
 bs=bytearray();planes=bytearray(l[1][:16]);offsets=bytearray();sideprops=bytearray();tex=bytearray();bounds=[];remap={};records=[]
 for i,r in enumerate(rows):
  if i in removed:continue
  at=len(bounds);remap[i]=at;first=len(offsets)//2;oldside=6*r[5]+r[9];count=6+r[4]
  record=bytearray(l[0x5c][i*32:i*32+32]);struct.pack_into('<H',record,14,at);struct.pack_into('<I',record,28,first);bs.extend(record)
  planes.extend(l[1][16*(1+r[9]):16*(1+r[9]+r[4])]);offsets.extend(l[0x5d][2*r[9]:2*(r[9]+r[4])]);sideprops.extend(l[0x5e][2*oldside:2*(oldside+count)]);tex.extend(l[0x5f][32*oldside:32*(oldside+count)])
  lo=[r[k]-r[k+6] for k in range(3)];hi=[r[k]+r[k+6] for k in range(3)];bounds.append((lo,hi));records.append((lo,hi,oldplanes[1+r[9]:1+r[9]+r[4]].tolist()))
 for i,owner in removed.items():remap[i]=remap[owner]
 retained=len(bounds);cache={};done=[];candidates=[]
 targets=sorted(audit['targets'],key=lambda p:('crate' not in p['model'],'ring' not in p['model'],p['index']))
 for target in targets:
  prop=props[target['index']];name=Path(prop['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in cache:cache[name]=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0])
  pieces=cache[name];matrix=rotation(prop['angles']);first_brush=len(bounds);kind='crate' if 'crate' in name else 'ring' if 'ring' in name else 'pipe-elbow'
  if first_brush+len(pieces)>65535:raise ValueError('Restored props exceed reclaimed capacity')
  for piece in pieces:
   result=convex_planes([[transform(v,matrix,prop['origin'],prop['scale']) for v in face] for face in piece])
   if result is None:raise ValueError('Original prop physics is not convex')
   points,cuts=result;lo,hi=box(points);cuts=[q for q in cuts if not any(abs(abs(v)-1)<1e-7 for v in q[:3])]
   _,extra=vertices_and_bevels(lo,hi,cuts);c=np.array([(lo[k]+hi[k])/2 for k in range(3)],dtype='<f4');e=np.array([(hi[k]-lo[k])/2 for k in range(3)],dtype='<f4')
   # Round extents outward only when float32 center rounding would exclude a vertex.
   need=np.maximum(abs(np.array(lo)-c),abs(np.array(hi)-c));e=np.maximum(e,np.nextafter(need.astype('<f4'),np.float32(np.inf)))
   lo=(c-e).astype(float).tolist();hi=(c+e).astype(float).tolist();at=len(bounds);offset=len(offsets)//2
   if len(cuts)+len(extra)>255 or any(abs(v)>32750 for v in lo+hi):raise ValueError('Native brush capacity exceeded')
   bs.extend(struct.pack('<3f2BH3fI',*c,len(cuts),len(cuts)+len(extra),at,*e,offset));bounds.append((lo,hi));records.append((lo,hi,cuts+extra))
   for q in cuts+extra:planes.extend(struct.pack('<4f',*q));offsets.extend(bytes(2))
   sideprops.extend(struct.pack('<'+'H'*(6+len(cuts)+len(extra)),*([0]*6+[1]*len(cuts)+[0x4001]*len(extra))));tex.extend(bytes(32*(6+len(cuts)+len(extra))))
   candidates.append(dict(kind=kind,source_prop=prop['index'],brush_index=at,end=np.mean(points,axis=0).tolist(),prop_probe=True,coverage_probe=True))
  done.append(dict(index=prop['index'],model=prop['model'],kind=kind,first_brush=first_brush,brushes=len(pieces),method='original_IRPS_convex_with_sweep_bevels'))
  if len(done)%100==0:print(f'Original prop collision {len(done)}/{len(targets)}',flush=True)
 # Vectorized clear pilot-sized starts, with the actual final float32 planes.
 finalrows=np.array(list(struct.iter_unpack('<3f2BH3fI',bs)));fp=np.frombuffer(planes,dtype='<f4').reshape(-1,4);mn=np.array([-16,-16,0]);mx=np.array([16,16,72]);lows=finalrows[:,:3]-finalrows[:,6:9];highs=finalrows[:,:3]+finalrows[:,6:9]
 def overlaps(point):
  point=np.array(point);ids=np.flatnonzero(np.all(point>=lows-mx-.05,axis=1)&np.all(point<=highs-mn+.05,axis=1))
  for i in ids:
   r=finalrows[i];q=fp[1+int(r[9]):1+int(r[9])+int(r[4])]
   if np.all(q[:,:3]@point<=q[:,3]-np.minimum(q[:,:3]*mn,q[:,:3]*mx).sum(axis=1)+.05):return True
  return False
 probes=[];counts=collections.Counter();owners=collections.Counter()
 for candidate in candidates:
  kind=candidate['kind'];owner=candidate['source_prop']
  if counts[kind]>=8 or owners[owner]>=2:continue
  lo,hi,_=records[candidate['brush_index']];end=candidate['end'];found=None
  for gap in (80,160,320,640):
   for axis in (2,0,1):
    for side in (1,-1):
     p=end.copy();p[axis]=hi[axis]+gap if side>0 else lo[axis]-gap-(72 if axis==2 else 0)
     if not overlaps(p):found=p;break
    if found:break
   if found:break
  if found:probes.append(dict(candidate,start=found,clear_pilot_hull_start_verified=True));counts[kind]+=1;owners[owner]+=1
 if counts['crate']<8 or counts['ring']<8:raise ValueError('Insufficient independent crate/ring contact probes')
 status=json.loads(src.with_name('source-build.json').read_text())
 for probe in status['collision_probes']:
  probe['brush_index']=remap[probe['brush_index']]
 status['collision_probes'].extend(probes)
 for probe in status['hull_clearance_probes']:
  if 'brush_index' in probe:probe['brush_index']=remap[probe['brush_index']]
  if overlaps(probe['start']) or overlaps(probe['end']):raise ValueError('New prop physics obstructs a previous clearance sample')
 for probe in status['collision_probes']:
  if probe.get('clear_pilot_hull_start_verified') and overlaps(probe['start']):raise ValueError('A contact probe no longer has a clear pilot start')
 nodes,refs,objects=build_visibility(l[0x51],leaf_size=128);vis=validate_visibility(nodes,refs,objects,l[0x51]);before=traversal_frontier(l[0x77]);after=traversal_frontier(nodes)
 if after['maximum_pending_nodes']>=1024:raise ValueError('Visibility exceeds the native local queue capacity')
 changes={1:planes,0x5c:bs,0x5d:offsets,0x5e:sideprops,0x5f:tex,**pack_grid(bounds),0x77:nodes,0x78:refs,0x79:objects};compaction=compact(src,out,changes)
 report=dict(removed_world_brushes=removed,retained_remap=remap,added_props=done,probes=probes)
 status['prop_coverage_repair']=dict(version='0.1.25',redundant_world_brushes_removed=len(removed),existing_solid_union_preserved=True,retained_brushes=retained,added_brushes=len(bounds)-retained,restored_prop_placements=len(done),placements_by_kind=dict(collections.Counter(p['kind'] for p in done)),new_contact_probes=dict(counts),full_collision_complete=False,client_movement_verified=False,elapsed_seconds=time.monotonic()-start)
 status['visibility_queue_rebuild']=dict(before=before,after=after,leaf_size=128,native_local_queue_slots=1024,validation=vis,actual_mesh_bounds_retained=True,geometry_indices_and_materials_byte_unchanged=True,client_rendering_verified=False,cause_established=False,limitation='A bounded spatial tree is a traversal-capacity diagnostic; dedicated loading does not establish that it fixes camera-angle pop-in.')
 status['collision_sample_brushes']=len(bounds);status['visibility_rebuild']=vis;status['final_compaction']=compaction
 out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('prop-coverage-repair.json').write_text(json.dumps(report,indent=2));shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
 for f in src.parent.glob(src.stem+'_*.ent'):shutil.copy2(f,out.parent/f.name)
 print(json.dumps({k:status[k] for k in ('prop_coverage_repair','visibility_queue_rebuild')},indent=2),flush=True)
if __name__=='__main__':build()
