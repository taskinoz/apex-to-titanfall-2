import json,struct,unittest
from pathlib import Path
from native_preview_cells import make_cells,validate_cells
from extend_structure_collision import merge_boxes,clear_hull

ROOT=Path(__file__).resolve().parent

class NativeCellTests(unittest.TestCase):
    def scene(self):
        # Crossing geometry must be in both cells, far backdrop stays reachable.
        return b''.join(struct.pack('<8f',x,y,0.,40.,20.,20.,20.,0.) for x,y in
            [(-100,-100),(100,-100),(-100,100),(100,100),(0,0),(40000,100)])
    def test_outdoor_cells_reciprocal_portals_and_crossing_geometry(self):
        bounds=self.scene();l,p=make_cells(bounds,bytes(16))
        self.assertEqual(p['cells'],4);self.assertEqual(p['directed_open_portals'],8)
        ns=list(struct.iter_unpack('<3f2BH3f2H',l[0x77]));refs=list(struct.iter_unpack('<H',l[0x78]))
        for n in ns[:4]:self.assertIn((4,),refs[n[10]:n[10]+n[5]])
        self.assertIn((5,),refs);self.assertTrue(p['all_meshes_reachable'])
    def test_invalid_portal_destination_is_rejected(self):
        b=self.scene();l,_=make_cells(b,bytes(16));p=bytearray(l[0x6c]);struct.pack_into('<H',p,6,65000);l[0x6c]=p
        with self.assertRaisesRegex(ValueError,'destination'):validate_cells(l,b)
    def test_broken_subtree_reference_range_is_rejected(self):
        b=self.scene();l,_=make_cells(b,bytes(16));n=bytearray(l[0x77]);struct.pack_into('<H',n,3*32+30,0);l[0x77]=n
        with self.assertRaisesRegex(ValueError,'root reference'):validate_cells(l,b)
    def test_real_native_cells_keep_every_mesh_and_valid_local_indices(self):
        path=ROOT/'output/phase-runner/preview-native-cells/mp_phase_runner_preview.bsp'
        with path.open('rb') as f:
            h=f.read(2064)
            def read(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
            l={i:read(i) for i in [1,0x6a,0x6b,0x6c,0x6d,0x6e,0x70,0x71,0x77,0x78,0x79]};bounds=read(0x51);m=read(0x50);indices=read(0x4f)
        self.assertEqual(validate_cells(l,bounds)['cells'],4)
        for at in range(0,len(m),28):
            first,count,lo,span=struct.unpack_from('<I3H',m,at);ids=struct.unpack_from('<'+'H'*(count*3),indices,first*2)
            self.assertEqual((lo,span),(min(ids),max(ids)-min(ids)))
    def test_local_vertex_range_encoding_matches_native_larger_maps(self):
        for relative in ('inputs/titanfall2-homestead/maps/mp_homestead.bsp','inputs/titanfall2-colony/maps/mp_colony02.bsp'):
            with (ROOT/relative).open('rb') as f:
                h=f.read(2064)
                def read(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
                m,indices=read(0x50),read(0x4f)
            for at in range(0,len(m),28):
                first,count,lo,span=struct.unpack_from('<I3H',m,at);ids=struct.unpack_from('<'+'H'*(count*3),indices,first*2)
                self.assertEqual((lo,span),(min(ids),max(ids)-min(ids)))

class StructuralPhysicsTests(unittest.TestCase):
    def test_exact_box_union_and_contained_solids(self):
        records=[([0.,0.,0.],[2.,2.,2.],[]),([2.,0.,0.],[4.,2.,2.],[]),
                 ([1.,.5,.5],[3.,1.5,1.5],[(1.,1.,0.,4.)])]
        new,remap,p=merge_boxes(records,3)
        self.assertEqual(len(new),1);self.assertEqual(set(remap.values()),{0});self.assertEqual(p['reclaimed_brushes'],2)
    def test_box_union_never_bridges_gaps_or_fills_l_shapes(self):
        for records in [([([0,0,0],[2,2,2],[]),([2.001,0,0],[4,2,2],[])]),
                        ([([0,0,0],[2,2,2],[]),([2,0,0],[4,1,2],[])])]:
            new,_,p=merge_boxes(records,2);self.assertEqual(len(new),2);self.assertEqual(p['reclaimed_brushes'],0)
    def test_real_structural_physics_preserves_existing_solids(self):
        path=ROOT/'output/phase-runner/preview-structure-physics/mp_phase_runner_preview.bsp'
        proof=json.loads(path.with_name('structure-collision-placements.json').read_text());status=json.loads(path.with_name('source-build.json').read_text())
        self.assertEqual(proof['box_union']['reclaimed_brushes'],424)
        self.assertGreater(status['structure_physics']['railing_placements'],150)
        self.assertEqual(sum(p['added_walkable_surface_prisms'] for p in status['structure_physics']['tube_floor_surfaces']),128)
        def read(p):
            with p.open('rb') as f:
                h=f.read(2064)
                def l(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
                planes=l(1);records=[]
                for r in struct.iter_unpack('<3f2BH3fI',l(0x5c)):
                    records.append(([r[k]-r[k+6] for k in range(3)],[r[k]+r[k+6] for k in range(3)],
                        list(struct.iter_unpack('<4f',planes[16+r[9]*16:16+(r[9]+r[4])*16]))))
                return records
        original=read(ROOT/'output/phase-runner/preview-prop-physics/mp_phase_runner_preview.bsp');new=read(path)
        expected,_,_=merge_boxes(original,63860)
        self.assertEqual(len(new),65535)
        for old,packed in zip(expected,new):
            self.assertEqual(old[2],packed[2])
            self.assertTrue(all(abs(old[s][k]-packed[s][k])<.003 for s in (0,1) for k in range(3)))
        for p in proof['probes']:
            self.assertTrue(clear_hull(p['start'],new))
            lo,hi,qs=new[p['brush_index']];end=p['end']
            self.assertTrue(all(lo[k]-.003<=end[k]<=hi[k]+.003 for k in range(3)))
            self.assertTrue(all(sum(q[k]*end[k] for k in range(3))<=q[3]+.01 for q in qs))

if __name__=='__main__':unittest.main()
