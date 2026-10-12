import json,struct,unittest
from pathlib import Path
from repair_preview_index_padding import add_index_padding,validate_index_padding,read_lumps,audit_native
from package_northstar import validate_bsp

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'output/phase-runner'

def mesh(first,count,minimum,span):
    return struct.pack('<I3H6b2h2BHI',first,count,minimum,span,*([0]*6),0,0,0,0,0,0)

class NativePairPaddingTests(unittest.TestCase):
    def test_lower_indices_from_next_mesh_reproduce_underflow(self):
        m=mesh(0,1,100,2)+mesh(3,1,0,2);i=struct.pack('<6H',100,101,102,0,1,2);s=bytes(12)
        with self.assertRaisesRegex(ValueError,'pair read exceeds'):validate_index_padding(m,i,s)
        self.assertEqual(struct.unpack_from('<H',i,6)[0]-100,-100)
        fixed,idx,count=add_index_padding(m,i);proof=validate_index_padding(fixed,idx,s)
        self.assertEqual(count,2);self.assertEqual(proof['render_triangles'],2)
        self.assertEqual(struct.unpack_from('<6H',idx),(100,101,102,102,102,102))
    def test_even_meshes_need_no_padding_or_geometry_changes(self):
        m=mesh(0,2,0,3);i=struct.pack('<6H',0,1,2,1,3,2)
        a,b,n=add_index_padding(m,i);self.assertEqual((a,b,n),(m,i,0));validate_index_padding(a,b,bytes(12))
    def test_non_degenerate_padding_is_rejected(self):
        m,i,_=add_index_padding(mesh(0,1,0,2),struct.pack('<3H',0,1,2));i=bytearray(i);struct.pack_into('<H',i,6,1)
        with self.assertRaisesRegex(ValueError,'not degenerate'):validate_index_padding(m,i,bytes(12))
    def test_padding_rule_matches_every_mesh_in_native_maps(self):
        for relative in ('inputs/titanfall2-homestead/maps/mp_homestead.bsp','inputs/titanfall2-colony/maps/mp_colony02.bsp'):
            p=audit_native(ROOT/relative);self.assertGreater(p['odd_meshes_padded'],200)
            self.assertTrue(p['pair_reads_within_declared_vertex_ranges'])
    def test_failed_build_cannot_pass_new_packaging_guard(self):
        with self.assertRaises(ValueError):validate_bsp(PROJECT/'preview-native-cells/mp_phase_runner_preview.bsp',require_native_index_padding=True)
    def test_real_repair_retains_geometry_and_collision_and_visibility(self):
        ids=(3,0x1e,0x49,2,0x2b,0x2c,0x51,0x52,0x6a,0x6b,0x6c,0x77,0x78,0x79,0x50,0x4f,1,0x5c)
        source=read_lumps(PROJECT/'preview-structure-physics/mp_phase_runner_preview.bsp',ids)
        path=PROJECT/'preview-index-repaired/mp_phase_runner_preview.bsp';new=read_lumps(path,ids)
        for i in ids:
            if i not in (0x50,0x4f):self.assertEqual(source[i],new[i])
        proof=validate_index_padding(new[0x50],new[0x4f],new[0x52]);self.assertEqual(proof['render_triangles'],7010627)
        for at in range(0,len(source[0x50]),28):
            old=source[0x50][at:at+28];fixed=new[0x50][at:at+28];self.assertEqual(old[4:],fixed[4:])
            a,count=struct.unpack_from('<IH',old);b=struct.unpack_from('<I',fixed)[0]
            self.assertEqual(source[0x4f][a*2:(a+count*3)*2],new[0x4f][b*2:(b+count*3)*2])
        mi=18176;first,count=struct.unpack_from('<IH',new[0x50],mi*28)
        self.assertEqual(count,313);padding=struct.unpack_from('<3H',new[0x4f],(first+count*3)*2)
        minimum,span=struct.unpack_from('<2H',new[0x50],mi*28+6)
        self.assertEqual(len(set(padding)),1);self.assertTrue(all(minimum<=v<=minimum+span for v in padding))
        validate_bsp(path,require_native_index_padding=True)

if __name__=='__main__':unittest.main()
