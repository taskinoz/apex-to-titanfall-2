"""Add native prop brushes without removing existing world collision."""
import collections,itertools,json,math,mmap,shutil,struct
from pathlib import Path
from read_prop_physics import read_phy,read_bvh,convex_planes,plane
from stage_prop_geometry import rotation,transform
from compact_preview_bsp import compact
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'output/phase-runner'

def box(points):return ([min(p[k] for p in points) for k in range(3)],[max(p[k] for p in points) for k in range(3)])
def area(face):
 from build_preview_source import cross,subtract
 return sum(math.sqrt(sum(v*v for v in cross(subtract(face[i],face[0]),subtract(face[i+1],face[0]))))*.5 for i in range(1,len(face)-1))
def slab(face,thickness=4.):
 q=plane(face)
 if q is None:return None
 n=q[:3];a=[tuple(p[k]+n[k]*thickness*.5 for k in range(3)) for p in face];b=[tuple(p[k]-n[k]*thickness*.5 for k in range(3)) for p in face]
 return convex_planes([a,b]+[[a[i],a[(i+1)%len(a)],b[(i+1)%len(a)],b[i]] for i in range(len(a))])
def rock_hull(points,matrix,origin,scale):
 # A bounded 26-direction convex approximation, built from ORIGINAL physics vertices.
 # Never used for hollow pipes or tunnel models.
 world=[transform(p,matrix,origin,scale) for p in set(tuple(p) for p in points)];planes=[]
 for d in itertools.product((-1,0,1),repeat=3):
  mag=math.sqrt(sum(v*v for v in d))
  if not mag:continue
  n=transform(tuple(v/mag for v in d),matrix);distance=max(sum(n[k]*p[k] for k in range(3)) for p in world)
  planes.append((*n,distance))
 return world,planes

