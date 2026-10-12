"""Correct signed global BVH vertices without disturbing other collision."""
import json,shutil,struct,time
from pathlib import Path
import numpy as np
from read_prop_physics import read_bvh
from extend_prop_collision import rock_hull,box,pack_grid
from stage_prop_geometry import rotation
from repair_preview_hull_edges import vertices_and_bevels
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact

ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'
LOCATIONS=[(186,-5211,-955),(-1716,-3994,-963)]

def build():
 start=time.monotonic();src=P/'preview-aligned/mp_phase_runner_preview.bsp';out=P/'preview-signed-rocks/mp_phase_runner_preview.bsp'
 l=read_lumps(src,(1,0x5c,0x5d,0x5e,0x5f));rows=list(struct.iter_unpack('<3f2BH3fI',l[0x5c]));ps=np.frombuffer(l[1],dtype='<f4').reshape(-1,4)
 source=json.loads((P/'preview-prop-physics/prop-collision-placements.json').read_text());props={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
 name='rock_sharp_lava_moss_desertlands_06';base=ROOT/'tools/legion/exported_files/models'/name/name
 pieces,stats=read_bvh(base.with_suffix('.rmdl'));points=[v for fs in pieces for face in fs for v in face];native=struct.unpack_from('<6f',base.with_suffix('.rmdl').read_bytes(),496)
 if any(not native[k]-.02<=p[k]<=native[k+3]+.02 for p in points for k in range(3)):raise ValueError('Decoded signed physics exceeds original model bounds')
 replacements={};report=[]
 for owner in source['restored']:
  if owner['method']!='bounded-rock-hull' or Path(owner['model']).stem!=name:continue
  if owner['brushes']!=1:raise ValueError('Unexpected original approximate rock ownership')
  i=owner['first_brush']-424;prop=props[owner['index']];world,cuts=rock_hull(points,rotation(prop['angles']),prop['origin'],prop['scale']);lo,hi=box(world)
  _,extra=vertices_and_bevels(lo,hi,cuts)
  replacements[i]=(lo,hi,cuts,extra)
  r=rows[i];report.append({'brush':i,'source_prop':prop['index'],'old_bounds':[[r[k]-r[k+6] for k in range(3)],[r[k]+r[k+6] for k in range(3)]],'new_bounds':[lo,hi],'face_planes':len(cuts),'bevel_planes':len(extra)})
  if len(report)%10==0:print(f'Corrected signed rock hull {len(report)}/73',flush=True)
 if len(replacements)!=73:raise ValueError('Signed rock inventory changed')
 bs=bytearray();planes=bytearray(l[1][:16]);offsets=bytearray();sideprops=bytearray();tex=bytearray();bounds=[];records=[]
 for i,r in enumerate(rows):
  record=bytearray(l[0x5c][32*i:32*i+32]);first=len(offsets)//2
  if i in replacements:
   lo,hi,cuts,extra=replacements[i];c=(np.array(lo)+hi)*.5;e=(np.array(hi)-lo)*.5
   struct.pack_into('<3f2BH3fI',record,0,*c,len(cuts),len(cuts)+len(extra),i,*e,first)
   q=np.array(cuts+extra,dtype='<f4');planes.extend(q.tobytes());offsets.extend(bytes(2*len(q)))
   oldside=6*r[5]+r[9];sideprops.extend(l[0x5e][oldside*2:(oldside+6+len(cuts))*2]);sideprops.extend(struct.pack('<'+'H'*len(extra),*([0x4001]*len(extra))))
   tex.extend(l[0x5f][oldside*32:(oldside+6+len(cuts))*32]);tex.extend(bytes(32*len(extra)))
  else:
   lo=[r[k]-r[k+6] for k in range(3)];hi=[r[k]+r[k+6] for k in range(3)];q=ps[1+r[9]:1+r[9]+r[4]]
   struct.pack_into('<I',record,28,first);planes.extend(q.tobytes());offsets.extend(bytes(2*len(q)))
   oldside=6*r[5]+r[9];n=6+r[4];sideprops.extend(l[0x5e][oldside*2:(oldside+n)*2]);tex.extend(l[0x5f][oldside*32:(oldside+n)*32])
  bs.extend(record);bounds.append((lo,hi));records.append((lo,hi,q))
 blo=np.array([r[0] for r in records]);bhi=np.array([r[1] for r in records]);hmin=np.array([-16,-16,0]);hmax=np.array([16,16,72])
 def overlaps(point,hull=True):
  point=np.array(point);mn=hmin if hull else np.zeros(3);mx=hmax if hull else np.zeros(3);ids=np.flatnonzero(np.all(point>=blo-mx-.05,axis=1)&np.all(point<=bhi-mn+.05,axis=1));hits=[]
  for i in ids:
   q=records[i][2]
   if np.all(q[:,:3]@point<=q[:,3]-np.minimum(q[:,:3]*mn,q[:,:3]*mx).sum(axis=1)+.05):hits.append(int(i))
  return hits
 status=json.loads(src.with_name('source-build.json').read_text());probes=[];clearance=[]
 for p in LOCATIONS:
  end=[p[0],p[1],p[2]+.1]
  if overlaps(p) or overlaps(end):raise ValueError('Reported obstruction is not cleared')
  clearance.append({'start':list(p),'end':end,'reported_obstruction_cleared':True,'former_brush':63594})
 # Retain existing contacts. Add contacts with the corrected rock class, which
 # was not covered by the previous eight generic rock samples.
 for i,(lo,hi,cuts,extra) in replacements.items():
  end=((np.array(lo)+hi)*.5).tolist()
  if not i in overlaps(end,False):continue
  found=None
  for gap in (160,320,640):
   for axis in (2,0,1):
    for side in (1,-1):
     p=end.copy();p[axis]=hi[axis]+gap if side>0 else lo[axis]-gap-(72 if axis==2 else 0)
     if not overlaps(p):found=p;break
    if found:break
   if found:break
  if found:probes.append({'kind':'rock','source_prop':next(r['source_prop'] for r in report if r['brush']==i),'brush_index':i,'start':found,'end':end,'clear_pilot_hull_start_verified':True,'signed_rock_probe':True})
  if len(probes)==8:break
 if len(probes)!=8:raise ValueError('Insufficient corrected-rock contacts')
 for p in status['collision_probes']+probes:
  if p.get('clear_pilot_hull_start_verified') and overlaps(p['start']):raise ValueError('A preserved positive contact starts inside corrected collision')
 status['collision_probes'].extend(probes);status['hull_clearance_probes'].extend(clearance)
 for p in status['hull_clearance_probes']:
  if overlaps(p['start']) or overlaps(p['end']):raise ValueError('A preserved clearance path is obstructed')
 changes={1:planes,0x5c:bs,0x5d:offsets,0x5e:sideprops,0x5f:tex,**pack_grid(bounds)}
 compaction=compact(src,out,changes);status['signed_rock_collision_repair']={'version':'0.1.24','corrected_placements':len(report),'model':name,'signed_packed_header_flag':1,'local_type8_unsigned_decode_retained':True,'original_model_bounds_verified':True,'unchanged_brushes':len(rows)-len(report),'repaired_positive_probes':len(probes),'reported_obstruction_probes':clearance,'render_buffers_unchanged':True,'visibility_issue_unresolved':True,'full_rock_collision_still_approximate':True,'client_movement_verified':False,'elapsed_seconds':time.monotonic()-start}
 status['final_compaction']=compaction;out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('signed-rock-repair.json').write_text(json.dumps(report,indent=2));shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
 print(json.dumps(status['signed_rock_collision_repair'],indent=2),flush=True)

if __name__=='__main__':build()
