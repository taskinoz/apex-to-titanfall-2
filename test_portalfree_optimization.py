"""Prove exact rendered corners, native range safety and portal-free sky coverage."""
import json,math,struct,unittest
from pathlib import Path
from optimize_portalfree_render import SOURCE,TARGET,DT,np,CAMERA_MIN,CAMERA_MAX
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY


class PortalfreeOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(2,3,0x1e,0x49,0x4f,0x50,0x51,0x52,*range(0x6a,0x7a))
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids)
        cls.report=json.loads(TARGET.with_name('portalfree-optimization.json').read_text())

    def test_every_rendered_corner_and_native_material_binding_are_exact(self):
        old,new=self.old,self.new
        ov=np.frombuffer(old[0x49],DT);nv=np.frombuffer(new[0x49],DT)
        positions=np.frombuffer(old[3],'V12');normals=np.frombuffer(old[0x1e],'V12')
        oi=np.frombuffer(old[0x4f],'<u2');ni=np.frombuffer(new[0x4f],'<u2')
        os=list(struct.iter_unpack('<3hHI',old[0x52]));ns=list(struct.iter_unpack('<3hHI',new[0x52]))
        rows=list(struct.iter_unpack('<I3H6b2h2BHI',new[0x50]));count=0
        for mi,(a,b) in enumerate(zip(struct.iter_unpack('<I3H6b2h2BHI',old[0x50]),rows)):
            self.assertEqual(a[:2],b[:2]);self.assertEqual(a[4:14],b[4:14]);self.assertEqual(a[-1],b[-1])
            sa,sb=os[a[-2]],ns[b[-2]];self.assertEqual(sa[:3],sb[:3])
            av=ov[sa[4]+oi[a[0]:a[0]+a[1]*3].astype('<u4')]
            bv=nv[sb[4]+ni[b[0]:b[0]+b[1]*3].astype('<u4')]
            np.testing.assert_array_equal(positions[av['pi']],positions[bv['pi']],err_msg=f'Mesh {mi} positions')
            np.testing.assert_array_equal(normals[av['ni']],normals[bv['ni']],err_msg=f'Mesh {mi} normals')
            np.testing.assert_array_equal(normals[av['tangent']&0x7fffffff],normals[bv['tangent']&0x7fffffff])
            np.testing.assert_array_equal(av['tangent']&0x80000000,bv['tangent']&0x80000000)
            # Compare UV, colour, lightmap/page and extra fields as raw bytes,
            # so even float-rounding or sign-bit differences are rejected.
            ar=av.view('u1').reshape(-1,44);br=bv.view('u1').reshape(-1,44)
            np.testing.assert_array_equal(ar[:,8:36],br[:,8:36]);np.testing.assert_array_equal(ar[:,40:],br[:,40:])
            count+=a[1]
        self.assertEqual(count,873018)

    def test_shared_batches_reduce_work_without_widening_native_mesh_spans(self):
        sharing=self.report['render_sharing']
        self.assertLess(sharing['new_material_sorts'],sharing['old_material_sorts']/5)
        self.assertGreater(sharing['vertex_bytes_saved'],1000000)
        oldrows=list(struct.iter_unpack('<I3H6b2h2BHI',self.old[0x50]))
        newrows=list(struct.iter_unpack('<I3H6b2h2BHI',self.new[0x50]))
        sorts=list(struct.iter_unpack('<3hHI',self.new[0x52]));seen=set()
        for a,b in zip(oldrows,newrows):
            self.assertLessEqual(b[3],a[3]);self.assertLessEqual(b[2]+b[3],sorts[b[-2]][3]);seen.add(b[-2])
        self.assertEqual(seen,set(range(len(sorts))))
        self.assertLessEqual(max(s[3]+1 for s in sorts),60000)
        validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        self.assertEqual(audit(SOURCE)['native_padded_indices'],audit(TARGET)['native_padded_indices'])
        self.assertLess(audit(TARGET)['native_padded_indices'],WORLD_INDEX_CAPACITY*.85)

    def test_exact_previous_cell_lookup_and_portal_graph_are_restored(self):
        for lid in range(0x6a,0x77):self.assertEqual(self.old[lid],self.new[lid])
        self.assertEqual(list(struct.iter_unpack('<iI',self.new[0x6a])),[(-1,0)])
        self.assertEqual(struct.unpack('<2H2h',self.new[0x6b]),(0,0,1,-1))
        validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51])
        self.assertEqual(len(self.new[0x78])//2,4561)

    def test_skybox_survives_every_tested_camera_angle_without_portals(self):
        report=self.report['visibility'];sky=set(report['sky_meshes'])
        refs=np.frombuffer(self.new[0x78],'<u2')
        ob=np.frombuffer(self.new[0x79],'<f4').reshape(-1,8)
        chosen=ob[np.array([i for i,m in enumerate(refs) if m in sky])]
        self.assertGreater(len(chosen),0)
        lo,hi=chosen[:,:3].astype(float),chosen[:,4:7].astype(float)
        cameras=[(x,y,z) for x in (CAMERA_MIN[0],0,CAMERA_MAX[0]) for y in (CAMERA_MIN[1],0,CAMERA_MAX[1])
                 for z in (CAMERA_MIN[2],-1000,CAMERA_MAX[2])]
        for camera in cameras:
            self.assertTrue(np.all((lo<=camera)&(hi>=camera)))
            for pitch in (-90,-45,0,45,90):
                for yaw in range(0,360,30):
                    p,y=math.radians(pitch),math.radians(yaw)
                    f=np.array([math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),-math.sin(p)])
                    r=np.array([-math.sin(y),math.cos(y),0]);u=np.cross(r,f)
                    for normal in (f+r,f-r,f+u,f-u):
                        support=np.where(normal>=0,hi,lo)
                        self.assertTrue(np.all((support-camera)@normal>=-.001))

    def test_tunnel_geometry_is_protected_along_both_walkways(self):
        refs=np.frombuffer(self.new[0x78],'<u2');ob=np.frombuffer(self.new[0x79],'<f4').reshape(-1,8)
        permesh={int(m):ob[i] for i,m in enumerate(refs)}
        routes=json.loads((Path(__file__).resolve().parent/'output/phase-runner/preview-tunnel-walkways/tunnel-walkways.json').read_text())['routes']
        for route,meshes in zip(routes,self.report['visibility']['tunnel_protected_meshes']):
            self.assertGreater(len(meshes),50)
            for point in route['points']:
                camera=np.array(point)+[0,0,64]
                for mi in meshes:
                    box=permesh[mi];self.assertTrue(np.all(box[:3]<=camera));self.assertTrue(np.all(box[4:7]>=camera))

    def test_distant_culling_stays_local_for_unprotected_objects(self):
        protection=self.report['visibility'];guarded=set(protection['sky_meshes'])
        guarded.update(mi for members in protection['tunnel_protected_meshes'] for mi in members)
        ms=np.frombuffer(self.new[0x51],'<f4').reshape(-1,8)
        refs=np.frombuffer(self.new[0x78],'<u2');obs=np.frombuffer(self.new[0x79],'<f4').reshape(-1,8)
        checked=0
        for mi,box in zip(refs,obs):
            if mi in guarded:continue
            m=ms[mi]
            np.testing.assert_allclose(box[:3],m[:3]-m[4:7]-384,atol=.01,rtol=0)
            np.testing.assert_allclose(box[4:7],m[:3]+m[4:7]+384,atol=.01,rtol=0);checked+=1
        self.assertGreater(checked,1000)

    def test_every_other_collision_lightmap_and_shadow_lump_is_byte_unchanged(self):
        changed={0x49,0x4f,0x50,0x52,0x77,0x78,0x79,0x23}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ha=a.read(2064);hb=b.read(2064)
            for lid in range(128):
                if lid in changed:continue
                oa,na=struct.unpack_from('<2I',ha,16+16*lid);ob,nb=struct.unpack_from('<2I',hb,16+16*lid)
                self.assertEqual(na,nb);a.seek(oa);b.seek(ob)
                for start in range(0,na,1024*1024):
                    size=min(1024*1024,na-start);self.assertEqual(a.read(size),b.read(size),f'Lump {lid:#x} changed')
            def normalize(f,h):
                o,n=struct.unpack_from('<2I',h,16+16*0x23);f.seek(o);raw=bytearray(f.read(n))
                for j in range(struct.unpack_from('<I',raw)[0]):struct.pack_into('<I',raw,4+16*j+8,0)
                return raw
            self.assertEqual(normalize(a,ha),normalize(b,hb))
        self.assertEqual(SOURCE.with_suffix('.stbsp').read_bytes(),TARGET.with_suffix('.stbsp').read_bytes())

if __name__=='__main__':unittest.main()
