"""Validate actual source LODs, collision preservation and native draw constraints."""
import hashlib,json,struct,unittest
from pathlib import Path
import numpy as np
from build_budget_preview import ROOT,P,SOURCE,TARGET
from plan_budget_model_geometry import component_locks,model_sections
from simplify_preview_draw import simplifier
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from repair_prop_coverage import traversal_frontier
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from read_vg_static import load

class BudgetPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status=json.loads(TARGET.with_name('source-build.json').read_text())
        cls.proof=json.loads(TARGET.with_name('render-placement-proof.json').read_text())
        cls.draw=read_lumps(TARGET,(3,0x1e,0x49,0x4f,0x50,0x51,0x52,0x77,0x78,0x79))

    def test_all_original_lod_sections_have_matching_material_slots(self):
        plan=self.status['world_draw_budget_repair']['source_model_lod_plan']
        lods={r['model']:r['lods'] for r in json.loads((ROOT/'logs/available-vg-lods.json').read_text())}
        for r in plan['models_detail']:
            name=r['model']
            if name not in lods:continue
            sections,slots,skins=load(ROOT/'tools/legion/exported_files/models'/name,r['lod_index'])
            self.assertEqual(sum(map(len,sections)),lods[name][r['lod_index']]['triangles'])
            self.assertEqual(len(sections),len(slots))
            self.assertTrue(all(s<len(skin) for s in slots for skin in skins))
        name='phase_runner_tunnel'
        with self.assertRaises(ValueError):load(ROOT/'tools/legion/exported_files/models'/name,-1)

    def test_component_anchors_include_extremes_of_disconnected_and_seamed_parts(self):
        # Two disconnected cubes, with a UV seam duplicating one corner index.
        points=np.array([(x+offset,y,z) for offset in (0,20) for z in (0,3) for y in (0,2) for x in (0,1)],dtype='<f4')
        faces=np.array([(0,1,3),(0,3,2),(4,6,7),(4,7,5),(0,4,5),(0,5,1),(2,3,7),(2,7,6),(0,2,6),(0,6,4),(1,5,7),(1,7,3)],dtype='<u4')
        triangles=np.concatenate((faces,faces+8));points=np.concatenate((points,points[:1]))
        triangles[0,0]=16
        locks,count=component_locks(triangles,points)
        self.assertEqual(count,2);self.assertTrue(locks[0] and locks[16])
        for section in (points[:8],points[8:16]):
            anchored=points[locks.astype(bool)]
            for axis in range(3):
                self.assertTrue(np.any(anchored[:,axis]==section[:,axis].min()))
                self.assertTrue(np.any(anchored[:,axis]==section[:,axis].max()))

    def test_budget_has_headroom_with_all_meshes_visible(self):
        b=audit(TARGET)
        self.assertTrue(b['all_meshes_fit_simultaneously'])
        self.assertLessEqual(b['native_padded_indices'],int(WORLD_INDEX_CAPACITY*.85))
        self.assertEqual(b['maximum_all_visible_mesh_prefix'],b['meshes'])
        validate_index_padding(self.draw[0x50],self.draw[0x4f],self.draw[0x52])

    def test_all_collision_and_original_attribute_buffers_are_preserved(self):
        changed={3,0x0e,0x1e,0x49,0x4f,0x50,0x51,0x52,0x77,0x78,0x79,0x7b}
        def digest(f,off,size):
            f.seek(off);h=hashlib.sha256()
            while size:
                data=f.read(min(size,8*1024*1024));self.assertTrue(data);h.update(data);size-=len(data)
            return h.digest()
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ah=a.read(2064);bh=b.read(2064)
            for i in range(128):
                ao,n,*_=struct.unpack_from('<4I',ah,16+i*16);bo,m,*_=struct.unpack_from('<4I',bh,16+i*16)
                if i in (3,0x1e,0x49):
                    self.assertGreaterEqual(m,n);self.assertEqual(digest(a,ao,n),digest(b,bo,n))
                elif i not in changed and i!=0x23:
                    self.assertEqual(m,n);self.assertEqual(digest(a,ao,n),digest(b,bo,m))
                elif i==0x23:
                    a.seek(ao);b.seek(bo);x=bytearray(a.read(n));y=bytearray(b.read(m));self.assertEqual(n,m)
                    count=struct.unpack_from('<I',x)[0]
                    for j in range(count):
                        at=4+16*j+8
                        if struct.unpack_from('<I',x,at+4)[0]:
                            self.assertEqual(struct.unpack_from('<I',x,at)[0]-ao,struct.unpack_from('<I',y,at)[0]-bo)
                        else:self.assertEqual(x[at:at+4],y[at:at+4])
                        x[at:at+4]=y[at:at+4]=bytes(4)
                    self.assertEqual(x,y)
        self.assertEqual(SOURCE.with_suffix('.stbsp').read_bytes(),TARGET.with_suffix('.stbsp').read_bytes())

    def test_every_placement_keeps_original_transform_and_positive_geometry(self):
        original={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
        expected=set()
        for folder in ('prop-geometry','phase-structure-geometry','support-geometry','area-detail-geometry','broad-geometry','portal-geometry','landscape-geometry'):
            expected.update(p['index'] for p in json.loads((P/folder/'report.json').read_text())['restored'])
        placements=self.proof['placements'];self.assertEqual(len(placements),len(expected))
        self.assertEqual({p['index'] for p in placements},expected)
        for p in placements:
            self.assertGreater(p['triangles'],0)
            for field in ('origin','angles','scale','model'):self.assertEqual(p[field],original[p['index']][field])

    def test_actual_mesh_bounds_normals_and_clockwise_winding(self):
        l=self.draw;positions=np.frombuffer(l[3],dtype='<f4').reshape(-1,3)
        normals=np.frombuffer(l[0x1e],dtype='<f4').reshape(-1,3)
        vd=np.dtype([('pi','<u4'),('ni','<u4'),('rest','V36')]);vertices=np.frombuffer(l[0x49],dtype=vd)
        ix=np.frombuffer(l[0x4f],dtype='<u2');bs=list(struct.iter_unpack('<8f',l[0x51]))
        for i,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
            base=struct.unpack_from('<I',l[0x52],r[-2]*12+8)[0];v=vertices[base+ix[r[0]:r[0]+r[1]*3].astype('<u4')]
            points=positions[v['pi']].reshape(-1,3,3);self.assertTrue(np.isfinite(points).all())
            b=bs[i];lo=np.array(b[:3])-b[4:7];hi=np.array(b[:3])+b[4:7]
            self.assertTrue(np.all(points>=lo-.01));self.assertTrue(np.all(points<=hi+.01))
            # Original world normal seams can intentionally oppose winding;
            # verify the newly rebuilt prop meshes separately.
            if i>=self.proof['world_meshes']:
                n=normals[v['ni']].reshape(-1,3,3);self.assertTrue(np.allclose(np.linalg.norm(n,axis=2),1,atol=1e-4))
                face=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);dots=(face*n.sum(axis=1)).sum(axis=1)
                self.assertTrue(np.all(dots<=.1),f'Incorrect winding in mesh {i}')
        validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51])
        self.assertLess(traversal_frontier(l[0x77])['maximum_pending_nodes'],1024)

if __name__=='__main__':unittest.main()
