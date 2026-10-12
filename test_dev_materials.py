"""Prove the texture pass preserves all geometry, lighting and collider data."""
import unittest,sys,struct,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_dev_materials import SOURCE,TARGET,P,DT
from repair_preview_index_padding import read_lumps,validate_index_padding
from extract_native_material import NativePak

def fingerprints(l,materials=False):
    v=np.frombuffer(l[0x49],dtype='V44');ix=np.frombuffer(l[0x4f],'<u2');s=list(struct.iter_unpack('<3hHI',l[0x52]));out=[]
    # Include the entire vertex record and atlas page: UVs, tangent handedness,
    # colors, position/normal references and all baked illumination coordinates.
    dtype=np.dtype([('corners','V132'),('page','<i2')]+([('material','<i2')] if materials else []))
    for r in struct.iter_unpack('<I3H6b2h2BHI',l[0x50]):
        if r[-1]&0x600!=0x200:raise ValueError('Unexpected vertex buffer type')
        sr=s[r[-2]];ids=sr[4]+ix[r[0]:r[0]+r[1]*3].astype(np.uint32)
        a=np.empty(r[1],dtype);a['corners']=v[ids].copy().view('V132').ravel();a['page']=sr[1]
        if materials:a['material']=sr[0]
        out.append(a.view('V'+str(dtype.itemsize)))
    return np.sort(np.concatenate(out))

class MaterialRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=read_lumps(SOURCE,[0x49,0x4f,0x50,0x52]);cls.b=read_lumps(TARGET,[0x49,0x4f,0x50,0x52])

    def test_every_triangle_and_atlas_page_preserved(self):
        np.testing.assert_array_equal(fingerprints(self.a),fingerprints(self.b))

    def test_only_fallback_bindings_changed(self):
        old=list(struct.iter_unpack('<3hHI',self.a[0x52]));new=list(struct.iter_unpack('<3hHI',self.b[0x52]))
        self.assertEqual(len(old),len(new));changed=0
        for a,b in zip(old,new):
            self.assertEqual(a[1:],b[1:])
            if a[0]!=b[0]:self.assertEqual(a[0],0);changed+=1
        self.assertEqual(changed,35);self.assertTrue(all(b[0]!=0 for b in new))

    def test_native_padding_and_unchanged_nonmaterial_lumps(self):
        validate_index_padding(self.b[0x50],self.b[0x4f],self.b[0x52])
        allowed={2,0x2b,0x2c,0x4f,0x50,0x51,0x52,0x77,0x78,0x79,0xe,0x7b,0x23}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ha=a.read(2064);hb=b.read(2064)
            for k in set(range(128))-allowed:
                ao,an,*_=struct.unpack_from('<4I',ha,16+k*16);bo,bn,*_=struct.unpack_from('<4I',hb,16+k*16)
                self.assertEqual(an,bn,hex(k));a.seek(ao);b.seek(bo)
                for at in range(0,an,1024*1024):self.assertEqual(a.read(min(1024*1024,an-at)),b.read(min(1024*1024,an-at)),hex(k))

    def test_existing_native_materials_unchanged(self):
        old=NativePak(P/'world-materials/build/phase_runner_world.rpak');new=NativePak(P/'dev-materials/build/phase_runner_world.rpak')
        assets={a['guid']:a for a in new.assets}
        for asset in old.assets:
            self.assertIn(asset['guid'],assets)
            if asset['type']=='matl':self.assertEqual(old.material(asset),new.material(assets[asset['guid']]))
        result=json.loads((P/'dev-materials/validation.json').read_text())
        self.assertTrue(result['all_dependencies_present'])

if __name__=='__main__':unittest.main()
