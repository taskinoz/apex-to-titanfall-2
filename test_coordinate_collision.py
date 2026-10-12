"""Check exact source physics, reported tunnel contacts and preserved draw data."""
import json,struct,unittest
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P,POINTS
from repair_preview_index_padding import read_lumps
from read_prop_physics import read_phy,convex_planes
from stage_prop_geometry import rotation,transform
from extend_prop_collision import area,slab

def segment_contacts(rows,planes,start,end):
 start=np.array(start);delta=np.array(end)-start;hits=[]
 for i,r in enumerate(rows):
  c,e=np.array(r[:3]),np.array(r[6:9]);lo,hi=c-e,c+e
  if np.any(np.maximum(start,start+delta)<lo) or np.any(np.minimum(start,start+delta)>hi):continue
  q=planes[1+r[9]:1+r[9]+r[4]];qs=np.concatenate((q,np.array([(1,0,0,hi[0]),(-1,0,0,-lo[0]),(0,1,0,hi[1]),(0,-1,0,-lo[1]),(0,0,1,hi[2]),(0,0,-1,-lo[2])])))
  begin,finish=0.,1.
  for nx,ny,nz,d in qs:
   n=np.array([nx,ny,nz]);a=float(n@start-d);b=float(n@delta)
   if abs(b)<1e-10:
    if a>0:begin=2.;break
   elif b<0:begin=max(begin,-a/b)
   else:finish=min(finish,-a/b)
  if begin<=finish:hits.append((begin,i))
 return sorted(hits)

class CoordinateCollisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.old=read_lumps(P/'preview-prop-coverage/mp_phase_runner_preview.bsp',(1,0x5c,0x5d,0x5e,0x5f));cls.new=read_lumps(P/'preview-coordinate-physics/mp_phase_runner_preview.bsp',cls.old.keys());cls.rows=list(struct.iter_unpack('<3f2BH3fI',cls.new[0x5c]));cls.planes=np.frombuffer(cls.new[1],dtype='<f4').reshape(-1,4);cls.report=json.loads((P/'preview-coordinate-physics/coordinate-collision-repair.json').read_text());cls.props={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
 def test_previous_collision_bytes_are_unchanged(self):
  for lid,old in self.old.items():self.assertEqual(old,self.new[lid][:len(old)])
 def test_every_added_prop_preserves_original_piece_planes_and_transform(self):
  cache={}
  for owner in self.report['added_props']:
   p=self.props[owner['index']];name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
   if name not in cache:cache[name]=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0])
   self.assertEqual(len(cache[name]),owner['brushes'])
   for j,piece in enumerate(cache[name]):
    pts,original=convex_planes([[transform(v,rotation(p['angles']),p['origin'],p['scale']) for v in face] for face in piece]);r=self.rows[owner['first_brush']+j];q=self.planes[1+r[9]:1+r[9]+r[4]];cuts=[v for v in original if not any(abs(abs(x)-1)<1e-7 for x in v[:3])]
    self.assertEqual(r[3],len(cuts));self.assertEqual(q[:r[3]].tobytes(),np.array(cuts,dtype='<f4').tobytes());self.assertTrue(np.all(np.array(pts)@q[:,:3].T<=q[:,3]+.01))
  self.assertIn(16765,[o['index'] for o in self.report['added_props']]);self.assertIn(12791,[o['index'] for o in self.report['added_props']])
 def test_each_tunnel_prism_follows_only_its_original_surface(self):
  for owner in self.report['tunnel_surfaces']:
   p=self.props[owner['index']];name=Path(p['model']).stem;faces=json.loads((P/'prop-physics'/(name+'.json')).read_text())['polygons'];faces.sort(key=area,reverse=True)
   for j,rank in enumerate(owner['surface_ranks']):
    original=[transform(v,rotation(p['angles']),p['origin'],p['scale']) for v in faces[rank]];pts,qs=slab(original);r=self.rows[owner['first_brush']+j];q=self.planes[1+r[9]:1+r[9]+r[4]];cuts=[v for v in qs if not any(abs(abs(x)-1)<1e-7 for x in v[:3])]
    self.assertEqual(q[:r[3]].tobytes(),np.array(cuts,dtype='<f4').tobytes());self.assertTrue(np.all(np.array(pts)@q[:,:3].T<=q[:,3]+.01));self.assertTrue(np.all(np.ptp(pts,axis=0)<=np.ptp(original,axis=0)+4.01))
 def test_reported_tunnel_columns_intersect_added_source_floor(self):
  ids=set(i for o in self.report['tunnel_surfaces'] for i in range(o['first_brush'],o['first_brush']+o['brushes']))
  for label in ('pipe','pipe_fall','pipe_section'):
   pt=POINTS[label];start=pt.copy();end=pt.copy();start[2]+=256;end[2]-=256
   hits=segment_contacts(self.rows,self.planes,start,end)
   self.assertTrue(any(i in ids for _,i in hits),label+' lacks source surface contact')
 def test_native_bevel_flags_and_capacity(self):
  self.assertLessEqual(len(self.rows),65535);self.assertEqual(len(self.rows),65204)
  for r in self.rows[len(self.old[0x5c])//32:]:
   first=r[5]*6+r[9]+6;flags=struct.unpack_from('<'+'H'*r[4],self.new[0x5e],first*2);self.assertTrue(all(not v&0x4000 for v in flags[:r[3]]));self.assertTrue(all(v&0x4000 for v in flags[r[3]:]))
 def test_all_render_lighting_visibility_and_streaming_are_unchanged(self):
  ids=(2,3,0xe,0x1e,0x49,0x4f,0x50,0x51,0x52,0x62,0x69,0x6a,0x6b,0x75,0x76,0x77,0x78,0x79,0x7b)
  self.assertEqual(read_lumps(P/'preview-prop-coverage/mp_phase_runner_preview.bsp',ids),read_lumps(P/'preview-coordinate-physics/mp_phase_runner_preview.bsp',ids))
if __name__=='__main__':unittest.main()
