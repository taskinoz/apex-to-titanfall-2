"""Validate source screen recovery and narrowly scoped menu/lighting changes."""
import json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'));sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from repair_preview_index_padding import read_lumps
from repair_environment_lighting import entities
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
OUT=ROOT/'output/composite';WORK=OUT/'screen-repair';MAP=OUT/'mp_arena_composite.bsp'
OLD=ROOT/'output/repair-backups/20261007-before-screen-repair/mp_arena_composite.bsp'
# The retained 0.5 binary protects that release's byte-exact repair contract.
# Later deliberate gutter/index changes are tested in test_composite_local.
SCREEN_MAP=ROOT/'output/repair-backups/20261007-before-local-repair/mp_arena_composite.bsp'
if not (OUT/'local-repair/result.json').exists():SCREEN_MAP=MAP

class ScreenRepairTests(unittest.TestCase):
    def test_every_banner_and_local_screen_has_its_source_transform(self):
        source=json.loads((OUT/'source-inventory.json').read_text())['props'];scene=json.loads((OUT/'scene.json').read_text())
        wanted={p['index'] for p in source if Path(p['model']).stem in ('flexscreen_frame_olympus','thunderdome_screen_tower_arm_01','composite_big_screen_01','composite_screen_animation_01') and abs(p['origin'][0])<5000 and -500<p['origin'][1]<8000}
        plan=json.loads((WORK/'result.json').read_text());self.assertEqual(len(wanted),43);self.assertEqual(wanted,{p['index'] for p in plan['placements']})
        present={p['index']:p for p in scene['placements']};original={p['index']:p for p in source}
        for index in wanted:
            for key in ('origin','angles','scale','skin','model'):self.assertEqual(present[index][key],original[index][key])
            self.assertGreater(present[index]['triangles'],0)

    def test_old_draw_and_collision_buffers_remain_unchanged(self):
        ids=(3,0x1e,0x42,0x44,0x45,0x49,0x4f,0x7c,0x7e,0x7f,0x67,0x68)
        old=read_lumps(OLD,ids);new=read_lumps(SCREEN_MAP,ids)
        for i in ids:self.assertEqual(old[i],new[i][:len(old[i])],i)

    def test_only_the_native_menu_entities_move_and_relative_offsets_survive(self):
        old=entities(OLD);new=entities(MAP);self.assertEqual(len(old),len(new));delta=np.array([-13224,12144,11264])
        changed=0
        for a,b in zip(old,new):
            if a.get('script_name') in ('menu_scene_ref','menu_camera_target') or a.get('lightEnvironmentIndex')=='*1':
                changed+=1;self.assertTrue(np.allclose(np.array(list(map(float,b['origin'].split())))-np.array(list(map(float,a['origin'].split()))),delta));aa=dict(a);bb=dict(b);aa.pop('origin');bb.pop('origin');self.assertEqual(aa,bb)
            else:self.assertEqual(a,b)
        self.assertEqual(changed,4)
        p=np.array([-25000,24000,24000]);self.assertGreater(np.linalg.norm(p)-3072,22000)

    def test_old_ambient_tiles_and_unaffected_rtl_tiles_survive(self):
        old=read_lumps(OLD,(0x62,0x69));new=read_lumps(SCREEN_MAP,(0x62,0x69));count=json.loads((OLD.parent/'scene.json').read_text())['triangles'];tileids=np.arange(4*512*512).reshape(4,512,512);used=tileids<count
        aa=np.frombuffer(old[0x62],'u1').reshape(4,2,2048,2048,4);bb=np.frombuffer(new[0x62],'u1').reshape(4,2,2048,2048,4)
        scope=np.load(WORK/'lighting-scope.npz');jobs=scope['jobs'];uv=scope['uv'];affected=scope['affected'];glow=scope['emissive']>0;scope.close();allowed=np.zeros((4,512,512),bool);ambient_scope=np.zeros_like(allowed)
        for p in range(4):
            ix=np.flatnonzero(affected&(jobs['page']==p));x=(uv[ix,0,0]//4).astype(int);y=(uv[ix,0,1]//4).astype(int);allowed[p,y,x]=True
            ix=np.flatnonzero(glow&(jobs['page']==p));x=(uv[ix,0,0]//4).astype(int);y=(uv[ix,0,1]//4).astype(int);ambient_scope[p,y,x]=True
            mask=np.repeat(np.repeat(used[p]&~ambient_scope[p],4,0),4,1)
            self.assertTrue(np.array_equal(aa[p,0,mask],bb[p,0,mask]))
            used_mask=np.repeat(np.repeat(used[p],4,0),4,1)
            self.assertTrue(np.array_equal(aa[p,1,used_mask],bb[p,1,used_mask]))
            safe=np.repeat(np.repeat(used[p]&~allowed[p],4,0),4,1);stride=2048**2*8+1024**2*4
            for channel in range(2):
                at=p*stride+channel*2048**2*4;a=np.frombuffer(old[0x69],'u1',2048**2*4,at).reshape(2048,2048,4);b=np.frombuffer(new[0x69],'u1',2048**2*4,at).reshape(2048,2048,4);self.assertTrue(np.array_equal(a[safe],b[safe]))

    def test_lighting_slots_and_translucent_screen_coverage(self):
        r=json.loads((WORK/'lighting.json').read_text());self.assertEqual({e['source_entity'] for e in r['source_lights']},{51,309});self.assertTrue(all(v>0 for v in r['new_light_luxel_references'].values()))
        old=read_lumps(OLD,(0x36,0x65));new=read_lumps(MAP,(0x36,0x65));self.assertEqual(len(old[0x36]),len(new[0x36]))
        for index in range(64):
            if index not in (1,3,5,6):self.assertEqual(old[0x36][index*112:(index+1)*112],new[0x36][index*112:(index+1)*112])
        scope=np.load(WORK/'lighting-scope.npz');near=scope['probes'];scope.close();a=np.frombuffer(old[0x65],'V48');b=np.frombuffer(new[0x65],'V48');self.assertTrue(np.array_equal(a[~near],b[~near]))
        m=json.loads((OUT/'materials/mapping.json').read_text())['materials']['composite_big_screen_animation_01'];self.assertTrue(m['transparent']);self.assertEqual(m['opacity'],.2);self.assertIn('13',m['textures'])
        s=json.loads((WORK/'screen-pass.json').read_text());self.assertEqual(s['translucent_source_triangles'],12);self.assertEqual(s['disabled_shadow_triangles'],12)

    def test_streaming_catalog_covers_every_bound_material(self):
        from bsp_tool.extensions.stbsp import StreamBsp
        from extract_native_material import NativePak
        l=read_lumps(MAP,(2,0x2b,0x2c));names=set()
        for at in range(0,len(l[2]),36):
            string=struct.unpack_from('<I',l[2],at+12)[0];offset=struct.unpack_from('<I',l[0x2c],string*4)[0];names.add(l[0x2b][offset:l[0x2b].index(0,offset)].decode().replace('\\','/'))
        pak=NativePak(OUT/'materials/build/composite_world.rpak');guids={}
        for asset in pak.assets:
            if asset['type']=='matl':guids[pak.material(asset)[0]['name']]=asset['guid']
        stbsp=StreamBsp.from_file(str(MAP.with_suffix('.stbsp')));self.assertEqual({m.guid for m in stbsp.material_infos},{guids[n] for n in names})

if __name__=='__main__':unittest.main()
