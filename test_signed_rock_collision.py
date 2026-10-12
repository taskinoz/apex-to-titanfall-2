"""Regress actual signed BVH assets, reported obstructions and unaffected solids."""
import json,struct,unittest
from pathlib import Path
import numpy as np
from read_prop_physics import read_bvh
from repair_preview_index_padding import read_lumps
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

class SignedRockTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  ids=(1,0x5c,0x5e,0x5f)
  cls.old=read_lumps(P/'preview-aligned/mp_phase_runner_preview.bsp',ids);cls.new=read_lumps(P/'preview-signed-rocks/mp_phase_runner_preview.bsp',ids)
  cls.repair=json.loads((P/'preview-signed-rocks/signed-rock-repair.json').read_text());cls.changed={r['brush'] for r in cls.repair}
 def overlaps(self,l,p):
  ps=np.frombuffer(l[1],dtype='<f4').reshape(-1,4);hits=[];mn=np.array([-16,-16,0]);mx=np.array([16,16,72]);p=np.array(p)
  for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
   lo=np.array(r[:3])-r[6:9];hi=np.array(r[:3])+r[6:9]
   if np.any(p<lo-mx-.05) or np.any(p>hi-mn+.05):continue
   q=ps[1+r[9]:1+r[9]+r[4]]
   if np.all(q[:,:3]@p<=q[:,3]-np.minimum(q[:,:3]*mn,q[:,:3]*mx).sum(axis=1)+.05):hits.append(i)
  return hits
 def test_both_reported_locations_previously_hit_the_same_displaced_rock(self):
  for p in [(186,-5211,-955),(-1716,-3994,-963)]:
   self.assertEqual(self.overlaps(self.old,p),[63594]);self.assertEqual(self.overlaps(self.new,p),[])
 def test_signed_global_physics_matches_independent_visual_geometry(self):
  from read_vg_static import load
  base=ROOT/'tools/legion/exported_files/models/rock_sharp_lava_moss_desertlands_06';fs,_=read_bvh(base/(base.name+'.rmdl'));p=np.array([v for q in fs for f in q for v in f]);v=np.array([v[:3] for q in load(base)[0] for f in q for v in f]);self.assertGreater(len(fs),3000)
  self.assertTrue(np.all(np.abs(p.min(axis=0)-v.min(axis=0))<.02));self.assertTrue(np.all(np.abs(p.max(axis=0)-v.max(axis=0))<.02))
 def test_inline_unsigned_portal_physics_is_not_reinterpreted(self):
  base=ROOT/'tools/legion/exported_files/models/phase_runner_tunnel/phase_runner_tunnel.rmdl';d=base.read_bytes();lo=struct.unpack_from('<3f',d,496);hi=struct.unpack_from('<3f',d,508);fs,_=read_bvh(base)
  points=np.array([v for q in fs for f in q for v in f]);self.assertTrue(np.all(points>=np.array(lo)-.1));self.assertTrue(np.all(points<=np.array(hi)+.1))
 def test_all_other_collision_shapes_and_properties_remain_byte_exact(self):
  a=list(struct.iter_unpack('<3f2BH3fI',self.old[0x5c]));b=list(struct.iter_unpack('<3f2BH3fI',self.new[0x5c]));self.assertEqual(len(a),65535);self.assertEqual(len(b),len(a));self.assertEqual(len(self.changed),73)
  for i,(x,y) in enumerate(zip(a,b)):
   if i in self.changed:continue
   self.assertEqual(self.old[0x5c][i*32:i*32+28],self.new[0x5c][i*32:i*32+28]);self.assertEqual(self.old[1][16*(1+x[9]):16*(1+x[9]+x[4])],self.new[1][16*(1+y[9]):16*(1+y[9]+y[4])])
   for lump,stride in [(0x5e,2),(0x5f,32)]:
    oa=(6*x[5]+x[9])*stride;ob=(6*y[5]+y[9])*stride;n=(6+x[4])*stride;self.assertEqual(self.old[lump][oa:oa+n],self.new[lump][ob:ob+n])
 def test_corrected_model_placements_enclose_original_transformed_physics(self):
  from stage_prop_geometry import transform,rotation
  props={r['index']:r for r in json.loads((P/'static-props.json').read_text())};base=ROOT/'tools/legion/exported_files/models/rock_sharp_lava_moss_desertlands_06/rock_sharp_lava_moss_desertlands_06.rmdl';fs,_=read_bvh(base);local=list({v for q in fs for f in q for v in f});ps=np.frombuffer(self.new[1],dtype='<f4').reshape(-1,4)
  for report in self.repair:
   prop=props[report['source_prop']];r=struct.unpack_from('<3f2BH3fI',self.new[0x5c],32*report['brush']);q=ps[1+r[9]:1+r[9]+r[4]];p=np.array([transform(v,rotation(prop['angles']),prop['origin'],prop['scale']) for v in local]);self.assertTrue(np.all(p@q[:,:3].T<=q[:,3]+.02));self.assertTrue(np.all(p>=np.array(r[:3])-r[6:9]-.02));self.assertTrue(np.all(p<=np.array(r[:3])+r[6:9]+.02))

if __name__=='__main__':unittest.main()
