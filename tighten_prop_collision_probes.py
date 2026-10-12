from pathlib import Path
p=Path('extend_prop_collision.py');s=p.read_text();s=s.replace('done=[];skipped=[];probes=[];cache={};pending_portals=[]','''done=[];skipped=[];probes=[];cache={};pending_portals=[];probe_candidates=[]
 portal_boxes=[]
 for pp in targets:
  if 'phase_runner_tunnel' not in pp['model']:continue
  nn=Path(pp['model']).stem;raw=(ROOT/'tools/legion/exported_files/models'/nn/(nn+'.rmdl')).read_bytes();low=struct.unpack_from('<3f',raw,496);high=struct.unpack_from('<3f',raw,508)
  corners=[transform(v,rotation(pp['angles']),pp['origin'],pp['scale']) for v in itertools.product(*zip(low,high))];aa,bb=box(corners);portal_boxes.append(([v-48 for v in aa],[v+48 for v in bb]))''')
a=s.index('  # Select surface traces');b=s.index('  return True',a)
s=s[:a]+'''  category=('rock' if '/rocks/' in p['model'] else 'portal' if 'tunnel' in p['model'] else 'pipe')
  center=[sum(v[k] for v in points)/len(points) for k in range(3)]
  probe_candidates.append(dict(kind=category,source_prop=p['index'],brush_index=i,end=center))
''' + s[b:]
s=s.replace("  if not results:skipped.append",'''  if method=='bounded-rock-hull' and results:
   aa,bb=box(results[0][0])
   if any(all(bb[k]>=lo[k] and aa[k]<=hi[k] for k in range(3)) for lo,hi in portal_boxes):
    skipped.append(dict(index=p['index'],model=p['model'],reason='Approximate rock hull withheld near portal geometry'));continue
  if not results:skipped.append''')
needle=' brushes=bytearray();planes=bytearray(oldplanes[:16]);'
s=s.replace(needle,''' # A prop test counts only an actual contact from a clear pilot-sized start.
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
''' + needle)
s=s.replace("  rock_placements=sum", "  approximate_rock_placements_withheld_near_portals=sum('withheld near portal' in p['reason'] for p in skipped),\n  clear_space_prop_probes=len(probes),\n  rock_placements=sum")
s=s.replace('Small hollow elbow decorations are deferred','Small hollow elbow decorations are deferred')
s=s.replace('Dense rock BVHs use a bounded convex approximation. Large portals have partial original surface prisms; small hollow elbows are deferred by native brush capacity.','Dense rock BVHs use bounded convex approximations away from portals. 67 overlapping approximations are withheld near portal geometry. Large portals have partial original surface prisms; small hollow elbows are deferred by native brush capacity.')
p.write_text(s)
p=Path('package_northstar.py');s=p.read_text().replace('if ( result.fraction < 1.0 || result.startSolid || result.allSolid )\\n\\t\\t\\t\\thullHits++','if ( result.fraction < 1.0 && !result.startSolid && !result.allSolid )\\n\\t\\t\\t\\thullHits++')
s=s.replace('which may fill small concavities. Large portal tubes','which may fill concavities; approximations that overlap the portal bounds are withheld. Large portal tubes');p.write_text(s)
p=Path('test_prop_physics.py');s=p.read_text().replace("self.assertEqual(status['prop_physics']['rock_placements'],408)","self.assertEqual(status['prop_physics']['rock_placements'],341);self.assertEqual(status['prop_physics']['approximate_rock_placements_withheld_near_portals'],67)")
s=s.replace(' def test_collision_primitive_overrun_is_rejected(self):',''' def test_selected_prop_probes_start_outside_every_expanded_brush(self):
  path=ROOT/'output/phase-runner/preview-prop-physics/mp_phase_runner_preview.bsp';d=path.read_bytes()
  def lump(i):o,n=struct.unpack_from('<2I',d,16+i*16);return d[o:o+n]
  planes=list(struct.iter_unpack('<4f',lump(1)));records=list(struct.iter_unpack('<3f2BH3fI',lump(0x5c)));status=json.loads(path.with_name('source-build.json').read_text())
  for probe in status['collision_probes'][24:]:
   self.assertTrue(probe['clear_pilot_hull_start_verified']);p=probe['start'];hmin=(-16,-16,0);hmax=(16,16,72)
   for r in records:
    if any(p[k]<r[k]-r[k+6]-hmax[k]-.05 or p[k]>r[k]+r[k+6]-hmin[k]+.05 for k in range(3)):continue
    qs=planes[1+r[9]:1+r[9]+r[4]]
    self.assertTrue(any(sum(q[k]*p[k] for k in range(3))>q[3]-sum(min(q[k]*hmin[k],q[k]*hmax[k]) for k in range(3))+.05 for q in qs))
 def test_collision_primitive_overrun_is_rejected(self):''');p.write_text(s)
