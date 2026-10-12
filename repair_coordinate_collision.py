"""Restore original container/stair physics and reported tunnel surface gaps."""
import collections,json,shutil,struct,time
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P,POINTS
from repair_preview_index_padding import read_lumps
from repair_preview_hull_edges import vertices_and_bevels
from read_prop_physics import read_phy,convex_planes,plane
from extend_prop_collision import area,box,slab,pack_grid
from compact_preview_bsp import compact
from stage_prop_geometry import rotation,transform

def build():
 start=time.monotonic();src=P/'preview-prop-coverage/mp_phase_runner_preview.bsp';out=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp'
 ids=(1,0x5c,0x5d,0x5e,0x5f);l=read_lumps(src,ids);buffers={i:bytearray(b) for i,b in l.items()};rows=list(struct.iter_unpack('<3f2BH3fI',l[0x5c]));bounds=[([r[k]-r[k+6] for k in range(3)],[r[k]+r[k+6] for k in range(3)]) for r in rows]
 props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};plan=json.loads((P/'coordinate-collision-plan.json').read_text());cache={};owners=[];candidates=[]
 def append(result,p,kind,rank=None):
  points,cuts=result;lo,hi=box(points);cuts=[q for q in cuts if not any(abs(abs(v)-1)<1e-7 for v in q[:3])];_,extra=vertices_and_bevels(lo,hi,cuts)
  c=np.array([(lo[k]+hi[k])/2 for k in range(3)],dtype='<f4');need=np.maximum(abs(np.array(lo)-c),abs(np.array(hi)-c));e=np.nextafter(need.astype('<f4'),np.float32(np.inf));at=len(bounds);offset=len(buffers[0x5d])//2
  if at>=65535 or len(cuts)+len(extra)>255:raise ValueError('Native collision capacity exceeded')
  buffers[0x5c].extend(struct.pack('<3f2BH3fI',*c,len(cuts),len(cuts)+len(extra),at,*e,offset));bounds.append(((c-e).astype(float).tolist(),(c+e).astype(float).tolist()))
  for q in cuts+extra:buffers[1].extend(struct.pack('<4f',*q));buffers[0x5d].extend(bytes(2))
  buffers[0x5e].extend(struct.pack('<'+'H'*(6+len(cuts)+len(extra)),*([0]*6+[1]*len(cuts)+[0x4001]*len(extra))));buffers[0x5f].extend(bytes(32*(6+len(cuts)+len(extra))))
  candidates.append(dict(kind=kind,source_prop=p['index'],brush_index=at,end=np.mean(points,axis=0).tolist(),prop_probe=True,coordinate_probe=True,source_surface_rank=rank))
 for target in plan['targets']:
  p=props[target['index']];name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in cache:cache[name]=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0])
  first=len(bounds);kind='stairs' if 'stair' in name else 'cargo';matrix=rotation(p['angles'])
  for piece in cache[name]:
   result=convex_planes([[transform(v,matrix,p['origin'],p['scale']) for v in face] for face in piece])
   if result is None:raise ValueError('Invalid original convex physics')
   append(result,p,kind)
  owners.append(dict(index=p['index'],model=p['model'],first_brush=first,brushes=len(bounds)-first,kind=kind,method='original_IRPS_convex_with_sweep_bevels'))
 print('Restored source convex pieces:',len(bounds)-len(rows),flush=True)
 surface_reports=[]
 for portal in plan['portals']:
  p=props[portal['index']];name=Path(p['model']).stem;faces=json.loads((P/'prop-physics'/(name+'.json')).read_text())['polygons'];faces.sort(key=area,reverse=True);matrix=rotation(p['angles']);walk=portal['remaining_walkable_ranks'];placed={};distances={}
  labels=('pipe_fall','pipe_section') if p['index']==16729 else ('pipe',)
  for rank in walk:
   vertices=np.array([transform(v,matrix,p['origin'],p['scale']) for v in faces[rank]]);placed[rank]=vertices.tolist();lo,hi=vertices.min(axis=0),vertices.max(axis=0)
   distances[rank]=[float(np.linalg.norm(np.maximum(np.maximum(lo-np.array(POINTS[label]),np.array(POINTS[label])-hi),0))) for label in labels]
  # Reserve half the surface budget around reported gaps, half for large missing
  # walkable surfaces throughout each tunnel. Every prism follows one source face.
  selected=set()
  for j,label in enumerate(labels):
   selected.update(sorted(walk,key=lambda rank:distances[rank][j])[:450//len(labels)])
  selected.update(rank for rank in walk[:900] if len(selected)<900)
  first=len(bounds);ranks=[]
  for rank in sorted(selected):
   result=slab(placed[rank])
   if result is None:raise ValueError('Invalid walkable source surface')
   append(result,p,'reported-tunnel-floor',rank);ranks.append(rank)
  surface_reports.append(dict(index=p['index'],first_brush=first,brushes=len(bounds)-first,surface_ranks=ranks,total_remaining_surfaces=len(walk),complete=False))
  print('Added tunnel surfaces:',p['index'],len(bounds)-first,flush=True)
 finalrows=np.array(list(struct.iter_unpack('<3f2BH3fI',buffers[0x5c])));planes=np.frombuffer(buffers[1],dtype='<f4').reshape(-1,4);lows=finalrows[:,:3]-finalrows[:,6:9];highs=finalrows[:,:3]+finalrows[:,6:9];mn=np.array([-16,-16,0]);mx=np.array([16,16,72])
 def overlaps(point):
  pt=np.array(point);near=np.flatnonzero(np.all(pt>=lows-mx-.05,axis=1)&np.all(pt<=highs-mn+.05,axis=1))
  for i in near:
   r=finalrows[i];q=planes[1+int(r[9]):1+int(r[9])+int(r[4])]
   if np.all(q[:,:3]@pt<=q[:,3]-np.minimum(q[:,:3]*mn,q[:,:3]*mx).sum(axis=1)+.05):return True
  return False
 probes=[];counts=collections.Counter();perowner=collections.Counter()
 for candidate in candidates:
  kind=candidate['kind'];owner=candidate['source_prop']
  if counts[kind]>=8 or perowner[owner]>=4:continue
  lo,hi=bounds[candidate['brush_index']];end=candidate['end'];found=None
  for gap in (80,160,320,640):
   for axis in (2,0,1):
    for side in (1,-1):
     pt=end.copy();pt[axis]=hi[axis]+gap if side>0 else lo[axis]-gap-(72 if axis==2 else 0)
     if not overlaps(pt):found=pt;break
    if found:break
   if found:break
  if found:probes.append(dict(candidate,start=found,clear_pilot_hull_start_verified=True));counts[kind]+=1;perowner[owner]+=1
 if any(counts[k]<8 for k in ('stairs','cargo','reported-tunnel-floor')):raise ValueError('Incomplete new contact probes')
 # Exercise each reported pipe column in-engine, ending inside the closest
 # newly restored source floor. Start the pilot hull in verified empty space.
 site_probes=[]
 for label in ('pipe','pipe_fall','pipe_section'):
  point=POINTS[label];matches=[]
  for owner in surface_reports:
   for i in range(owner['first_brush'],owner['first_brush']+owner['brushes']):
    lo,hi=bounds[i]
    if any(point[k]<lo[k] or point[k]>hi[k] for k in (0,1)):continue
    r=finalrows[i];q=planes[1+int(r[9]):1+int(r[9])+int(r[4])];low,high=lo[2],hi[2];valid=True
    for nx,ny,nz,d in q:
     remain=d-nx*point[0]-ny*point[1]
     if abs(nz)<1e-9:
      if remain<0:valid=False;break
     elif nz>0:high=min(high,remain/nz)
     else:low=max(low,remain/nz)
    if valid and low<=high:matches.append((abs((low+high)/2-point[2]),i,(low+high)/2,high))
  if not matches:raise ValueError('No source floor in reported column '+label)
  _,i,z,high=min(matches);z=float(z);high=float(high);end=[point[0],point[1],z];clear=None
  for gap in (80,160,320,640,1280):
   trial=[point[0],point[1],high+gap]
   if not overlaps(trial):clear=trial;break
  if clear is None:raise ValueError('Reported site has no clear vertical test start')
  probe=dict(kind='reported-site',source_prop=16730 if label=='pipe' else 16729,brush_index=i,start=clear,end=end,prop_probe=True,coordinate_probe=True,reported_site=label,clear_pilot_hull_start_verified=True)
  site_probes.append(probe)
 probes.extend(site_probes)
 status=json.loads(src.with_name('source-build.json').read_text());status['collision_probes'].extend(probes)
 for probe in status['hull_clearance_probes']:
  if overlaps(probe['start']) or overlaps(probe['end']):raise ValueError('New physics blocks a previous edge-clearance sample')
 for probe in status['collision_probes']:
  if probe.get('clear_pilot_hull_start_verified') and overlaps(probe['start']):raise ValueError('New physics blocks a previous clear pilot probe')
 changes={**buffers,**pack_grid(bounds)};compaction=compact(src,out,changes)
 report=dict(added_props=owners,tunnel_surfaces=surface_reports,probes=probes,reported_site_probes=site_probes,reported_points=POINTS)
 status['coordinate_collision_repair']=dict(version='0.1.26',restored_prop_placements=len(owners),placements_by_kind=dict(collections.Counter(o['kind'] for o in owners)),original_convex_brushes=sum(o['brushes'] for o in owners),added_tunnel_floor_prisms=sum(p['brushes'] for p in surface_reports),total_brushes=len(bounds),remaining_brush_capacity=65535-len(bounds),existing_collision_preserved_byte_exact=True,rendering_unchanged=True,client_movement_verified=False,visibility_issue_unresolved=True,full_collision_complete=False,elapsed_seconds=time.monotonic()-start)
 status['collision_sample_brushes']=len(bounds);status['final_compaction']=compaction
 out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('coordinate-collision-repair.json').write_text(json.dumps(report,indent=2));shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
 for f in src.parent.glob(src.stem+'_*.ent'):shutil.copy2(f,out.parent/f.name)
 print(json.dumps(status['coordinate_collision_repair'],indent=2),flush=True)
if __name__=='__main__':build()