def pack_grid(bounds,chunk=64):
 memberships=collections.defaultdict(list)
 for i,(lo,hi) in enumerate(bounds):
  cells=tuple(c for c in range(4) if hi[0]>=(c%2-1)*32768 and lo[0]<=c%2*32768 and hi[1]>=(c//2-1)*32768 and lo[1]<=c//2*32768)
  if not cells:raise ValueError('Collision outside grid')
  memberships[cells].append(i)
 primitives=bytearray();pbounds=bytearray();sets=bytearray();sbounds=bytearray();cells=bytearray();groups=[]
 def packed_bounds(lo,hi):
  c=[round((lo[k]+hi[k])/2) for k in range(3)];e=[math.ceil(max(abs(lo[k]-c[k]),abs(hi[k]-c[k])))+2 for k in range(3)]
  if any(abs(v)>32767 for v in c) or any(v>32767 for v in e):raise ValueError('Native collision bounds overflow')
  return struct.pack('<3hH3hH',*c,0x8000,*e,0)
 for touched,ids in sorted(memberships.items()):
  for begin in range(0,len(ids),chunk):
   selected=ids[begin:begin+chunk];first=len(primitives)//4
   lo=[min(bounds[i][0][k] for i in selected) for k in range(3)];hi=[max(bounds[i][1][k] for i in selected) for k in range(3)]
   for i in selected:primitives.extend(struct.pack('<I',i<<8));pbounds.extend(packed_bounds(*bounds[i]))
   groups.append((touched,len(selected),first,packed_bounds(lo,hi)))
 for c in range(4):
  first=len(sets)//8
  for touched,count,start,b in groups:
   if c in touched:
    # Compound references share one primitive range across touched grid cells.
    if count==1:packed=struct.unpack_from('<I',primitives,start*4)[0]
    else:packed=start<<8
    sets.extend(struct.pack('<HHI',0,count,packed));sbounds.extend(b)
  count=len(sets)//8-first
  if first+count>65535:raise ValueError('Grid reference overflow')
  cells.extend(struct.pack('<HH',first,count))
 cells.extend(struct.pack('<HH',len(sets)//8,0))
 return {0x56:cells,0x57:sets,0x58:sbounds,0x59:primitives,0x5a:pbounds}

def build():
 source=PROJECT/'preview-spatial/mp_phase_runner_preview.bsp';out=PROJECT/'preview-prop-physics/mp_phase_runner_preview.bsp';status=json.loads(source.with_name('source-build.json').read_text())
 with source.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as d:
  h=[struct.unpack_from('<4I',d,16+16*i) for i in range(128)]
  def lump(i):o,n,_,_=h[i];return d[o:o+n]
  oldbrushes=lump(0x5c);oldplanes=lump(1);oldoffsets=lump(0x5d)
 if any(oldoffsets):raise ValueError('Expected zero plane offsets in prior preview')
 records=[];bounds=[];remap={};seen={};duplicates=0
 for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',oldbrushes)):
  qs=list(struct.iter_unpack('<4f',oldplanes[16+r[9]*16:16+(r[9]+r[4])*16]));lo=[r[k]-r[k+6] for k in range(3)];hi=[r[k]+r[k+6] for k in range(3)];key=tuple(r[:3]+r[6:9])+tuple(sorted(qs))
  if key in seen:remap[i]=seen[key];duplicates+=1;continue
  remap[i]=len(records);seen[key]=len(records);records.append((lo,hi,qs));bounds.append((lo,hi))
 world_count=len(records);restored=set()
 for p in PROJECT.glob('*-geometry/report.json'):restored.update(v['index'] for v in json.loads(p.read_text()).get('restored',[]))
 targets=[p for p in json.loads((PROJECT/'static-props.json').read_text()) if p['index'] in restored and p['solid_mode'] in (2,6,7) and ('/rocks/' in p['model'] or any(w in Path(p['model']).stem for w in ('pipe','tunnel')))]
 done=[];skipped=[];probes=[];cache={};pending_portals=[];probe_candidates=[]
 portal_boxes=[]
 for pp in targets:
  if 'phase_runner_tunnel' not in pp['model']:continue
  nn=Path(pp['model']).stem;raw=(ROOT/'tools/legion/exported_files/models'/nn/(nn+'.rmdl')).read_bytes();low=struct.unpack_from('<3f',raw,496);high=struct.unpack_from('<3f',raw,508)
  corners=[transform(v,rotation(pp['angles']),pp['origin'],pp['scale']) for v in itertools.product(*zip(low,high))];aa,bb=box(corners);portal_boxes.append(([v-48 for v in aa],[v+48 for v in bb]))
 def append_convex(result,p,method):
  if result is None:raise ValueError('Nonconvex original physics piece '+p['model'])
  points,qs=result;lo,hi=box(points)
  if any(abs(v)>32750 for v in lo+hi):raise ValueError('Prop collider outside native coordinates')
  cuts=[q for q in qs if not any(abs(abs(v)-1)<1e-7 for v in q[:3])]
  if len(cuts)>255:raise ValueError('Native cutting-plane count overflow')
  if len(records)>=65535:return False
  i=len(records);records.append((lo,hi,cuts));bounds.append((lo,hi))
  category=('rock' if '/rocks/' in p['model'] else 'portal' if 'tunnel' in p['model'] else 'pipe')
  center=[sum(v[k] for v in points)/len(points) for k in range(3)]
  probe_candidates.append(dict(kind=category,source_prop=p['index'],brush_index=i,end=center))
  return True
 # First preserve complete original convex pieces for rocks and ordinary pipes.
 # Small hollow elbow decorations are deferred to keep capacity for the large tubes.
 targets.sort(key=lambda p:('/rocks/' not in p['model'],p['index']))
 for p in targets:
  name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name;matrix=rotation(p['angles'])
  if 'phase_runner_tunnel' in name:pending_portals.append(p);continue
  if 'hollow_pipe' in name and 'corner' in name:skipped.append(dict(index=p['index'],model=p['model'],reason='Reserved capacity for large portal tubes'));continue
  if name not in cache:
   if base.with_suffix('.phy').is_file():
    checksum=struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0];cache[name]=('original-convex',read_phy(base.with_suffix('.phy'),checksum))
   elif '/rocks/' in p['model']:
    pieces,stats=read_bvh(base.with_suffix('.rmdl'));cache[name]=('bounded-rock-hull',pieces)
   else:cache[name]=('unavailable',[])
  method,pieces=cache[name];begin=len(records)
  if method=='original-convex':
   results=[convex_planes([[transform(v,matrix,p['origin'],p['scale']) for v in face] for face in faces]) for faces in pieces]
  elif method=='bounded-rock-hull':results=[rock_hull([v for fs in pieces for f in fs for v in f],matrix,p['origin'],p['scale'])] if pieces else []
  else:results=[]
  if method=='bounded-rock-hull' and results:
   aa,bb=box(results[0][0])
   if any(all(bb[k]>=lo[k] and aa[k]<=hi[k] for k in range(3)) for lo,hi in portal_boxes):
    skipped.append(dict(index=p['index'],model=p['model'],reason='Approximate rock hull withheld near portal geometry'));continue
  if not results:skipped.append(dict(index=p['index'],model=p['model'],reason='No decoded solid physics'));continue
  if len(records)+len(results)>65535:skipped.append(dict(index=p['index'],model=p['model'],reason='Native brush capacity'));continue
  for result in results:append_convex(result,p,method)
  done.append(dict(index=p['index'],model=p['model'],method=method,first_brush=begin,brushes=len(records)-begin))
 # Portal collision remains a surface shell: never fill the tube with a whole-model hull.
 portal_reports=[]
 for at,p in enumerate(pending_portals):
  name=Path(p['model']).stem;source_data=json.loads((PROJECT/'prop-physics'/(name+'.json')).read_text());matrix=rotation(p['angles']);polygons=source_data['polygons'];polygons.sort(key=area,reverse=True)
  capacity=(65535-len(records))//(len(pending_portals)-at);begin=len(records);covered=0.;total=sum(area(f) for f in polygons)
  for face in polygons:
   if len(records)-begin>=capacity:break
   placed=[transform(v,matrix,p['origin'],p['scale']) for v in face];result=slab(placed)
   if result is None:continue
   if append_convex(result,p,'portal-surface-prism'):covered+=area(face)
  done.append(dict(index=p['index'],model=p['model'],method='portal-surface-prism',first_brush=begin,brushes=len(records)-begin))
  portal_reports.append(dict(model=name,original_polygons=source_data['original_polygons'],merged_polygons=len(polygons),selected_polygons=len(records)-begin,source_surface_area_fraction=covered/total,thickness=4.,complete=False))
 # A prop test counts only an actual contact from a clear pilot-sized start.
 def clear(point):
  hmin=(-16.,-16.,0.);hmax=(16.,16.,72.)
  for lo,hi,qs in records:
   if any(point[k]<lo[k]-hmax[k]-.05 or point[k]>hi[k]-hmin[k]+.05 for k in range(3)):continue
   if all(sum(q[k]*point[k] for k in range(3))<=q[3]-sum(min(q[k]*hmin[k],q[k]*hmax[k]) for k in range(3))+.05 for q in qs):return False
  return True
 selected_owners=collections.Counter()
 for candidate in probe_candidates:
  category=candidate['kind'];owner=candidate['source_prop'];limit=4 if category=='portal' else 2
  if sum(p['kind']==category for p in probes)>=8 or selected_owners[owner]>=limit:continue
  lo,hi,qs=records[candidate['brush_index']];end=candidate['end'];found=None
  for extra in (48.,128.,256.):
   for axis in (2,0,1):
    for side in (1,-1):
     start=end.copy();start[axis]=(hi[axis]+extra) if side>0 else (lo[axis]-extra-72 if axis==2 else lo[axis]-extra)
     if clear(start):found=start;break
    if found:break
   if found:break
  if found:probes.append(dict(candidate,start=found,clear_pilot_hull_start_verified=True));selected_owners[owner]+=1
 if any(sum(p['kind']==kind for p in probes)!=8 for kind in ('rock','pipe','portal')):raise ValueError('Insufficient clear-space prop probes')
 brushes=bytearray();planes=bytearray(oldplanes[:16]);offsets=bytearray();props=bytearray();tex=bytearray()
 for i,(lo,hi,qs) in enumerate(records):
  c=[(lo[k]+hi[k])/2 for k in range(3)];e=[(hi[k]-lo[k])/2 for k in range(3)];first=len(offsets)//2;count=len(qs)
  brushes.extend(struct.pack('<3f2BH3fI',*c,count,count,i,*e,first));props.extend(struct.pack('<'+'H'*(6+count),*([0]*6+[1]*count)));tex.extend(bytes(32*(6+count)))
  for q in qs:planes.extend(struct.pack('<4f',*q));offsets.extend(bytes(2))
 replacements={1:planes,0x5c:brushes,0x5d:offsets,0x5e:props,0x5f:tex,**pack_grid(bounds)}
 report=compact(source,out,replacements)
 for probe in status['collision_probes']:probe['brush_index']=remap[probe['brush_index']]
 status['collision_probes'].extend(probes);status['collision_sample_brushes']=len(records);status['collision_sample_limit']=65535
 status['prop_physics']=dict(original_world_brushes=len(oldbrushes)//32,unchanged_world_solids=world_count,exact_duplicate_world_brushes_removed=duplicates,
  added_brushes=len(records)-world_count,restored_prop_placements=len(done),original_convex_placements=sum(p['method']=='original-convex' for p in done),approximate_rock_placements=sum(p['method']=='bounded-rock-hull' for p in done),
  approximate_rock_placements_withheld_near_portals=sum('withheld near portal' in p['reason'] for p in skipped),
  clear_space_prop_probes=len(probes),
  rock_placements=sum('/rocks/' in p['model'] for p in done),pipe_placements=sum('pipe' in p['model'] for p in done),portal_surfaces=portal_reports,compound_grid_geosets=len(replacements[0x57])//8,
  world_collision_preserved=True,client_movement_verified=False,full_prop_collision_complete=False,
  limitation='Dense rock BVHs use bounded convex approximations away from portals. 67 overlapping approximations are withheld near portal geometry. Large portals have partial original surface prisms; small hollow elbows are deferred by native brush capacity.')
 status['final_compaction']=report;out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('prop-collision-placements.json').write_text(json.dumps(dict(restored=done,skipped=skipped,probes=probes),indent=2))
 for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,out.parent/p.name)
 shutil.copy2(source.with_suffix('.stbsp'),out.with_suffix('.stbsp'));print(json.dumps(status['prop_physics'],indent=2))
if __name__=='__main__':build()
