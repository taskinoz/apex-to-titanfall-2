"""Source recovery, alpha pipeline, physics and immutable-scene regression checks."""
import collections,json,mmap,os,struct,unittest
from build_phase_runner_firs import ROOT,P,SOURCE,TARGET,PACKAGE,MATERIALS,MODEL,LEAVES,dds_image
from repair_preview_index_padding import read_lumps,validate_index_padding
from build_phase_runner_catwalks import mesh_faces,face_key
from build_center_detail import active
from read_prop_physics import read_phy
from stage_prop_geometry import rotation
from optimize_portalfree_render import material_name,DT
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from preview_visibility import validate_visibility
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from finalize_lighting_release import digest
import numpy as np

class Trees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(2,3,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x57,0x59,0x5c,0x42,0x45,0x77,0x78,0x79,0x7b)
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids);cls.report=json.loads(TARGET.with_name('trees.json').read_text())
    def test_existing_lumps_attributes_lighting_and_packages_preserved(self):
        changed={2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x42,0x44,0x45,0x60,0x56,0x57,0x58,0x59,0x5a,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f}
        with SOURCE.open('rb') as f,TARGET.open('rb') as g,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as a,mmap.mmap(g.fileno(),0,access=mmap.ACCESS_READ) as b:
            for i in set(range(128))-changed:
                x,n=struct.unpack_from('<2I',a,16+i*16);y,m=struct.unpack_from('<2I',b,16+i*16)
                if i==0x23:self.assertEqual(a[x+20:x+n],b[y+20:y+m]);continue
                self.assertEqual(a[x:x+n],b[y:y+m],hex(i))
            for i in (2,3,0x1e,0x49,0x4f,0x52,0x53,0x62,0x69,0x42,0x44,0x45,0x60):
                x,n=struct.unpack_from('<2I',a,16+i*16);y,m=struct.unpack_from('<2I',b,16+i*16)
                self.assertGreaterEqual(m,n);self.assertEqual(a[x:x+n],b[y:y+n],hex(i))
        for p in (SOURCE.parents[2]/'paks').glob('*.rpak'):
            self.assertEqual(digest(p),digest(PACKAGE/'paks'/p.name),p.name)
    def test_every_existing_mesh_record_and_bounds_preserved(self):
        mapping=self.report['retained_meshes'];self.assertEqual(len(mapping),len(self.old[0x50])//28)
        for before,after in enumerate(mapping):
            self.assertEqual(self.old[0x50][before*28:(before+1)*28],self.new[0x50][after*28:(after+1)*28])
            self.assertEqual(self.old[0x51][before*32:(before+1)*32],self.new[0x51][after*32:(after+1)*32])
    def test_tree_mesh_positions_uvs_and_twenty_authored_placements(self):
        data=np.load(TARGET.with_name('source-geometry.npz'));wanted=collections.Counter();got=collections.Counter()
        for mat,t in zip(data['materials'],data['data']):wanted[(mat,b''.join(sorted(v.tobytes() for v in np.column_stack((t[:,:3],t[:,6:8])))))]+=1
        vertices=np.frombuffer(self.new[0x49],DT);added=set(self.report['new_meshes'])
        for i,r,raw,ids,tri in mesh_faces(self.new):
            if i not in added:continue
            tex=struct.unpack_from('<h',self.new[0x52],r[-2]*12)[0];mat=material_name(self.new,tex).rsplit('/',1)[-1]
            for t,vi in zip(tri,ids):got[(mat,b''.join(sorted(v.tobytes() for v in np.column_stack((t,vertices['uv'][vi])))))]+=1
        self.assertEqual(got,wanted);self.assertEqual(sum(got.values()),20280)
        source=json.loads((P/'static-props.json').read_text());props=self.report['source_placements'];self.assertEqual(len(props),20)
        self.assertEqual(len({p['index'] for p in props}),20)
        for p in props:
            self.assertEqual(p['source_lod'],2)
            for key in ('model','origin','angles','scale','skin'):self.assertEqual(p[key],source[p['index']][key])
    def test_restored_models_are_full_size_trees_with_canopies(self):
        from read_vg_static import load
        sections,slots,skins=load(ROOT/'tools/legion/exported_files/models'/MODEL,2)
        self.assertEqual([len(x) for x in sections],[62,952])
        data=np.load(TARGET.with_name('source-geometry.npz'))['data']
        for p in self.report['source_placements']:
            xyz=data[p['first_triangle']:p['first_triangle']+p['triangles'],:,:3]
            self.assertGreater(np.ptp(xyz[:,:,2]),700.)
            self.assertGreater(np.ptp(xyz[:,:,0]),200.)
            self.assertTrue('tree_fir_large_arenas_01' in p['model'])
    def test_exact_source_trunk_physics_and_existing_active_collision(self):
        pieces=read_phy(ROOT/f'tools/legion/exported_files/models/{MODEL}/{MODEL}.phy')
        local=np.asarray([[f[0],f[j],f[j+1]] for piece in pieces for f in piece for j in range(1,len(f)-1)],'<f4')
        source={p['index']:p for p in json.loads((P/'static-props.json').read_text())};pos=np.frombuffer(self.new[3],'<f4').reshape(-1,3)
        heads=list(struct.iter_unpack('<6h4i4f',self.new[0x45]));added=set()
        for owner in self.report['collision']['owners']:
            p=source[owner['index']];expected=(local@np.asarray(rotation(p['angles'])).T*p['scale']+p['origin']).astype('<f4')
            expected=expected[np.linalg.norm(np.cross(expected[:,1]-expected[:,0],expected[:,2]-expected[:,0]),axis=1)>1e-5]
            actual=[]
            for hi in range(owner['first_header'],owner['first_header']+owner['headers']):
                added.add((0x40,hi));h=heads[hi];actual.extend(pos[h[6]:h[6]+h[3]].reshape(-1,3,3))
            self.assertEqual(collections.Counter(face_key(t) for t in expected),collections.Counter(face_key(t) for t in actual))
        self.assertEqual(active(self.new),active(self.old)|added)
        self.assertEqual(self.old[0x5c],self.new[0x5c]);self.assertEqual(len(self.report['collision']['owners']),20)
    def test_native_cutout_alpha_and_local_shader_dependencies(self):
        pak=NativePak(MATERIALS/'build/phase_runner_firs.rpak');assets={a['guid']:a for a in pak.assets}
        native=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak');common=NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak')
        leaves=[]
        for a in pak.assets:
            if a['type']!='matl':continue
            s,u=pak.material(a)
            if LEAVES not in s['name']:continue
            leaves.append(s);self.assertFalse(int(s['rasterizerFlags'],16)&4)
            for key in ('shaderSet','$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
                g=int(s[key],16)
                if g:self.assertIn(g,assets)
        self.assertEqual(len(leaves),15)
        for f in (MATERIALS/'assets/shaderset').glob('*.msw'):
            original=int(f.stem.rsplit('_',1)[-1],16);old=next(a for a in native.assets if a['guid']==original);h=native.address(old['header']);vs,ps=struct.unpack_from('<2Q',native.data,h+72)
            from build_phase_runner_presentation import guid
            new=assets[guid('shaderset/'+f.stem+'.rpak')];h=pak.address(new['header']);newvs,newps=struct.unpack_from('<2Q',pak.data,h+72)
            for before,after in ((vs,newvs),(ps,newps)):
                owner=native if any(a['guid']==before for a in native.assets) else common
                self.assertEqual(shader(owner,next(a for a in owner.assets if a['guid']==before)),shader(pak,assets[after]))
        for name in sorted({p['name'].rsplit('/',1)[-1] for p in leaves if not p['name'].endswith(('_shadow','_prepass','_vsm','_colpass'))}):
            folder=ROOT/'tools/legion/exported_files/materials'/name
            a=np.array(dds_image(folder/(name+'_albedoTexture.dds')))[:,:,3].astype(float)
            b=np.array(dds_image(folder/(name+'_opacityMultiplyTexture.dds')))[:,:,0].astype(float)
            actual=np.array(dds_image(MATERIALS/(name+'_cutout.dds')))[:,:,3].astype(float)
            self.assertLess(np.mean(abs(actual-a*b/255)),3.)
            self.assertEqual(int(actual.min()),0);self.assertEqual(int(actual.max()),255)
            self.assertGreater(np.mean(actual>=128),.20)
    def test_visibility_native_padding_partitions_and_safe_budget(self):
        result=validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51]);self.assertEqual(result['reachable_meshes'],len(self.new[0x50])//28)
        validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        boxes=np.frombuffer(self.new[0x77]+self.new[0x79],'<f4').reshape(-1,8)
        for p in self.report['source_placements']:
            camera=np.asarray(p['origin'])+[0,0,64];self.assertTrue(np.all((boxes[:,:3]<=camera)&(boxes[:,4:7]>=camera)))
        b=enforce_camera_bypass_budget(TARGET);self.assertLess(b['static_batch_runs'],512);self.assertLess(b['native_padded_indices'],WORLD_INDEX_CAPACITY*.95);self.assertEqual(b['real_triangles'],952348+20280)
        op,tr,total=struct.unpack_from('<3I',self.new[0x7b]);self.assertEqual(op,tr)
        for i in range(total):self.assertEqual(bool(struct.unpack_from('<I',self.new[0x50],i*28+24)[0]&0x10),i>=tr)
    def test_leaf_mips_retain_needle_coverage(self):
        import io
        from PIL import Image
        for path in MATERIALS.glob('*_cutout.dds'):
            data=path.read_bytes();h,w=struct.unpack_from('<2I',data,12);count=struct.unpack_from('<I',data,28)[0];offset=128
            target=None
            for mip in range(count):
                size=max(1,(w+3)//4)*max(1,(h+3)//4)*16
                header=bytearray(data[:128]);struct.pack_into('<2I',header,12,h,w);struct.pack_into('<I',header,28,1)
                alpha=np.array(Image.open(io.BytesIO(header+data[offset:offset+size])).convert('RGBA'))[:,:,3]
                coverage=float(np.mean(alpha>=128))
                if mip==0:target=coverage
                elif w>=16:self.assertLess(abs(coverage-target),.06,(path.name,mip,coverage,target))
                offset+=size;w=max(1,w//2);h=max(1,h//2)
            self.assertEqual(offset,len(data))
    def test_sidecar_preserves_resident_assets_and_adds_tree_materials(self):
        a=SOURCE.with_suffix('.stbsp').read_bytes();b=TARGET.with_suffix('.stbsp').read_bytes()
        for i in range(6):
            o,n=struct.unpack_from('<2Q',a,168+i*16);p,m=struct.unpack_from('<2Q',b,168+i*16);stride=24 if i in (1,4) else 1;self.assertEqual(a[o:o+n*stride],b[p:p+n*stride])
            if i>=2:self.assertEqual(n,m)
        self.assertEqual(len(self.report['resident_added_materials']),4)
    def test_new_trunk_probes_start_outside_existing_brushes(self):
        before=read_lumps(SOURCE,(1,0x5c,0x57,0x59));live=active(before);planes=np.frombuffer(before[1],'<f4').reshape(-1,4)
        for probe in self.report['collision']['probes']:
            p=np.asarray(probe['start'])
            for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',before[0x5c])):
                if (0,i) not in live:continue
                if np.any(p<np.asarray(r[:3])-r[6:9]-.01) or np.any(p>np.asarray(r[:3])+r[6:9]+.01):continue
                cuts=planes[1+r[9]:1+r[9]+r[4]]
                self.assertFalse(np.all(cuts[:,:3]@p<=cuts[:,3]+.01),(probe['index'],i))
        self.assertEqual(len(self.report['collision']['probes']),40)
    def test_editable_release_metadata_does_not_share_baseline_files(self):
        baseline=SOURCE.parents[2]
        for p in baseline.rglob('*'):
            if p.is_file() and p.suffix not in ('.bsp','.stbsp','.rpak'):
                other=PACKAGE/p.relative_to(baseline)
                if other.exists():self.assertFalse(os.path.samefile(p,other),str(p.relative_to(baseline)))

if __name__=='__main__':unittest.main()
