"""Verify reclaimed collision union, original prop pieces and visibility capacity."""
import json,struct,unittest
from pathlib import Path
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from repair_prop_coverage import traversal_frontier
from read_prop_physics import read_phy,convex_planes
from stage_prop_geometry import rotation,transform
from preview_visibility import validate_visibility
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

class PropCoverageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  ids=(1,0x51,0x5c,0x5d,0x5e,0x5f,0x77,0x78,0x79)
  cls.old=read_lumps(P/'preview-signed-rocks/mp_phase_runner_preview.bsp',ids);cls.new=read_lumps(P/'preview-prop-coverage/mp_phase_runner_preview.bsp',ids)
  cls.report=json.loads((P/'preview-prop-coverage/prop-coverage-repair.json').read_text());cls.oldrows=list(struct.iter_unpack('<3f2BH3fI',cls.old[0x5c]));cls.newrows=list(struct.iter_unpack('<3f2BH3fI',cls.new[0x5c]));cls.planes=np.frombuffer(cls.new[1],dtype='<f4').reshape(-1,4)
 def test_removed_world_brushes_are_strictly_inside_retained_existing_solids(self):
  removed=self.report['removed_world_brushes'];remap=self.report['retained_remap'];self.assertEqual(len(removed),5037)
  for key,owner in removed.items():
   old=self.oldrows[int(key)];r=self.newrows[remap[str(owner)]];c=np.array(old[:3]);e=np.array(old[6:9]);q=self.planes[1+r[9]:1+r[9]+r[4]].astype(float)
   self.assertTrue(np.all(abs(c-r[:3])+e<=r[6:9]));self.assertTrue(np.all(q[:,:3]@c+abs(q[:,:3])@e<q[:,3]))
 def test_retained_brush_geometry_and_every_side_property_are_byte_exact(self):
  removed=self.report['removed_world_brushes']
  for key,j in self.report['retained_remap'].items():
   if key in removed:continue
   i=int(key);a,b=self.oldrows[i],self.newrows[j];self.assertEqual(a[:5]+a[6:9],b[:5]+b[6:9]);self.assertEqual(b[5],j)
   self.assertEqual(self.old[1][16*(1+a[9]):16*(1+a[9]+a[4])],self.new[1][16*(1+b[9]):16*(1+b[9]+b[4])]);self.assertEqual(self.old[0x5d][2*a[9]:2*(a[9]+a[4])],self.new[0x5d][2*b[9]:2*(b[9]+b[4])])
   for lid,stride in [(0x5e,2),(0x5f,32)]:
    aa=(6*a[5]+a[9])*stride;bb=(6*b[5]+b[9])*stride;n=(6+a[4])*stride;self.assertEqual(self.old[lid][aa:aa+n],self.new[lid][bb:bb+n])
 def test_new_collision_preserves_each_original_convex_piece_and_transform(self):
  props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};cache={};self.assertEqual(len(self.report['added_props']),575)
  for owner in self.report['added_props']:
   prop=props[owner['index']];name=Path(prop['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
   if name not in cache:cache[name]=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0])
   pieces=cache[name];self.assertEqual(len(pieces),owner['brushes'])
   for j,piece in enumerate(pieces):
    points,original=convex_planes([[transform(v,rotation(prop['angles']),prop['origin'],prop['scale']) for v in face] for face in piece]);r=self.newrows[owner['first_brush']+j];q=self.planes[1+r[9]:1+r[9]+r[4]];points=np.array(points)
    self.assertTrue(np.all(points>=np.array(r[:3])-r[6:9]-.004));self.assertTrue(np.all(points<=np.array(r[:3])+r[6:9]+.004));self.assertTrue(np.all(points@q[:,:3].T<=q[:,3]+.006))
    expected=[v for v in original if not any(abs(abs(x)-1)<1e-7 for x in v[:3])];self.assertEqual(r[3],len(expected));self.assertEqual(q[:len(expected)].tobytes(),np.array(expected,dtype='<f4').tobytes())
 def test_ring_aperture_is_not_filled_by_a_whole_object_collider(self):
  # The source ring-frame origin is the center of its open aperture.
  owners=[p for p in self.report['added_props'] if Path(p['model']).stem=='mp_phase_r_ring_large_frame_01'];props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};self.assertTrue(owners)
  for owner in owners:
   origin=np.array(props[owner['index']]['origin']);inside=False
   for i in range(owner['first_brush'],owner['first_brush']+owner['brushes']):
    r=self.newrows[i];q=self.planes[1+r[9]:1+r[9]+r[4]]
    if np.all(abs(origin-r[:3])<=r[6:9]) and np.all(q[:,:3]@origin<=q[:,3]):inside=True
   self.assertFalse(inside)
 def test_visibility_traversal_stays_below_native_queue_and_keeps_geometry_bounds(self):
  self.assertEqual(self.old[0x51],self.new[0x51]);before=traversal_frontier(self.old[0x77]);after=traversal_frontier(self.new[0x77]);self.assertGreaterEqual(before['maximum_pending_nodes'],1024);self.assertLess(after['maximum_pending_nodes'],1024)
  v=validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51]);self.assertEqual(v['reachable_meshes'],22170)
 def test_render_buffers_and_native_triangle_padding_are_unchanged(self):
  ids=(2,3,0x1e,0x49,0x4f,0x50,0x52,0x62,0x69);a=read_lumps(P/'preview-signed-rocks/mp_phase_runner_preview.bsp',ids);b=read_lumps(P/'preview-prop-coverage/mp_phase_runner_preview.bsp',ids);self.assertEqual(a,b)
  self.assertEqual(validate_index_padding(b[0x50],b[0x4f],b[0x52])['render_triangles'],7010519)
if __name__=='__main__':unittest.main()
