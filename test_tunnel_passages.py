"""Check surgical collider adaptation and preservation of working rendering."""
import json,struct,unittest
import numpy as np
from repair_tunnel_passages import SOURCE,TARGET,ROOT,P
from repair_preview_index_padding import read_lumps,validate_index_padding
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from package_northstar import validate_bsp
from stage_prop_geometry import rotation
from read_vg_static import load

class TunnelPassageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads(TARGET.with_name('tunnel-collision-repair.json').read_text())
        cls.source=read_lumps(SOURCE,range(128));cls.output=read_lumps(TARGET,range(128))

    def test_working_render_and_all_unrelated_lumps_preserved(self):
        changed={3,0x42,0x44,0x45,0x60,0x55,0x56,0x57,0x58,0x59,0x5a}
        for i in range(128):
            if i not in changed and i!=0x23:self.assertEqual(self.source[i],self.output[i],f'lump {i}')
        for i in (3,0x42,0x44,0x45,0x60):self.assertTrue(self.output[i].startswith(self.source[i]),f'prefix {i}')

    def test_grid_disables_only_replaced_source_shapes(self):
        def active(l):
            values=[w[0] for w in struct.iter_unpack('<I',l[0x59])]
            values += [w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
            return {((w>>24),(w>>8)&65535) for w in values}
        before=active(self.source);after=active(self.output)
        removed={(0,i) for i in self.report['disabled_convex_brushes']}|{(0x40,i) for i in self.report['disabled_world_headers']}
        self.assertEqual(before-after,removed)
        count=len(self.source[0x45])//44
        self.assertEqual(after-before,{(0x40,i) for i in range(count,len(self.output[0x45])//44)})

    def test_world_changes_restricted_to_tool_caps(self):
        labels=json.loads((ROOT/'logs/world-source-materials.json').read_text())
        from audit_world_collision_contents import load_world
        world,_=load_world();allowed=set(self.report['allowed_materials'])
        for event in self.report['cap_adaptations']:
            self.assertTrue(any(s.lower().replace('\\','/') in allowed for s in labels[event['triangle']]))
            t=world[event['triangle']];n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
            self.assertLess(abs(n[2]),.201)
        self.assertLess(self.report['modified_world_triangles'],500)

    def test_frames_use_exact_visible_solid_section(self):
        sections,slots,skins=load(ROOT/'tools/legion/exported_files/models/wraith_tt_portal_large',0)
        frame=np.array([t for sec,s in zip(sections,slots) if skins[0][s]=='trim_metal_01' for t in sec],dtype='<f4')[:,:,:3]
        props={p['index']:p for p in json.loads((P/'static-props.json').read_text())}
        v=np.frombuffer(self.output[3],dtype='<f4').reshape(-1,3);h=list(struct.iter_unpack('<6h4i4f',self.output[0x45]))
        for r in self.report['portal_frame_replacements']:
            p=props[r['index']];a=r['replacement'];expected=(frame@np.array(rotation(p['angles'])).T*p['scale']+p['origin']).astype('<f4')
            start=h[a['first_header']][6];actual=v[start:start+a['triangles']*3].reshape(-1,3,3)
            self.assertTrue(np.array_equal(expected,actual));self.assertEqual(a['brushes'],0)

    def test_complete_tunnel_physics_records_retained(self):
        owners=json.loads(TARGET.with_name('collision-ownership.json').read_text())['owners'];h=list(struct.iter_unpack('<6h4i4f',self.source[0x45]))
        for o in owners:
            if 'phase_runner_tunnel' not in o['model']:continue
            self.assertEqual(o['method'],'BVH');self.assertGreater(o['triangles'],49000)
            self.assertFalse(set(range(o['first_header'],o['first_header']+o['headers']))&set(self.report['disabled_world_headers']))
            for i in range(o['first_header'],o['first_header']+o['headers']):self.assertEqual(self.source[0x45][i*44:(i+1)*44],self.output[0x45][i*44:(i+1)*44])

    def test_native_structure_and_draw_budget(self):
        validate_bsp(TARGET,require_native_index_padding=True)
        b=audit(TARGET);self.assertTrue(b['all_meshes_fit_simultaneously']);self.assertLessEqual(b['native_padded_indices'],int(WORLD_INDEX_CAPACITY*.85))

if __name__=='__main__':unittest.main()
