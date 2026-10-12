import collections,json,math,mmap,struct,tempfile,unittest
from pathlib import Path
from read_prop_physics import read_phy,read_bvh,convex_planes
from extend_prop_collision import slab,pack_grid
from package_northstar import validate_bsp
from preview_visibility import validate_visibility
ROOT=Path(__file__).resolve().parent
class PropPhysicsTests(unittest.TestCase):
 def test_original_irps_convex_pieces_and_checksum(self):
  base=ROOT/'tools/legion/exported_files/models/pipe_large_angle_01_red/pipe_large_angle_01_red';check=struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]
  fs=read_phy(base.with_suffix('.phy'),check);self.assertEqual(len(fs),3)
  self.assertTrue(all(convex_planes(f) for f in fs))
  with self.assertRaisesRegex(ValueError,'checksum'):read_phy(base.with_suffix('.phy'),check^1)
 def test_physics_pointer_out_of_range_is_rejected(self):
  path=ROOT/'tools/legion/exported_files/models/rock_lava_small_moss_desertlands_02/rock_lava_small_moss_desertlands_02.phy';d=bytearray(path.read_bytes());struct.pack_into('<q',d,20,9999999)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'bad.phy';p.write_bytes(d)
   with self.assertRaisesRegex(ValueError,'outside'):read_phy(p)
 def test_original_bvh_solid_points_fit_model_bounds(self):
  path=ROOT/'tools/legion/exported_files/models/phase_runner_tunnel/phase_runner_tunnel.rmdl';d=path.read_bytes();lo=struct.unpack_from('<3f',d,496);hi=struct.unpack_from('<3f',d,508);fs,stats=read_bvh(path)
  self.assertGreater(len(fs),10000)
  self.assertGreater(stats['type_3'],100)
  for piece in fs:
   for face in piece:
    for p in face:
     self.assertTrue(all(lo[k]-.1<=p[k]<=hi[k]+.1 for k in range(3)))
 def test_surface_slab_does_not_fill_tunnel_interior(self):
  p,qs=slab([(0,0,0),(100,0,0),(100,100,0),(0,100,0)])
  self.assertTrue(all(sum(q[k]*50 for k in range(2))<=q[3]+.001 for q in qs))
  self.assertTrue(any(sum(q[k]*(50,50,40)[k] for k in range(3))>q[3] for q in qs))
 def test_compound_collision_grid_references_and_crossing(self):
  bounds=[([-2,-2,0],[2,2,8]) for _ in range(200)];l=pack_grid(bounds)
  self.assertEqual(len(l[0x59])//4,200)
  sets=list(struct.iter_unpack('<HHI',l[0x57]));cells=list(struct.iter_unpack('<HH',l[0x56]))
  for first,count in cells[:4]:self.assertEqual(sum(r[1] for r in sets[first:first+count]),200)
  self.assertTrue(any(r[1]>1 for r in sets))
 def test_real_collision_preserves_world_and_adds_valid_props(self):
  paths=[ROOT/'output/phase-runner'/x/'mp_phase_runner_preview.bsp' for x in ('preview-spatial','preview-prop-physics')];maps=[]
  def read(path):
   with path.open('rb') as f:
    h=f.read(2064);out={}
    for i in (1,0x5c,0x59,0x57,0x5e):o,n=struct.unpack_from('<2I',h,16+16*i);f.seek(o);out[i]=f.read(n)
    return out
  old,new=map(read,paths);validate_bsp(paths[1])
  def keys(l):
   for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
    qs=tuple(sorted(struct.iter_unpack('<4f',l[1][16+r[9]*16:16+(r[9]+r[4])*16])))
    yield tuple(r[:3]+r[6:9])+qs
  self.assertTrue(set(keys(old)).issubset(set(keys(new))))
  status=json.loads(paths[1].with_name('source-build.json').read_text());self.assertEqual(status['prop_physics']['rock_placements'],341);self.assertEqual(status['prop_physics']['approximate_rock_placements_withheld_near_portals'],67);self.assertGreater(status['prop_physics']['pipe_placements'],600)
  self.assertLessEqual(len(new[0x5c])//32,65535)
  for r in struct.iter_unpack('<3f2BH3fI',new[0x5c]):
   self.assertLessEqual((r[5]*6+r[9]+6+r[4])*2,len(new[0x5e]))
   for q in struct.iter_unpack('<4f',new[1][16+r[9]*16:16+(r[9]+r[4])*16]):
    self.assertAlmostEqual(sum(v*v for v in q[:3]),1,places=5)
 def test_selected_prop_probes_start_outside_every_expanded_brush(self):
  path=ROOT/'output/phase-runner/preview-prop-physics/mp_phase_runner_preview.bsp';d=path.read_bytes()
  def lump(i):o,n=struct.unpack_from('<2I',d,16+i*16);return d[o:o+n]
  planes=list(struct.iter_unpack('<4f',lump(1)));records=list(struct.iter_unpack('<3f2BH3fI',lump(0x5c)));status=json.loads(path.with_name('source-build.json').read_text())
  for probe in status['collision_probes'][24:]:
   self.assertTrue(probe['clear_pilot_hull_start_verified']);p=probe['start'];hmin=(-16,-16,0);hmax=(16,16,72)
   for r in records:
    if any(p[k]<r[k]-r[k+6]-hmax[k]-.05 or p[k]>r[k]+r[k+6]-hmin[k]+.05 for k in range(3)):continue
    qs=planes[1+r[9]:1+r[9]+r[4]]
    self.assertTrue(any(sum(q[k]*p[k] for k in range(3))>q[3]-sum(min(q[k]*hmin[k],q[k]*hmax[k]) for k in range(3))+.05 for q in qs))
 def test_collision_primitive_overrun_is_rejected(self):
  path=ROOT/'output/phase-runner/preview-prop-physics/mp_phase_runner_preview.bsp';d=bytearray(path.read_bytes());o=struct.unpack_from('<I',d,16+0x57*16)[0];struct.pack_into('<HHI',d,o,0,64,65535<<8)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'bad.bsp';p.write_bytes(d)
   with self.assertRaisesRegex(ValueError,'primitive array'):validate_bsp(p)
class SpatialSectionTests(unittest.TestCase):
 def test_native_material_sort_loader_overflow_is_rejected(self):
  path=ROOT/'output/phase-runner/preview-draw-restored/mp_phase_runner_preview.bsp';d=bytearray(path.read_bytes());at=len(d);d.extend(bytes(8193*12));struct.pack_into('<4I',d,16+0x52*16,at,8193*12,0,0)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'bad.bsp';p.write_bytes(d)
   with self.assertRaisesRegex(ValueError,'material-sort loader capacity'):validate_bsp(p)

 def test_exact_triangle_membership_vertex_attributes_and_local_ranges(self):
  paths=[ROOT/'output/phase-runner'/x/'mp_phase_runner_preview.bsp' for x in ('preview-draw-restored','preview-spatial')]
  def read(path):
   with path.open('rb') as f:
    h=f.read(2064);out={}
    for i in (0x50,0x52,0x4f,0x51,0x77,0x78,0x79):o,n=struct.unpack_from('<2I',h,16+16*i);f.seek(o);out[i]=f.read(n)
    return out
  old,new=map(read,paths);self.assertEqual(old[0x52],new[0x52]);self.assertLess(len(new[0x52])//12,8192);proof=json.loads(paths[1].with_name('partition-proof.json').read_text());total=0
  for p in proof:
   m=struct.unpack_from('<IH',old[0x50],p['source_mesh']*28);sort=struct.unpack_from('<H',old[0x50],p['source_mesh']*28+22)[0];originalsort=old[0x52][sort*12:sort*12+12];expected=collections.Counter(old[0x4f][i:i+6] for i in range(m[0]*2,(m[0]+m[1]*3)*2,6));actual=collections.Counter()
   for i in range(p['first_new_mesh'],p['first_new_mesh']+p['sections']):
    first,count=struct.unpack_from('<IH',new[0x50],i*28);self.assertLessEqual(count,512);total+=count;sort=struct.unpack_from('<H',new[0x50],i*28+22)[0];self.assertEqual(new[0x52][sort*12:sort*12+12],originalsort)
    actual.update(new[0x4f][j:j+6] for j in range(first*2,(first+count*3)*2,6))
   self.assertEqual(actual,expected)
  self.assertEqual(total,7010627);validate_visibility(new[0x77],new[0x78],new[0x79],new[0x51])
  # Check preserved large buffers directly, in bounded chunks.
  with paths[0].open('rb') as a,paths[1].open('rb') as b:
   ha=a.read(2064);hb=b.read(2064)
   for i in (3,0x1e,0x49,2,0x2b,0x2c,1,0x5c):
    oa,n=struct.unpack_from('<2I',ha,16+16*i);ob,nn=struct.unpack_from('<2I',hb,16+16*i);self.assertEqual(n,nn);a.seek(oa);b.seek(ob)
    while n:
     take=min(n,8*1024*1024);self.assertEqual(a.read(take),b.read(take));n-=take
if __name__=='__main__':unittest.main()
