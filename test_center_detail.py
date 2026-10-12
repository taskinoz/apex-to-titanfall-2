"""Check localized source restoration, native draw limits and exact preservation."""
import collections,json,struct,unittest
from build_center_detail import ROOT,P,SOURCE,TARGET,PACKAGE,MATERIALS,TRUCK,active
from build_phase_runner_catwalks import mesh_faces,face_key
from optimize_portalfree_render import DT
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from finalize_lighting_release import digest
import numpy as np

class CenterDetailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(1,2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x5d,0x5e,0x5f,0x57,0x59,0x77,0x78,0x79,0x7c,0x7e,0x7f)
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids)
        cls.report=json.loads((TARGET.parent/'center-detail.json').read_text());cls.geometry=np.load(TARGET.parent/'center-geometry.npz')
        cls.before=list(mesh_faces(cls.old));cls.after=list(mesh_faces(cls.new))

    def test_unrelated_render_corners_bindings_bounds_and_lightmaps_exact(self):
        old=self.old;new=self.new;ov=np.frombuffer(old[0x49],DT);nv=np.frombuffer(new[0x49],DT)
        for m in self.report['retained_meshes']:
            a=self.before[m['source_mesh']];b=self.after[m['new_mesh']];take=m['retained_triangles']
            np.testing.assert_array_equal(a[2][take],b[2]);np.testing.assert_array_equal(a[3][take],b[3]);np.testing.assert_array_equal(a[4][take],b[4])
            self.assertEqual(a[1][4:],b[1][4:]);np.testing.assert_array_equal(ov[a[3][take]],nv[b[3]])
            if len(take)==len(a[4]):self.assertEqual(old[0x51][a[0]*32:a[0]*32+32],new[0x51][b[0]*32:b[0]*32+32])
        for i in (1,2,3,0x1e,0x2b,0x2c,0x49,0x52,0x53,0x62,0x69,0x5c,0x5d,0x5e,0x5f):self.assertTrue(new[i].startswith(old[i]),hex(i))
        for i in (0x42,0x44,0x45,0x60):self.assertEqual(old[i],new[i],hex(i))

    def test_only_old_nessie_faces_replaced_and_all_source_additions_exact(self):
        expected={bytes.fromhex(k) for k in json.loads((TARGET.parent/'old-nessie-keys.json').read_text())}
        removed=[]
        for m in self.report['retained_meshes']:
            old=self.before[m['source_mesh']];take=set(m['retained_triangles'])
            removed.extend(face_key(t) for i,t in enumerate(old[4]) if i not in take)
        mapped={m['source_mesh'] for m in self.report['retained_meshes']}
        for mi,r,raw,ids,t in self.before:
            if mi not in mapped:removed.extend(map(face_key,t))
        self.assertEqual(len(removed),59);self.assertEqual(set(removed),expected)
        actual=collections.Counter(t.tobytes() for mi in self.report['new_meshes'] for t in self.after[mi][4][:,[0,2,1]])
        authored=collections.Counter(t.tobytes() for t in self.geometry['data'][:,:,:3]);self.assertEqual(actual,authored)
        nessie=next(p for p in self.report['source_geometry']['placements'] if p['index']==7806)
        self.assertEqual(nessie['source_lod'],0);self.assertEqual(nessie['triangles'],1442)
        self.assertEqual(nessie['origin'],[2914.69921875,902.0,-1074.6199951171875]);self.assertEqual(nessie['scale'],1.5)
        placements=self.report['source_geometry']['placements'];self.assertEqual(len(placements),210)
        self.assertEqual(sum(PathModel(p)==TRUCK for p in placements),3)
        self.assertEqual(sum('/rocks/icelandic_rockcluster_' in p['model'] for p in placements),206)

    def test_source_material_uv_smooth_normals_tangent_frames_and_luxels(self):
        l=self.new;v=np.frombuffer(l[0x49],DT);n=np.frombuffer(l[0x1e],'<f4').reshape(-1,3)
        source=self.geometry['data'];attributes=collections.Counter((t[:,:3].tobytes(),t[:,3:].tobytes(),str(mat)) for t,mat in zip(source,self.geometry['materials']))
        actual=collections.Counter();sorts=list(struct.iter_unpack('<3hHI',l[0x52]));oldpages=len(self.old[0x53])//8
        for mi in self.report['new_meshes']:
            _,r,raw,ids,p=self.after[mi];ids=ids[:,[0,2,1]];p=p[:,[0,2,1]];nn=n[v['ni'][ids]];tangent=n[v['tangent'][ids]&0x7fffffff]
            self.assertTrue(np.allclose(np.linalg.norm(nn,axis=2),1,atol=1e-5));self.assertTrue(np.allclose(np.linalg.norm(tangent,axis=2),1,atol=1e-5));self.assertTrue(np.allclose((nn*tangent).sum(2),0,atol=1e-5))
            self.assertTrue(np.all(np.isfinite(v['light'][ids])));self.assertTrue(np.all((v['light'][ids][...,:2]>=0)&(v['light'][ids][...,:2]<=1)))
            ti,pg,*_=sorts[r[-2]];self.assertGreaterEqual(pg,oldpages)
            row=struct.unpack_from('<3f6I',l[2],ti*36);off=struct.unpack_from('<I',l[0x2c],row[3]*4)[0];mat=l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/').rsplit('/',1)[-1]
            for a,b,u in zip(p,nn,v['uv'][ids]):actual[(a.tobytes(),np.column_stack((b,u)).astype('<f4').tobytes(),mat)]+=1
        self.assertEqual(actual,attributes)
        nessie=next(p for p in self.report['source_geometry']['placements'] if p['index']==7806);s=source[nessie['first_triangle']:nessie['first_triangle']+nessie['triangles']]
        self.assertGreater(np.count_nonzero(np.linalg.norm(s[:,0,3:6]-s[:,1,3:6],axis=1)>.05),500)
        self.assertGreater(self.report['light_bake']['valid_luxels'],10000)

    def test_collision_only_appends_original_truck_hulls(self):
        old=active(self.old);new=active(self.new);col=self.report['collision'];first=col['first_new_brush']
        self.assertEqual(new-old,{(0,i) for i in range(first,first+col['new_brushes'])});self.assertFalse(old-new)
        self.assertEqual(len(col['owners']),3)
        original={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
        from read_prop_physics import read_phy
        from stage_prop_geometry import transform,rotation
        for owner in col['owners']:
            prop=original[owner['index']];base=ROOT/'tools/legion/exported_files/models'/TRUCK/TRUCK;pieces=read_phy(base.with_suffix('.phy'))
            self.assertEqual(owner['brushes'],len(pieces))
            for i,piece in enumerate(pieces):
                row=struct.unpack_from('<3f2BH3fI',self.new[0x5c],(owner['first_brush']+i)*32);lo=np.array(row[:3])-row[6:9];hi=np.array(row[:3])+row[6:9]
                points=np.array([transform(v,rotation(prop['angles']),prop['origin'],prop['scale']) for face in piece for v in face]);self.assertTrue(np.all(points>=lo-.001));self.assertTrue(np.all(points<=hi+.001))
                planes=np.frombuffer(self.new[1],'<f4').reshape(-1,4)[1+row[9]:1+row[9]+row[3]];self.assertTrue(np.all(points@planes[:,:3].T<=planes[:,3]+.08))
        for p in self.report['source_geometry']['placements']:
            if '/rocks/' in p['model']:self.assertEqual(p['solid_mode'],0)

    def test_whole_map_camera_guard_batch_and_index_capacity(self):
        l=self.new;validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51]);validate_index_padding(l[0x50],l[0x4f],l[0x52]);budget=enforce_camera_bypass_budget(TARGET)
        self.assertLessEqual(budget['native_padded_indices'],WORLD_INDEX_CAPACITY*.9);self.assertLess(budget['static_batch_runs'],512)
        self.assertEqual(budget['maximum_all_visible_mesh_prefix'],budget['meshes']);self.assertEqual(budget['real_triangles'],881966-59+57439)
        from test_world_batch_order import native_bytes,simulate_submission
        self.assertEqual(native_bytes(0xb7304,7),b'\x41\x81\xff'+struct.pack('<I',2048))
        emitted,runs,indices=simulate_submission(l[0x50]);self.assertEqual(emitted,list(range(budget['meshes'])));self.assertEqual(runs,budget['static_batch_runs']);self.assertEqual(indices,budget['native_padded_indices'])
        for row in struct.iter_unpack('<3fI3fI',l[0x79]):self.assertTrue(np.all(np.array(row[:3])<=-np.array([12288,12288,4096])));self.assertTrue(np.all(np.array(row[4:7])>=[12288,12288,4096]))

    def test_original_nessie_support_uses_full_detail_truck(self):
        proof=json.loads((TARGET.parent/'nessie-support-proof.json').read_text())
        self.assertEqual(proof['truck'],16850);self.assertGreater(proof['contact_samples'],30)
        self.assertLessEqual(proof['maximum_foot_gap'],4);self.assertGreaterEqual(proof['minimum_foot_gap'],-4)
        truck=next(p for p in self.report['source_geometry']['placements'] if p['index']==16850)
        self.assertEqual(truck['source_lod'],0);self.assertEqual(truck['triangles'],10401)

    def test_every_other_bsp_payload_bit_exact(self):
        changed={1,2,3,5,0xe,0x1e,0x23,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b,0x5c,0x5d,0x5e,0x5f,0x56,0x57,0x58,0x59,0x5a,0x77,0x78,0x79,0x7c,0x7e,0x7f}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ah=a.read(2064);bh=b.read(2064)
            for i in range(128):
                if i in changed:continue
                ao,an,av,ap=struct.unpack_from('<4I',ah,16+i*16);bo,bn,bv,bp=struct.unpack_from('<4I',bh,16+i*16)
                self.assertEqual((an,av,ap),(bn,bv,bp),hex(i));a.seek(ao);b.seek(bo)
                for at in range(0,an,8*1024*1024):n=min(8*1024*1024,an-at);self.assertEqual(a.read(n),b.read(n),hex(i))

    def test_presentation_original_material_rpak_and_probe_assets_preserved(self):
        self.assertEqual(json.loads((PACKAGE/'mod.json').read_text())['Version'],'0.1.41')
        base=ROOT/'northstar/PhaseRunner.Preview'
        for rel in ('paks/phase_runner_world.rpak','paks/phase_runner_presentation.rpak'):
            self.assertEqual(digest(base/rel),digest(PACKAGE/rel))
        for file in (base/'mod/resource').iterdir():self.assertEqual(file.read_bytes(),(PACKAGE/'mod/resource'/file.name).read_bytes())
        config=json.loads((PACKAGE/'paks/rpak.json').read_text());self.assertEqual(config['Postload']['phase_runner_detail.rpak'],'mp_coliseum.rpak')
        self.assertTrue(json.loads((MATERIALS/'validation.json').read_text())['all_dependencies_present'])
        self.assertTrue(self.report['resident_sidecar']['column_payload_preserved'])

def PathModel(p):return p['model'].rsplit('/',1)[-1].rsplit('.',1)[0]
if __name__=='__main__':unittest.main()
