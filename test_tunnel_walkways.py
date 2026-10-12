"""Validate visible traversal floors without changing unrelated geometry."""
import json,struct,unittest
import numpy as np
from build_tunnel_walkways import ROOT,P,SOURCE,TARGET
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from package_northstar import validate_bsp

class TunnelWalkwayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=read_lumps(SOURCE,range(128));cls.after=read_lumps(TARGET,range(128))
        cls.report=json.loads(TARGET.with_name('tunnel-walkways.json').read_text())

    def test_original_visual_and_collision_records_preserved(self):
        appended={3,0x1e,0x49,0x4f,0x50,0x51,0x52,0x42,0x44,0x45,0x60}
        replaced={0x0e,0x7b,0x56,0x57,0x58,0x59,0x5a,0x77,0x78,0x79,0x23}
        for i in range(128):
            if i in appended:self.assertTrue(self.after[i].startswith(self.before[i]),f'prefix {i}')
            elif i not in replaced:self.assertEqual(self.before[i],self.after[i],f'lump {i}')

    def test_rendered_floor_geometry_matches_native_physics_exactly(self):
        l=self.after;pos=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);lit=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('ni','<u4'),('rest','V36')]))
        ix=np.frombuffer(l[0x4f],dtype='<u2');render=[]
        for r in list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))[self.report['first_mesh']:]:
            base=struct.unpack_from('<I',l[0x52],r[-2]*12+8)[0];t=pos[lit['pi'][base+ix[r[0]:r[0]+r[1]*3].astype('<u4')]].reshape(-1,3,3);render.extend(t[:,[0,2,1]])
        physics=[]
        for h in list(struct.iter_unpack('<6h4i4f',l[0x45]))[self.report['first_header']:]:physics.extend(pos[h[6]:h[6]+h[3]].reshape(-1,3,3))
        self.assertEqual(len(render),self.report['triangles']);self.assertTrue(np.array_equal(np.array(render),np.array(physics)))

    def test_ramps_have_no_abrupt_steps_and_both_routes_are_connected(self):
        self.assertEqual(len(self.report['routes']),2);self.assertEqual(self.report['width'],80)
        for r in self.report['routes']:
            p=np.array(r['points']);xy=np.linalg.norm(np.diff(p[:,:2],axis=0),axis=1);height=abs(np.diff(p[:,2]));self.assertTrue(np.all(xy>0))
            self.assertTrue(np.all(height<=xy*.700001));self.assertGreater(np.sum(xy),4000)

    def test_active_collision_shapes_are_retained(self):
        def active(l):
            words=[w for w, in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
            return {(w>>24,(w>>8)&65535) for w in words}
        before=active(self.before);after=active(self.after);self.assertTrue(before<=after)
        self.assertEqual(after-before,{(0x40,i) for i in range(self.report['first_header'],len(self.after[0x45])//44)})

    def test_new_mesh_bounds_winding_normals_and_visibility(self):
        l=self.after;pos=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);normals=np.frombuffer(l[0x1e],dtype='<f4').reshape(-1,3);lit=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('ni','<u4'),('rest','V36')]))
        ix=np.frombuffer(l[0x4f],dtype='<u2');bounds=list(struct.iter_unpack('<8f',l[0x51]))
        for i,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
            if i<self.report['first_mesh']:continue
            base=struct.unpack_from('<I',l[0x52],r[-2]*12+8)[0];v=lit[base+ix[r[0]:r[0]+r[1]*3].astype('<u4')];p=pos[v['pi']].reshape(-1,3,3);n=normals[v['ni']].reshape(-1,3,3);b=bounds[i]
            self.assertTrue(np.all(p>=np.array(b[:3])-b[4:7]-.01));self.assertTrue(np.all(p<=np.array(b[:3])+b[4:7]+.01));self.assertTrue(np.allclose(np.linalg.norm(n,axis=2),1,atol=1e-5))
            face=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);self.assertTrue(np.all((face*n.sum(1)).sum(1)<=.01))
        validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51]);validate_index_padding(l[0x50],l[0x4f],l[0x52])

    def test_native_structure_and_all_visible_budget(self):
        validate_bsp(TARGET,require_native_index_padding=True);b=audit(TARGET)
        self.assertTrue(b['all_meshes_fit_simultaneously']);self.assertLessEqual(b['native_padded_indices'],int(WORLD_INDEX_CAPACITY*.85))

if __name__=='__main__':unittest.main()
