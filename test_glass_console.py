"""Preservation, exact source rebinding and native transparency compatibility."""
import collections,json,mmap,struct,unittest
from build_glass_console import ROOT,SOURCE,TARGET,PACKAGE,MATERIALS,NAMES
from repair_preview_index_padding import read_lumps,validate_index_padding
from build_phase_runner_catwalks import mesh_faces,face_key
from optimize_portalfree_render import material_name
from preview_visibility import validate_visibility
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget
import numpy as np

class GlassConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(2,3,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x77,0x78,0x79,0x7b)
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids)
        cls.provenance=json.loads(TARGET.with_name('mesh-provenance.json').read_text())
    def test_every_other_lump_preserved(self):
        allowed={2,5,0xe,0x2b,0x2c,0x4f,0x50,0x51,0x52,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b,mmap.mmap(a.fileno(),0,access=mmap.ACCESS_READ) as x,mmap.mmap(b.fileno(),0,access=mmap.ACCESS_READ) as y:
            for i in set(range(128))-allowed:
                ox,nx=struct.unpack_from('<2I',x,16+i*16);oy,ny=struct.unpack_from('<2I',y,16+i*16)
                if i==0x23:continue # Compact relocates only the absolute game-lump directory pointer.
                self.assertEqual(nx,ny,hex(i));self.assertEqual(x[ox:ox+nx],y[oy:oy+ny],hex(i))
            # Native game-lump payload remains identical after its 16-byte directory.
            ox,nx=struct.unpack_from('<2I',x,16+0x23*16);oy,ny=struct.unpack_from('<2I',y,16+0x23*16)
            self.assertEqual(x[ox+20:ox+nx],y[oy+20:oy+ny])
    def test_all_faces_preserved_with_exact_bindings(self):
        oldfaces={mi:(r,ids,tri) for mi,r,raw,ids,tri in mesh_faces(self.old)};seen=collections.defaultdict(list);counts=collections.Counter()
        for mi,r,raw,ids,tri in mesh_faces(self.new):
            proof=self.provenance[mi];oldr,oldids,oldtri=oldfaces[proof['old_mesh']];selection=proof['faces'];seen[proof['old_mesh']].extend(selection)
            self.assertTrue(np.array_equal(ids,oldids[selection]));self.assertTrue(np.array_equal(tri,oldtri[selection]))
            oldsort=struct.unpack_from('<3hHI',self.old[0x52],oldr[-2]*12);newsort=struct.unpack_from('<3hHI',self.new[0x52],r[-2]*12)
            self.assertEqual(oldsort[1:],newsort[1:]);self.assertEqual(r[-1],oldr[-1]|(0x10 if proof['glass'] else 0))
            if proof['glass']:
                self.assertTrue(material_name(self.new,newsort[0]).endswith('/'+proof['glass']+'_transparent'));counts[proof['glass']]+=r[1]
            else:self.assertEqual(oldsort[0],newsort[0])
        for mi,(r,ids,tri) in oldfaces.items():self.assertEqual(sorted(seen[mi]),list(range(r[1])))
        self.assertEqual(dict(counts),dict(zip(NAMES,(82,72,240))))
    def test_native_partition_visibility_and_budget(self):
        count=len(self.new[0x50])//28;opaque,transparent,sky=struct.unpack_from('<3I',self.new[0x7b]);self.assertEqual(opaque,transparent);self.assertEqual(sky,count)
        for i in range(count):self.assertEqual(bool(struct.unpack_from('<I',self.new[0x50],i*28+24)[0]&0x10),i>=transparent)
        validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51]);validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        budget=enforce_camera_bypass_budget(TARGET);self.assertLess(budget['static_batch_runs'],512);self.assertLess(budget['native_padded_indices'],3145728*.9)
    def test_native_shaders_and_opacity_not_opaque(self):
        original=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak');new=NativePak(MATERIALS/'build/phase_runner_glass_console.rpak')
        for g in (0xf93913c7915690bf,0x1675e75e60ffb061):
            self.assertEqual(shader(original,next(a for a in original.assets if a['guid']==g)),shader(new,next(a for a in new.assets if a['guid']==g)))
        count=0
        for a in new.assets:
            if a['type']!='matl':continue
            spec,uber=new.material(a);self.assertEqual(spec['glueFlags'],'0x72000002');self.assertEqual(spec['depthStencilFlags'],'0x7');self.assertEqual(spec['rasterizerFlags'],'0x2');self.assertEqual(spec['blendStateMask'],'0x5')
            self.assertIn('13',spec['$textures']);self.assertLess(struct.unpack_from('<f',uber,108)[0],1);self.assertEqual(spec['$depthShadowMaterial'],'0x0');count+=1
        self.assertEqual(count,3)
    def test_resident_sidecar_and_prior_packages(self):
        before=SOURCE.with_suffix('.stbsp').read_bytes();after=TARGET.with_suffix('.stbsp').read_bytes()
        for i in range(6):
            o,n=struct.unpack_from('<2Q',before,168+i*16);p,m=struct.unpack_from('<2Q',after,168+i*16);stride=24 if i in (1,4) else 1
            self.assertEqual(before[o:o+n*stride],after[p:p+n*stride]);self.assertEqual(m,n if i>=2 else m)
        for n in ('phase_runner_world.rpak','phase_runner_detail.rpak','phase_runner_presentation.rpak'):
            self.assertEqual(digest(PACKAGE/'paks'/n),digest(ROOT/'northstar/PhaseRunner.Preview/paks'/n))
    def test_only_glass_removed_from_opaque_shadow_casters(self):
        def triangles(path):
            l=read_lumps(path,(0x7c,0x7e,0x7f));p=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);ix=np.frombuffer(l[0x7e],'<u2');out=[];at=0
            for base,count,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
                self.assertEqual((opaque,sort),(1,-1));out.extend(p[base+ix[at:at+count*3].astype('<u4')].reshape(-1,3,3));at+=count*3
            return collections.Counter(face_key(t) for t in out)
        removed=collections.Counter(face_key(t) for mi,r,raw,ids,tri in mesh_faces(self.new) if r[-1]&0x10 for t in tri)
        self.assertEqual(sum(removed.values()),394);self.assertEqual(triangles(TARGET)+removed,triangles(SOURCE))
if __name__=='__main__':unittest.main()
