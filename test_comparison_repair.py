"""Verify the incremental repair does not regress working geometry or physics."""
import hashlib,json,struct,unittest
from pathlib import Path
from recover_vertex_paint import ROOT,CONFIG,np,DT
from repair_preview_index_padding import read_lumps,validate_index_padding
from audit_world_draw_budget import audit

class RepairTests(unittest.TestCase):
    def test_only_authored_paint_and_material_bindings_change(self):
        for label,(package,name,_,_) in CONFIG.items():
            with self.subTest(map=label):
                before=ROOT/'output/repair-backups/20261012-vertex-paint'/package/'mod/maps'/(name+'.bsp')
                after=ROOT/'northstar'/package/'mod/maps'/(name+'.bsp')
                a=read_lumps(before,range(128));b=read_lumps(after,range(128))
                allowed={2,0x23,0x2b,0x2c,0x49,0x52}
                self.assertEqual([i for i in range(128) if i not in allowed and a[i]!=b[i]],[])
                va=np.frombuffer(a[0x49],DT);vb=np.frombuffer(b[0x49],DT);vc=vb.copy();vc['color']=va['color']
                self.assertEqual(va.tobytes(),vc.tobytes())
                self.assertTrue(np.array_equal(va['color'][:,3],vb['color'][:,3]))
                changed=np.flatnonzero(np.any(va['color']!=vb['color'],axis=1))
                report=json.loads((ROOT/'output/comparison-repair'/label/'vertex-paint.json').read_text())
                self.assertEqual(len(changed),report['changed_vertices']);self.assertGreater(len(changed),10000)
                oldsort=np.frombuffer(a[0x52],dtype='V12');newsort=bytearray(b[0x52])
                self.assertEqual(len(a[0x52]),len(b[0x52]))
                for i in range(len(oldsort)):newsort[i*12:i*12+2]=a[0x52][i*12:i*12+2]
                self.assertEqual(bytes(newsort),a[0x52])
                aa=audit(before);bb=audit(after);self.assertEqual({k:v for k,v in aa.items() if k!='path'},{k:v for k,v in bb.items() if k!='path'})
                validate_index_padding(b[0x50],b[0x4f],b[0x52])

    def test_shader_retains_opaque_depth_state_and_existing_pbr_channels(self):
        from extract_native_material import NativePak
        for label,(package,name,_,_) in CONFIG.items():
            folder=ROOT/'output/comparison-repair'/label
            proof=json.loads((folder/'shader.json').read_text())
            self.assertTrue(proof['all_dependencies_resolved']);self.assertTrue(proof['material_states_and_pbr_channels_preserved'])
            manifest=json.loads((folder/'shader-build.json').read_text());assets=Path(manifest['assetsDir'])
            pack='composite_world' if label=='drop-off' else 'phase_runner_world'
            source=NativePak(ROOT/'northstar'/package/'paks'/(pack+'.rpak'))
            specs={}
            for a in source.assets:
                if a['type']=='matl':
                    s,_=source.material(a);specs[s['name']]=s
            for entry in manifest['files']:
                if entry['_type']!='matl':continue
                s=json.loads((assets/entry['_path']).with_suffix('.json').read_text())
                old=specs[s['name'].replace('_paint_colpass','_colpass').removesuffix('_paint')]
                for field in ('depthStencilFlags','rasterizerFlags','blendStateMask'):
                    self.assertEqual(s[field],old[field])
                self.assertEqual(s['blendStates'][:4],old['blendStates'])
                self.assertEqual(set(s['$textures']),set(old['$textures']))
                for channel,texture in s['$textures'].items():
                    if texture.startswith('0x'):
                        self.assertEqual(texture,old['$textures'][channel]);continue
                    copied=(assets/texture).with_suffix('.dds')
                    folders=([ROOT/'output/composite/materials/assets'] if label=='drop-off' else
                             [ROOT/'output/phase-runner/balanced-materials/assets',ROOT/'output/phase-runner/world-materials/assets'])
                    original=next(p for folder0 in folders for p in folder0.rglob(copied.name))
                    self.assertEqual(hashlib.sha256(copied.read_bytes()).digest(),hashlib.sha256(original.read_bytes()).digest())
                self.assertEqual(int(s['glueFlags2'],16)&2,2)
                self.assertTrue(all(k in s['$textures'] for k in ('0','1','2','3')))
            for native in proof['native_shader_sets']:
                self.assertTrue(native['unchanged_bytecode']);self.assertGreater(len(native['vertex_variants']),0)

if __name__=='__main__':unittest.main()
