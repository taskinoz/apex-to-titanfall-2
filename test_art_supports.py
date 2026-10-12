"""Exact scene preservation, source props, native alpha decals and physics."""
import collections,io,json,mmap,struct,unittest
from build_art_supports import ROOT,SOURCE,TARGET,PACKAGE,MATERIALS,SUPPORTS,PIPES,DECAL,NEWDECAL
from repair_preview_index_padding import read_lumps,validate_index_padding
from build_phase_runner_catwalks import mesh_faces,face_key
from build_center_detail import active
from optimize_portalfree_render import material_name,DT
from preview_visibility import validate_visibility
from extract_native_material import NativePak
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from PIL import Image
import numpy as np

class ArtSupports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(2,3,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x57,0x59,0x5c,0x77,0x78,0x79,0x7b)
        cls.old=read_lumps(SOURCE,ids);cls.new=read_lumps(TARGET,ids);cls.report=json.loads(TARGET.with_name('art-supports.json').read_text())
    def test_unrelated_lumps_and_original_attribute_prefixes(self):
        changed={1,2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x57,0x58,0x59,0x5a,0x5c,0x5d,0x5e,0x5f,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f}
        with SOURCE.open('rb') as f,TARGET.open('rb') as g,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as a,mmap.mmap(g.fileno(),0,access=mmap.ACCESS_READ) as b:
            for i in set(range(128))-changed:
                x,n=struct.unpack_from('<2I',a,16+i*16);y,m=struct.unpack_from('<2I',b,16+i*16)
                if i==0x23:self.assertEqual(a[x+20:x+n],b[y+20:y+m]);continue
                self.assertEqual(a[x:x+n],b[y:y+m],hex(i))
            for i in (1,3,0x1e,0x49,0x53,0x62,0x69,0x5c,0x5d,0x5e,0x5f):
                x,n=struct.unpack_from('<2I',a,16+i*16);y,m=struct.unpack_from('<2I',b,16+i*16)
                self.assertGreaterEqual(m,n);self.assertEqual(a[x:x+n],b[y:y+n],hex(i))
    def test_retained_faces_uvs_and_only_decal_bindings_changed(self):
        faces={i:(r,ids,tri) for i,r,raw,ids,tri in mesh_faces(self.old)};newfaces={i:(r,ids,tri) for i,r,raw,ids,tri in mesh_faces(self.new)};counts=0
        for h in self.report['retained_meshes']:
            oldr,oldids,oldtri=faces[h['source_mesh']];r,ids,tri=newfaces[h['new_mesh']];selection=h['retained_triangles']
            self.assertTrue(np.array_equal(ids,oldids[selection]));self.assertTrue(np.array_equal(tri,oldtri[selection]))
            oldsort=struct.unpack_from('<3hHI',self.old[0x52],oldr[-2]*12);s=struct.unpack_from('<3hHI',self.new[0x52],r[-2]*12)
            self.assertEqual(oldsort[1:],s[1:]);name=material_name(self.old,oldsort[0])
            if name.endswith('/'+DECAL):
                self.assertTrue(material_name(self.new,s[0]).endswith('/'+NEWDECAL));self.assertEqual(r[-1],oldr[-1]|0x10);counts+=r[1]
            else:self.assertEqual(oldsort[0],s[0]);self.assertEqual(oldr[-1],r[-1])
        self.assertEqual(counts,self.report['road_decal_triangles_rebound']);self.assertGreater(counts,0)
    def test_all_new_rendered_corners_match_original_source_and_full_pipe_lod(self):
        arr=np.load(TARGET.with_name('source-geometry.npz'));data=arr['data'];mats=arr['materials'];v=np.frombuffer(self.new[0x49],DT)
        wanted=collections.Counter()
        for mat,t in zip(mats,data):
            wanted[(mat,b''.join(sorted(q.tobytes() for q in np.column_stack((t[:,:3],t[:,6:8])))))]+=1
        got=collections.Counter();newids=set(self.report['new_meshes'])
        for i,r,raw,ids,tri in mesh_faces(self.new):
            if i not in newids:continue
            s=struct.unpack_from('<3hHI',self.new[0x52],r[-2]*12);mat=material_name(self.new,s[0]).rsplit('/',1)[-1]
            for t,vi in zip(tri,ids):got[(mat,b''.join(sorted(q.tobytes() for q in np.column_stack((t,v['uv'][vi])))))]+=1
        self.assertEqual(got,wanted);self.assertEqual(len(data),13060)
        p={p['index']:p for p in self.report['source_placements']};self.assertEqual(set(p),set(SUPPORTS+PIPES));self.assertEqual(p[8483]['triangles'],720);self.assertEqual(p[8484]['triangles'],400)
        original=json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
        for i,row in p.items():
            for field in ('origin','angles','scale','skin'):self.assertEqual(row[field],original[i][field])
    def test_all_original_collision_active_and_every_added_brush_live(self):
        old=active(self.old);new=active(self.new);first=len(self.old[0x5c])//32;last=len(self.new[0x5c])//32
        self.assertEqual(new,old|{(0,i) for i in range(first,last)});self.assertGreater(last,first)
        owners=[p for group in self.report['collision'] for p in group['owners']];self.assertEqual({p['index'] for p in owners},set(SUPPORTS))
        self.assertTrue(all(p['method']=='original_IRPS_convex_with_sweep_bevels' for p in owners));self.assertEqual(sum(p['brushes'] for p in owners),last-first)
    def test_native_transparent_ranges_visibility_and_draw_headroom(self):
        validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51]);validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        op,tr,sky=struct.unpack_from('<3I',self.new[0x7b]);self.assertEqual(op,tr);self.assertEqual(sky,len(self.new[0x50])//28)
        for i in range(sky):self.assertEqual(bool(struct.unpack_from('<I',self.new[0x50],i*28+24)[0]&0x10),i>=tr)
        b=enforce_camera_bypass_budget(TARGET);self.assertLess(b['static_batch_runs'],512);self.assertLess(b['native_padded_indices'],WORLD_INDEX_CAPACITY*.95)
    def test_alpha_mask_native_decal_bias_and_old_materials(self):
        pak=NativePak(MATERIALS/'build/phase_runner_art_supports.rpak');spec=None
        for a in pak.assets:
            if a['type']!='matl':continue
            s,b=pak.material(a)
            if s['name'].endswith('/'+NEWDECAL):spec=s
        self.assertIsNotNone(spec);self.assertEqual(spec['rasterizerFlags'],'0x16');self.assertEqual(spec['depthStencilFlags'],'0x7');self.assertEqual(spec['blendStateMask'],'0x5');self.assertIn('13',spec['$textures'])
        def image(path):
            r=bytearray(path.read_bytes())
            if r[84:88]==b'DX10':
                fmt=struct.unpack_from('<I',r,128)[0]
                if fmt in (72,75,78,99):struct.pack_into('<I',r,128,fmt-1)
            return np.array(Image.open(io.BytesIO(r)).convert('RGBA'))
        alpha=image(ROOT/f'tools/legion/exported_files/materials/{DECAL}/{DECAL}_albedoTexture.dds')[:,:,3]
        mask=image(MATERIALS/f'assets/texture/phase_runner_preview/{NEWDECAL}_opacity.dds')[:,:,0]
        self.assertEqual(alpha.shape,mask.shape);self.assertLess(np.mean(abs(mask.astype(float)-alpha)),4.);self.assertEqual(int(mask.min()),0);self.assertEqual(int(mask.max()),255)
        for n in ('phase_runner_world','phase_runner_detail','phase_runner_presentation','phase_runner_glass_console'):
            self.assertEqual(digest(PACKAGE/f'paks/{n}.rpak'),digest(ROOT/f'northstar/PhaseRunner.Preview/paks/{n}.rpak'))
    def test_resident_sidecar_original_data_and_new_material_guids(self):
        a=SOURCE.with_suffix('.stbsp').read_bytes();b=TARGET.with_suffix('.stbsp').read_bytes()
        for i in range(6):
            o,n=struct.unpack_from('<2Q',a,168+i*16);p,m=struct.unpack_from('<2Q',b,168+i*16);stride=24 if i in (1,4) else 1;self.assertEqual(a[o:o+n*stride],b[p:p+n*stride])
            if i>=2:self.assertEqual(n,m)
        self.assertEqual(len(self.report['resident_added_materials']),4)
if __name__=='__main__':unittest.main()
