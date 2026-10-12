"""Native collision layout and sweep regressions, including the real map audit."""
import itertools,json,struct,unittest
import numpy as np
from audit_user_coordinates import ROOT,P
from native_triangle_collision import encode,collision_grid
from repair_preview_index_padding import read_lumps
from repair_preview_hull_edges import vertices_and_bevels
from read_prop_physics import convex_planes

class NativeTriangleTests(unittest.TestCase):
 def test_flags_identify_z_extrema_for_every_vertex_order(self):
  for zs in itertools.product((-10.,0.,10.),repeat=3):
   face=np.array([[0,0,zs[0]],[128,0,zs[1]],[0,128,zs[2]]]);l,b=encode([[face]]);word=struct.unpack('<I',l[0x42])[0];lo=word>>28&3;hi=(((word>>30)&1)+1)&~lo
   self.assertEqual(zs[lo],min(zs));self.assertEqual(zs[hi],max(zs))
 def test_orientation_rule_matches_every_homestead_triangle(self):
  l=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',(3,0x42,0x45));v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);words=np.frombuffer(l[0x42],dtype='<u4');count=0
  for h in struct.iter_unpack('<6h4i4f',l[0x45]):
   w=words[h[7]:h[7]+h[4]];a=w&1023;t=v[h[6]+np.stack((a,a+((w>>10)&127),a+((w>>17)&127)),axis=1)];lo=w>>28&3;hi=(((w>>30)&1)+1)&~lo;z=t[:,:,2];self.assertTrue(np.allclose(z[np.arange(len(w)),lo],z.min(1)));self.assertTrue(np.allclose(z[np.arange(len(w)),hi],z.max(1)));count+=len(w)
  self.assertEqual(count,662080)
 def test_vertex_and_tree_ranges_for_all_supported_counts(self):
  face=np.array([[0,0,0],[128,0,0],[0,128,0]])
  for count in (1,2,3,4,6,12,24,96,300):
   l,b=encode([[face]*count],first_vertex=27);h=struct.unpack('<6h4i4f',l[0x45]);self.assertEqual(h[3:5],(count*3,count));self.assertEqual(h[6],27);self.assertEqual(len(l[0x44])//16,2*(count-(count+3)%6+3)//3);self.assertEqual(len(l[0x60]),count*2)
 def test_grid_keeps_brush_and_triangle_types_separate(self):
  l=collision_grid([([-5,-5,-5],[5,5,5])],[([100,100,0],[200,200,0])]);words=np.frombuffer(l[0x59],dtype='<u4');self.assertEqual(set((words>>24).tolist()),{0,64});self.assertEqual(set(((words>>8)&65535).tolist()),{0})
 def test_original_vertices_generate_equivalent_player_bevels(self):
  a=np.array([[0,0,0],[80,20,0],[60,100,0],[-20,80,0]],dtype=float);b=a+[0,0,50];faces=[a.tolist(),b.tolist()]+[[a[i].tolist(),a[(i+1)%4].tolist(),b[(i+1)%4].tolist(),b[i].tolist()] for i in range(4)];points,cuts=convex_planes(faces);lo=np.min(points,axis=0);hi=np.max(points,axis=0);_,x=vertices_and_bevels(lo,hi,cuts);_,y=vertices_and_bevels(lo,hi,cuts,source_vertices=points);self.assertTrue(np.allclose(np.array(sorted(x)),np.array(sorted(y)),atol=.002))

class FullMapCollisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=P/'preview-full-collision/mp_phase_runner_preview.bsp';cls.l=read_lumps(cls.path,(1,3,0x42,0x44,0x45,0x56,0x57,0x59,0x5c,0x5d,0x5e,0x5f,0x60,0x61));cls.report=json.loads(cls.path.with_name('collision-ownership.json').read_text());cls.rows=list(struct.iter_unpack('<3f2BH3fI',cls.l[0x5c]));cls.planes=np.frombuffer(cls.l[1],dtype='<f4').reshape(-1,4);cls.headers=list(struct.iter_unpack('<6h4i4f',cls.l[0x45]))
 def test_every_rendered_solid_placement_has_owned_collision(self):
  rendered=set()
  for path in P.glob('*-geometry/report.json'):rendered.update(r['index'] for r in json.loads(path.read_text()).get('restored',[]))
  expected={p['index'] for p in json.loads((P/'static-props.json').read_text()) if p['index'] in rendered and p['solid_mode'] in (2,6,7)};owners=self.report['owners'];self.assertEqual({o['index'] for o in owners},expected);self.assertEqual(len(owners),len(expected));self.assertTrue(all(o['brushes'] or o['headers'] for o in owners))
 def test_every_convex_brush_has_valid_faces_and_bevel_flags(self):
  for i,r in enumerate(self.rows):
   self.assertEqual(i,r[5]);self.assertLessEqual(r[3],r[4]);self.assertTrue(np.isfinite(r).all());self.assertTrue(np.all(np.array(r[6:9])>0));q=self.planes[1+r[9]:1+r[9]+r[4]];self.assertEqual(len(q),r[4]);self.assertTrue(np.isfinite(q).all());self.assertTrue(np.allclose(np.linalg.norm(q[:,:3],axis=1),1,atol=.002));flags=np.frombuffer(self.l[0x5e],dtype='<u2',count=r[4],offset=(6*r[5]+r[9]+6)*2);self.assertTrue(np.all(flags[:r[3]]&0x4000==0));self.assertTrue(np.all(flags[r[3]:]&0x4000!=0))
 def test_every_triangle_header_has_finite_vertices_and_correct_extrema(self):
  v=np.frombuffer(self.l[3],dtype='<f4').reshape(-1,3);words=np.frombuffer(self.l[0x42],dtype='<u4');count=0
  for h in self.headers:
   self.assertEqual(h[0],0);self.assertLessEqual(h[3],1023);self.assertLessEqual(h[4],300);w=words[h[7]:h[7]+h[4]];a=w&1023;ids=np.stack((a,a+(w>>10&127),a+(w>>17&127)),axis=1);self.assertTrue(np.all(ids<h[3]));t=v[h[6]+ids];self.assertTrue(np.isfinite(t).all());self.assertTrue(np.all(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)>1e-5));z=t[:,:,2];lo=w>>28&3;hi=(((w>>30)&1)+1)&~lo;self.assertTrue(np.array_equal(z[np.arange(len(w)),lo],z.min(1)));self.assertTrue(np.array_equal(z[np.arange(len(w)),hi],z.max(1)));count+=len(w)
  self.assertEqual(count,self.report['summary']['native_triangles']);self.assertEqual(len(self.l[0x60]),count*2)
 def test_grid_references_every_owned_shape(self):
  w=np.frombuffer(self.l[0x59],dtype='<u4');ids=w>>8&65535;typ=w>>24;self.assertEqual(set(ids[typ==0]),set(range(len(self.rows))));self.assertEqual(set(ids[typ==64]),set(range(len(self.headers))));self.assertLess(len(w),65536)
 def test_pipes_rocks_and_reported_stairs_have_complete_source_ownership(self):
  owners={o['index']:o for o in self.report['owners']}
  for index in (16729,16730,12791,16765,116,117,118):self.assertIn(index,owners)
  for index in (16729,16730):self.assertGreater(owners[index]['triangles'],49000);self.assertEqual(owners[index]['brushes'],0)
  for o in owners.values():
   if o['method']=='BVH':self.assertEqual(o['brushes'],0)
 def test_render_geometry_lighting_visibility_and_streaming_preserved(self):
  src=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp';ids=(2,0xe,0x1e,0x49,0x4f,0x50,0x51,0x52,0x62,0x69,0x6a,0x6b,0x75,0x76,0x77,0x78,0x79,0x7b);self.assertEqual(read_lumps(src,ids),read_lumps(self.path,ids));old=read_lumps(src,(3,))[3];self.assertEqual(self.l[3][:len(old)],old);self.assertEqual(src.with_suffix('.stbsp').read_bytes(),self.path.with_suffix('.stbsp').read_bytes())
 def test_every_source_world_surface_inside_native_grid_is_preserved(self):
  from merge_collision import polygons
  from rebuild_complete_collision import clip_polygon,triangles
  faces=[f for f in (clip_polygon(p) for p in polygons(P/'collision/world-collision-regular.obj')) if f];expected=triangles(faces);expected=expected[np.linalg.norm(np.cross(expected[:,1]-expected[:,0],expected[:,2]-expected[:,0]),axis=1)>1e-5];n=self.report['summary']['world_triangles'];v=np.frombuffer(self.l[3],dtype='<f4').reshape(-1,3);actual=v[self.headers[0][6]:self.headers[0][6]+n*3].reshape(-1,3,3)
  def ordered(t):
   a=t.reshape(-1,9);return t[np.lexsort(tuple(a[:,k] for k in range(8,-1,-1)))]
  self.assertEqual(expected.shape,actual.shape);self.assertTrue(np.array_equal(ordered(expected),ordered(actual)))
if __name__=='__main__':unittest.main()
