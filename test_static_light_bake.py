"""Verify native encoding and geometry/collision preservation of the lighting pass."""
import unittest,struct,hashlib
import numpy as np
from apply_baked_lighting import encode_rgbm,tangents,SOURCE,TARGET,DT
from repair_preview_index_padding import read_lumps

class EncodingTests(unittest.TestCase):
    def test_linear_rgbm_roundtrip(self):
        rgb=np.array([[0,0,0],[.025,.027,.032],[1,.5,.25],[3.9,2,1]])
        encoded=encode_rgbm(rgb);decoded=encoded[:,:3]/255*(encoded[:,3,None]/255*3.984375+.015625)
        self.assertLess(np.max(np.abs(decoded-rgb)),.016)

    def test_light_ids_skip_unused_entries(self):
        value=0x00FFFFC0
        self.assertEqual([(value>>(i*6))&63 for i in range(4)],[0,63,63,63])
        self.assertEqual(value>>24,0)

    def test_tangent_normal_and_mirrored_uv(self):
        p=np.array([[[0,0,0],[10,0,0],[0,10,0]]]*2,float)
        n=np.array([[[0,0,1]]*3]*2,float)
        uv=np.array([[[0,0],[1,0],[0,1]],[[0,0],[-1,0],[0,1]]],float)
        t,m=tangents(p,n,uv)
        np.testing.assert_allclose(t[0],[[1,0,0]]*3);np.testing.assert_allclose(t[1],[[-1,0,0]]*3)
        self.assertFalse(m[0].any());self.assertTrue(m[1].all())

    def test_degenerate_uv_has_finite_tangent(self):
        p=np.array([[[0,0,0],[1,0,0],[0,1,0]]],float);n=np.array([[[0,0,1]]*3],float)
        t,m=tangents(p,n,np.zeros((1,3,2)))
        self.assertTrue(np.isfinite(t).all());np.testing.assert_allclose(np.linalg.norm(t,axis=2),1)

def render_fingerprints(l):
    v=np.frombuffer(l[0x49],DT);p=np.frombuffer(l[3],dtype='V12');ix=np.frombuffer(l[0x4f],'<u2');sorts=list(struct.iter_unpack('<4hI',l[0x52]));records=[]
    # Preserve triangle order within each source mesh's atlas-page subdivisions.
    # Fingerprint normal, material, winding, positions, diffuse UV and color.
    dtype=np.dtype([('position','V12'),('normal','V4'),('uv','V8'),('color','V4'),('texture','<i4')])
    for r in struct.iter_unpack('<I3H6b2h2BHI',l[0x50]):
        if r[-1]&0x600!=0x200:continue
        s=sorts[r[-2]];ids=s[4]+ix[r[0]:r[0]+r[1]*3].astype(np.uint32);vv=v[ids];out=np.empty(len(ids),dtype)
        out['position']=p[vv['pi']];out['normal']=vv['ni'].view('V4');out['uv']=vv['uv'].copy().view('V8').reshape(-1);out['color']=vv['color'].copy().view('V4').reshape(-1);out['texture']=s[0]
        records.append(out.view('V96').reshape(-1))
    return np.sort(np.concatenate(records))

class OutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not TARGET.is_file():raise unittest.SkipTest('Run the bake before output validation')
        ids=[3,0x1e,0x49,0x4f,0x50,0x52,0x53,0x62,0x69,0x7a]
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids)

    def test_every_render_triangle_preserved(self):
        np.testing.assert_array_equal(render_fingerprints(self.old),render_fingerprints(self.new))

    def test_collision_data_preserved(self):
        # Check all lumps outside the explicit draw/lightmap allowlist, streaming
        # to avoid retaining the 500MB physics payload twice in memory.
        changed={0x1e,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7a,0xe,0x7b,0x77,0x78,0x79,0x23}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ha=a.read(2064);hb=b.read(2064)
            for k in set(range(128))-changed:
                ao,an,*_=struct.unpack_from('<4I',ha,16+k*16);bo,bn,*_=struct.unpack_from('<4I',hb,16+k*16);self.assertEqual(an,bn,hex(k));a.seek(ao);b.seek(bo)
                for at in range(0,an,1024*1024):self.assertEqual(a.read(min(1024*1024,an-at)),b.read(min(1024*1024,an-at)),hex(k))
        self.assertTrue(self.new[0x1e].startswith(self.old[0x1e]))

    def test_native_atlas_layout(self):
        pixels=sum(w*h for _,w,h in struct.iter_unpack('<I2H',self.new[0x53]))
        self.assertEqual(len(self.new[0x62]),pixels*8);self.assertEqual(len(self.new[0x69]),pixels*9)
        self.assertEqual(struct.unpack('<63h',self.new[0x7a]),(0,)+(-1,)*62)

if __name__=='__main__':unittest.main()
