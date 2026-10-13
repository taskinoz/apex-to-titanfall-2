"""Source vista decoding and static-light cone/slot regressions."""
import struct,subprocess,tempfile,unittest
from pathlib import Path
from new_arena_ports import ROOT,WORK
from read_vg_static import decode
from prepare_new_arena_scene import asset_index
from add_source_light_fill import FIXTURE,np
from recover_composite_details import JOB

class SourceFeatures(unittest.TestCase):
 def test_stripless_vista_decodes_every_triangle_and_rejects_bad_indices(self):
  p=asset_index('firing-range')['canyonlands_hu_se'];r=(p/'canyonlands_hu_se.rmdl').read_bytes();v=bytearray((p/'canyonlands_hu_se.vg').read_bytes())
  h=struct.unpack_from('<18Q',v,16);s,slots,skins=decode(r,v,0,True)
  self.assertEqual(sum(len(a) for a in s)*3,h[5]);self.assertIn('canyonlands_river_water_03_skybox',skins[0])
  struct.pack_into('<H',v,h[4],65535)
  with self.assertRaisesRegex(ValueError,'missing vertex'):decode(r,v,0,True)

 def test_static_fill_respects_spot_direction_and_supports_more_than_63_fixtures(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'output') as d:
   p=Path(d);t=np.array([[[-1,-1,0],[1,-1,0],[0,1,0]]],'<f4');t.tofile(p/'tri')
   j=np.zeros(1,JOB);j['p']=t;j['n']=[[[0,0,1]]*3];j['uv']=[[[.5,.5],[3.2,.5],[.5,3.2]]];j.tofile(p/'jobs')
   (p/'mask').write_bytes(b'\1');np.array([[0,0,0]],'<f4').tofile(p/'probes')
   def run(direction,count):
    f=np.zeros(count,FIXTURE);f['p']=[0,0,4];f['radius']=16;f['colour']=[1,0,0];f['direction']=direction;f['inner']=.9;f['outer']=.7;f['spot']=1;f.tofile(p/'fixtures')
    subprocess.run([str(WORK/'tools/bake_source_light_fill.exe'),str(p/'tri'),str(p/'jobs'),str(p/'fixtures'),str(p/'result'),'4','4','1',str(p/'mask'),str(p/'probes')],check=True,capture_output=True)
    return np.fromfile(p/'result','<f4').reshape(-1,3)
   self.assertEqual(float(run([0,0,1],1).max()),0)
   single=run([0,0,-1],1);many=run([0,0,-1],65)
   self.assertGreater(float(single[:,0].max()),0);self.assertGreaterEqual(float(many[:,0].max()),float(single[:,0].max()))
   self.assertEqual(float(many[:,1:].max()),0)

if __name__=='__main__':unittest.main()
