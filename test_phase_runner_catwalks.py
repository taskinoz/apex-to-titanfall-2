"""Independent preservation, traversal, native rendering and presentation checks."""
import collections,hashlib,json,math,struct,subprocess,unittest
from pathlib import Path
from build_phase_runner_catwalks import ROOT,SOURCE,TARGET,DT,np,face_key,mesh_faces,old_path_keys
from build_phase_runner_presentation import OUT as PRESENTATION,LANGUAGES,guid
from package_phase_runner_release import PACKAGE
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from extract_native_material import NativePak
from finalize_lighting_release import digest

class CatwalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(2,3,5,0xe,0x1e,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x57,0x59,*range(0x6a,0x7a))
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids);cls.report=json.loads(TARGET.with_name('catwalks.json').read_text())
        cls.geometry=np.load(TARGET.with_name('catwalk-geometry.npz'));cls.keys,cls.path_report=old_path_keys()

    def test_every_unrelated_corner_binding_and_lightmap_are_preserved(self):
        before=self.old;after=self.new;oldmeshes=list(mesh_faces(before));newmeshes=list(mesh_faces(after));v=np.frombuffer(before[0x49],DT)
        for newmi,mapping in enumerate(self.report['retained_source_meshes']):
            oldmi=mapping['source_mesh'];keep=mapping['retained_triangles'];a=oldmeshes[oldmi];b=newmeshes[newmi]
            np.testing.assert_array_equal(a[2][keep],b[2]);np.testing.assert_array_equal(a[3][keep],b[3]);np.testing.assert_array_equal(a[4][keep],b[4])
            self.assertEqual(a[1][4:],b[1][4:]);np.testing.assert_array_equal(v[a[3][keep]],np.frombuffer(after[0x49],DT)[b[3]])
            for t in b[4]:self.assertNotIn(face_key(t),self.keys)
        for lid in (3,0x1e,0x49,0x52,0x53,0x62,0x69,0x42,0x44,0x45,0x60):self.assertTrue(after[lid].startswith(before[lid]),hex(lid))
        self.assertEqual(len(before[0x53])//8,2);self.assertEqual(len(after[0x53])//8,3)

    def test_catwalk_draw_and_collision_have_the_same_exact_faces(self):
        l=self.new;tri=self.geometry['triangles'];render=[]
        for mi,r,raw,ids,faces in mesh_faces(l):
            if mi>=self.report['first_new_mesh']:render.extend(faces[:,[0,2,1]])
        def oriented(t):return t.tobytes()
        self.assertEqual(collections.Counter(map(oriented,render)),collections.Counter(map(oriented,tri)))
        p=np.frombuffer(l[3],'<f4').reshape(-1,3);physics=[];first=self.report['collision']['new_first_header']
        for h in list(struct.iter_unpack('<6h4i4f',l[0x45]))[first:]:physics.extend(p[h[6]:h[6]+h[3]].reshape(-1,3,3))
        np.testing.assert_array_equal(np.array(physics),tri)
        self.assertEqual(len(render),14744)

    def test_new_normals_tangents_bounds_and_native_budget(self):
        l=self.new;v=np.frombuffer(l[0x49],DT);n=np.frombuffer(l[0x1e],'<f4').reshape(-1,3);bounds=list(struct.iter_unpack('<8f',l[0x51]))
        for mi,r,raw,ids,p in mesh_faces(l):
            if mi<self.report['first_new_mesh']:continue
            nn=n[v['ni'][ids]];t=n[v['tangent'][ids]&0x7fffffff];cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);b=bounds[mi]
            self.assertTrue(np.all((cross*nn.sum(1)).sum(1)<0));self.assertTrue(np.allclose(np.linalg.norm(nn,axis=2),1,atol=1e-5))
            self.assertTrue(np.allclose(np.linalg.norm(t,axis=2),1,atol=1e-5));self.assertTrue(np.allclose((nn*t).sum(2),0,atol=1e-5))
            self.assertTrue(np.all(p>=np.array(b[:3])-b[4:7]-.01));self.assertTrue(np.all(p<=np.array(b[:3])+b[4:7]+.01))
        validate_index_padding(l[0x50],l[0x4f],l[0x52]);budget=audit(TARGET)
        self.assertEqual(budget['real_triangles'],881966);self.assertLess(budget['native_padded_indices'],WORLD_INDEX_CAPACITY*.85)
        self.assertEqual(struct.unpack_from('<I',l[0xe],28)[0],len(l[0x50])//28)

    def test_unrelated_collision_and_active_shapes_are_retained(self):
        def active(l):
            words=[w for w, in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
            return {(w>>24,(w>>8)&65535) for w in words}
        original=active(self.old);current=active(self.new);disabled={(0x40,i) for i in self.report['collision']['disabled_old_path_headers']}
        first=self.report['collision']['new_first_header'];count=self.report['collision']['new_headers']
        self.assertEqual(original-current,disabled);self.assertEqual(current-original,{(0x40,i) for i in range(first,first+count)})
        self.assertEqual(self.old[0x5c],self.new[0x5c])

    def test_whole_map_visibility_contains_both_routes_at_all_view_angles(self):
        l=self.new;validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51])
        objects=list(struct.iter_unpack('<3fI3fI',l[0x79]))
        eyes=np.concatenate([np.array(r['points'])+[0,0,64] for r in self.report['routes']])
        for o in objects:
            self.assertTrue(np.all(eyes>=o[:3]));self.assertTrue(np.all(eyes<=o[4:7]))
            # A contained camera lies inside the support of every side plane,
            # independent of horizontal/up/down direction.
            lo=np.array(o[:3]);hi=np.array(o[4:7]);sample=eyes[::32]
            for pitch in (-90,-45,0,45,90):
                for yaw in range(0,360,45):
                    q=np.deg2rad([pitch,yaw]);axis=np.array([math.cos(q[0])*math.cos(q[1]),math.cos(q[0])*math.sin(q[1]),math.sin(q[0])])
                    support=np.where(axis>=0,hi,lo);self.assertTrue(np.all((support-sample)@axis>=-.01))
        for lid in range(0x6a,0x77):self.assertEqual(l[lid],self.old[lid],hex(lid))

    def test_new_deck_retains_route_elevation_and_clear_center_lane(self):
        self.assertEqual(self.report['routes'],self.path_report['routes']);tri=self.geometry['triangles'];kind=self.geometry['kinds']
        normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);self.assertTrue(np.all(normal[kind==0,2]>0))
        for d in self.report['catwalk_details']:
            self.assertEqual(d['deck_width'],80);self.assertGreater(d['clear_width'],32);self.assertEqual(d['top_rail_height'],42)
            p=np.array(d['rail_station_points']);self.assertLessEqual(np.linalg.norm(np.diff(p,axis=0),axis=1).max(),96.00001)
        bake=self.report['light_bake'];self.assertGreater(bake['valid_luxels'],30000);self.assertGreater(bake['local_lit_luxels'],10000)

    def test_every_other_bsp_payload_is_preserved(self):
        changed={3,5,0xe,0x1e,0x23,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b,0x42,0x44,0x45,0x60,0x56,0x57,0x58,0x59,0x5a,0x77,0x78,0x79,0x7c,0x7e,0x7f}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ah=a.read(2064);bh=b.read(2064)
            for i in range(128):
                if i in changed:continue
                ao,an,av,ap=struct.unpack_from('<4I',ah,16+i*16);bo,bn,bv,bp=struct.unpack_from('<4I',bh,16+i*16)
                self.assertEqual((an,av,ap),(bn,bv,bp),hex(i));a.seek(ao);b.seek(bo)
                for at in range(0,an,8*1024*1024):size=min(8*1024*1024,an-at);self.assertEqual(a.read(size),b.read(size),hex(i))
        self.assertEqual(digest(SOURCE.with_suffix('.stbsp')),digest(TARGET.with_suffix('.stbsp')))

    def test_renamed_package_localization_and_loading_assets_are_consistent(self):
        mod=json.loads((PACKAGE/'mod.json').read_text());self.assertEqual(mod['Version'],'0.1.37');self.assertEqual(mod['Localisation'],['resource/phase_runner_%language%.txt'])
        self.assertEqual(digest(PACKAGE/'mod/maps/mp_phase_runner.bsp'),digest(TARGET));self.assertFalse((PACKAGE/'mod/maps/mp_phase_runner_preview.bsp').exists())
        script=(PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut').read_text();self.assertIn('GetMapName() != "mp_phase_runner"',script)
        config=json.loads((PACKAGE/'paks/rpak.json').read_text());self.assertEqual(config['Aliases']['mp_phase_runner_loadscreen.rpak'],'phase_runner_presentation.rpak')
        self.assertEqual(config['Postload']['phase_runner_presentation.rpak'],'common.rpak')
        for language in LANGUAGES:
            p=PACKAGE/f'mod/resource/phase_runner_{language}.txt';self.assertEqual(p.read_bytes()[:2],b'\xff\xfe');text=p.read_text(encoding='utf-16')
            self.assertIn('"mp_phase_runner" "Phase Runner"',text);self.assertIn('"mp_phase_runner_ALLCAPS" "PHASE RUNNER"',text);self.assertIn('mp_phase_runner_CLASSIC_DESC',text)
        pak=NativePak(PACKAGE/'paks/phase_runner_presentation.rpak');assets={a['guid']:a for a in pak.assets}
        for name in ('mp_phase_runner_widescreen','mp_phase_runner','mp_phase_runner_lobby'):
            self.assertIn(guid('material/loadscreens/'+name+'_gen.rpak'),assets)
        self.assertEqual(collections.Counter(a['type'] for a in pak.assets),{'txtr':1,'uimg':1,'matl':3})
        # All expected RUI image hashes exist in the loaded atlas.
        u=next(a for a in pak.assets if a['type']=='uimg');addr=pak.address(u['header']);ptr=struct.unpack_from('<2I',pak.data,addr+40);at=pak.address(ptr)
        hashes=[struct.unpack_from('<I',pak.data,at+i*8)[0] for i in range(3)]
        for name in ('mp_phase_runner_lobby','mp_phase_runner','mp_phase_runner_widescreen'):
            result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),'-uimghash','loadscreens/'+name],capture_output=True,text=True,check=True)
            self.assertIn(int(result.stdout.strip(),16),hashes)

    def test_requested_old_build_backup_is_complete(self):
        backup=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.36-before-catwalks';checks=json.loads((backup/'checksums.json').read_text())
        self.assertEqual(json.loads((backup/'mod.json').read_text())['Version'],'0.1.36')
        for rel,sha in checks.items():self.assertEqual(digest(backup/rel),sha,rel)
        self.assertTrue((ROOT/'output/PhaseRunner.Preview-0.1.36.zip').is_file())

if __name__=='__main__':unittest.main()
