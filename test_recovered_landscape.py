"""Check compiled geometry against a complete independent Legion export."""
import math,struct,unittest,tempfile,json,contextlib,io
from pathlib import Path
from read_vg_static import load,decode,packed_normal
from recover_model_slots import load_bound_sections
from pack_preview_vertices import smooth_tangent
from conservative_preview_draw import widened_bounds
from preview_visibility import build_visibility,validate_visibility
ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'tools/legion/exported_files/models'

class RecoveredLandscapeTests(unittest.TestCase):
    def test_vg_geometry_matches_complete_legion_portal_export(self):
        name='phase_runner_tunnel';folder=MODELS/name
        vg,slots,skins=load(folder)
        qc=ROOT/'output/phase-runner/prepared-models/mdl/levels_terrain/mp_rr_phase_runner'/name/(name+'.qc')
        smd,oldslots,oldskins=load_bound_sections(qc,folder/(name+'.rmdl'))
        self.assertEqual(slots,oldslots);self.assertEqual(skins,oldskins)
        self.assertEqual([len(x) for x in vg],[len(x) for x in smd])
        for a,b in zip(vg,smd):
            for i in range(0,len(a),97):
                for aa,bb in zip(a[i],b[i]):
                    for x,y in zip(aa,bb):self.assertAlmostEqual(x,y,delta=.00011)

    def test_truncated_vg_and_missing_vertices_are_rejected(self):
        name='rock_lava_small_moss_desertlands_02';folder=MODELS/name
        model=(folder/(name+'.rmdl')).read_bytes();vg=bytearray((folder/(name+'.vg')).read_bytes())
        with self.assertRaises(ValueError):decode(model,vg[:200])
        index_offset=struct.unpack_from('<Q',vg,16+4*8)[0]
        struct.pack_into('<H',vg,index_offset,65535)
        with self.assertRaisesRegex(ValueError,'missing vertex'):decode(model,vg)

    def test_packed_normal_dominant_axis_and_sign(self):
        for axis in range(3):
            for sign in range(2):
                value=(axis<<29)|(sign<<28)|(256<<19)|(256<<10)
                n=packed_normal(value)
                self.assertAlmostEqual(n[axis],-1 if sign else 1)
                self.assertAlmostEqual(sum(x*x for x in n),1.)
        with self.assertRaises(ValueError):packed_normal(3<<29)

    def test_tangent_reprojection_retains_unit_orthogonal_frame(self):
        n=(.6,0,.8);t=smooth_tangent(n,(2,1,3),(0,1,0))
        self.assertAlmostEqual(sum(a*b for a,b in zip(n,t)),0.)
        self.assertAlmostEqual(sum(x*x for x in t),1.)
        self.assertEqual(smooth_tangent((0,0,1),(0,0,0),(1,0,0)),(1,0,0))

    def test_conservative_bounds_include_every_original_extreme(self):
        old=b''.join(struct.pack('<8f',*c,10.,*e,0.) for c,e in [((-9000,2000,-1000),(20,30,40)),((6000,-7000,2000),(50,60,70))])
        new=widened_bounds(old)
        for a in struct.iter_unpack('<8f',old):
            for b in struct.iter_unpack('<8f',new):
                for k in range(3):
                    self.assertLessEqual(b[k]-b[k+4],a[k]-a[k+4]-2000)
                    self.assertGreaterEqual(b[k]+b[k+4],a[k]+a[k+4]+2000)
        nodes,refs,objects=build_visibility(new)
        self.assertEqual(validate_visibility(nodes,refs,objects,new)['reachable_meshes'],2)

    def test_vertex_weld_preserves_uv_seams_and_every_drawn_corner(self):
        from compact_preview_bsp import compact
        from pack_preview_vertices import build
        positions=struct.pack('<12f',0,0,0,128,0,0,128,128,0,0,128,0)
        normals=struct.pack('<9f',0,0,1,1,0,0,.99,.1,0)
        records=bytearray()
        for ti,ids in enumerate([(0,1,2),(0,2,3),(0,1,2)]):
            for pi in ids:
                x,y=[(0,0),(1,0),(1,1),(0,1)][pi]
                tangent=(1 if ti!=1 else 2)|(0x80000000 if ti==2 else 0)
                records.extend(struct.pack('<2I2f4B4f2I',pi,0,x,y,255,255,255,255,.2,.3,0,0,tangent,0))
        mesh=struct.pack('<I4H4b2h2BHI',0,3,0,8,2,0,0,0,0,0,0,0,0,0,0x100a00)
        bounds=struct.pack('<8f',64,64,0,100,64,64,0,0)
        nodes,refs,objects=build_visibility(bounds)
        payload={3:positions,0x1e:normals,0x49:records,0x50:mesh,0x51:bounds,
            0x52:struct.pack('<3hHi',0,0,-1,8,0),0x4f:struct.pack('<9H',0,2,1,3,5,4,6,8,7),0x77:nodes,0x78:refs,0x79:objects}
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.bsp';target=Path(temp)/'target.bsp'
            compact(ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp',source,payload)
            source.with_name('source-build.json').write_text('{}')
            with contextlib.redirect_stdout(io.StringIO()):build(source,target)
            data=target.read_bytes()
            def lump(i):
                o,n,_,_=struct.unpack_from('<4I',data,16+i*16);return data[o:o+n]
            self.assertEqual(len(lump(0x49))//44,7)
            newidx=struct.unpack('<9H',lump(0x4f));oldidx=struct.unpack('<9H',payload[0x4f])
            for old,new in zip(oldidx,newidx):
                a=records[old*44:(old+1)*44];b=lump(0x49)[new*44:(new+1)*44]
                p,n=struct.unpack_from('<2I',b)
                self.assertEqual(lump(3)[p*12:p*12+12],positions[struct.unpack_from('<I',a)[0]*12:struct.unpack_from('<I',a)[0]*12+12])
                self.assertEqual(lump(0x1e)[n*12:n*12+12],normals[:12])
                self.assertEqual(a[8:36],b[8:36]);self.assertEqual(a[40:],b[40:])
                ta,tb=struct.unpack_from('<I',a,36)[0],struct.unpack_from('<I',b,36)[0]
                self.assertEqual(ta&0x80000000,tb&0x80000000)
                t=struct.unpack_from('<3f',lump(0x1e),(tb&0x7fffffff)*12)
                self.assertAlmostEqual(sum(x*x for x in t),1.,places=6)
                self.assertAlmostEqual(t[2],0.,places=6)

if __name__=='__main__':unittest.main()
