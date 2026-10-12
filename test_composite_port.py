"""Regressions for the independently packaged Composite port."""
import json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'));sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from audit_world_draw_budget import enforce_camera_bypass_budget
from repair_environment_lighting import entities
from preview_visibility import validate_visibility
OUT=ROOT/'output/composite';MAP=OUT/'mp_arena_composite.bsp'

class CompositeTests(unittest.TestCase):
    def test_obj_relative_references_recover_distinct_world_surfaces(self):
        w=np.load(OUT/'world.npz')['triangles']
        self.assertGreater(len(w),300000)
        self.assertTrue(np.all(np.ptp(w[:,:,:3],axis=(0,1))>5000))
        self.assertGreater(len(np.unique(w[:,0,:3],axis=0)),100000)
        self.assertTrue(np.all(np.linalg.norm(np.cross(w[:,1,:3]-w[:,0,:3],w[:,2,:3]-w[:,0,:3]),axis=1)>1e-5))

    def test_native_mesh_ranges_and_all_visible_capacity(self):
        l=read_lumps(MAP,(0x4f,0x50,0x51,0x52,0x77,0x78,0x79))
        validate_index_padding(l[0x50],l[0x4f],l[0x52]);validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51])
        a=enforce_camera_bypass_budget(MAP)
        expected=json.loads((OUT/'scene.json').read_text())['triangles']
        self.assertEqual(a['real_triangles'],expected);self.assertLess(a['native_padded_indices'],3145728*.9)

    def test_game_lump_payload_is_relocated_inside_its_directory(self):
        with MAP.open('rb') as f:
            head=f.read(2064);at,n,_,_=struct.unpack_from('<4I',head,16+0x23*16);f.seek(at);raw=f.read(n)
        count=struct.unpack_from('<I',raw)[0]
        for j in range(count):
            ptr,size=struct.unpack_from('<2I',raw,12+j*16)
            if size:self.assertGreaterEqual(ptr,at+4+16*count);self.assertLessEqual(ptr+size,at+n)

    def test_native_collision_indices_and_source_aligned_bounds(self):
        l=read_lumps(MAP,(3,0x42,0x44,0x45,0x5c))
        p=np.frombuffer(l[3],'<f4').reshape(-1,3);w=np.frombuffer(l[0x42],'<u4')
        total=0
        for h in struct.iter_unpack('<6h4i4f',l[0x45]):
            self.assertLessEqual(h[4],300);a=w[h[7]:h[7]+h[4]];ix=a&1023;ids=h[6]+np.stack((ix,ix+(a>>10&127),ix+(a>>17&127)),axis=1)
            self.assertLess(int(ids.max()),len(p));t=p[ids];self.assertTrue(np.isfinite(t).all());total+=len(t)
        report=json.loads((OUT/'physics.json').read_text())
        self.assertEqual(total,report['triangles']);self.assertEqual(len(l[0x5c])//32,report['brushes'])
        removed=report['removed_obsolete_clip_triangles']
        self.assertEqual(removed,{})
        self.assertEqual(report['restored_source_clip_triangles'],dict(diagonal_room_boundary=24,north_room_boundary=12,upper_platform_exclusion=34))
        self.assertNotIn(4924,{p['index'] for p in report['owners']})

    def test_all_source_stairs_have_visuals(self):
        audit=json.loads((OUT/'asset-audit.json').read_text())
        scene=json.loads((OUT/'scene.json').read_text())
        expected={p['index'] for p in audit['props'] if 'stair' in p['model'].lower()}
        self.assertEqual(len(expected),124)
        self.assertLessEqual(expected,{p['index'] for p in scene['placements']})
        self.assertEqual(scene['removed_door_placeholder_triangles'],12)

    def test_solid_cargo_uses_opaque_material(self):
        mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
        found=[v for v in mapping.values() if v['name'].endswith('/underbelly_cargo_containers_hammond')]
        self.assertTrue(found)
        self.assertTrue(all(not v['transparent'] for v in found))

    def test_floor_overlay_resolves_exported_variant_and_alpha(self):
        mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
        dirt=mapping['world/dirt/dirt_desert_05_desaturated_btt_wld']
        self.assertTrue(dirt['recovered'])
        self.assertTrue(dirt['transparent'])
        self.assertIn('13',dirt['textures'])
        self.assertTrue(mapping['world/metal/trim_metal_01_wet_01_bm']['recovered'])

    def test_native_safety_volumes_and_zipline_links(self):
        rows=entities(MAP)
        for kind,count in [('trigger_out_of_bounds',21),('trigger_hurt',5),('move_rope',2),('keyframe_rope',2)]:
            self.assertEqual(sum(e['classname']==kind for e in rows),count)
        names={e.get('targetname'):e for e in rows}
        for e in rows:
            if e['classname']=='move_rope':
                self.assertEqual(e['Zipline'],'1')
                self.assertEqual(names[e['NextKey']]['classname'],'keyframe_rope')
                self.assertTrue(e['targetname'].startswith('dropoff_zipline_source_'))
            if e['classname'].startswith('trigger_'):
                self.assertTrue(any(k.startswith('*trigger_brush_0_plane_') for k in e))

    def test_only_hull_verified_team_starts_are_packaged(self):
        rows=entities(MAP);starts=[e for e in rows if e.get('classname')=='info_spawnpoint_human_start'];self.assertEqual(len(starts),24)
        safe={tuple(p['origin']) for p in json.loads((OUT/'team-spawn-probes.json').read_text())['data'] if p['pilot'] and p['floor']}
        self.assertEqual({tuple(map(float,e['origin'].split())) for e in starts},safe)
        self.assertEqual({e['teamnumber'] for e in starts},{'2','3'})
        titans=[e for e in rows if e.get('classname')=='info_spawnpoint_titan_start']
        self.assertEqual(len(titans),6)
        self.assertEqual({e['teamnumber'] for e in titans},{'2','3'})

    def test_zipline_endpoints_match_apex_entities_without_added_routes(self):
        source=json.loads((OUT/'source-inventory.json').read_text())['entities']['mp_rr_arena_composite_script.ent']
        ends={e.get('link_guid'):e for e in source if e['classname']=='zipline_end'}
        expected={(tuple(map(float,e['origin'].split())),tuple(map(float,ends[e['link_to_guid_0']]['origin'].split()))) for e in source if e['classname']=='zipline'}
        rows=entities(MAP);names={e.get('targetname'):e for e in rows}
        actual={(tuple(map(float,e['origin'].split())),tuple(map(float,names[e['NextKey']]['origin'].split()))) for e in rows if e['classname']=='move_rope'}
        self.assertEqual(actual,expected)

    def test_spawn_covers_and_recorded_orphan_are_the_only_disabled_old_triangles(self):
        old=ROOT/'output/repair-backups/20261007-source-layout/mp_arena_composite.bsp'
        ids=(3,0x49,0x4f,0x7e,0x62,0x69)
        before=read_lumps(old,ids);after=read_lumps(MAP,ids)
        self.assertEqual(after[3][:len(before[3])],before[3])
        from build_composite_map import DT
        va=np.frombuffer(before[0x49],DT);vb=np.frombuffer(after[0x49],DT)[:len(va)].copy()
        scope=OUT/'local-repair/wall-scope.npz'
        if scope.exists():
            s=np.load(scope);vi=s['vertices'].ravel();s.close();vi=vi[vi<len(va)];vb['light'][vi,:2]=va['light'][vi,:2]
        self.assertEqual(va.tobytes(),vb.tobytes())
        # The separately audited orphan lamp adds exactly 24 disabled slots;
        # no other original triangle may be suppressed.
        for i in (0x4f,0x7e):
            # Page partitioning reorders current draw indices; compare the
            # original cover suppression against the retained 0.5 snapshot.
            sample=after[i]
            extra=24 if (OUT/'local-repair/orphan.json').exists() else 0
            if i==0x4f and (OUT/'local-repair/wall-pages.json').exists():
                sample=read_lumps(ROOT/'output/repair-backups/20261007-before-local-repair/mp_arena_composite.bsp',(i,))[i];extra=0
            a=np.frombuffer(before[i],'<u2').reshape(-1,3);b=np.frombuffer(sample[:len(before[i])],'<u2').reshape(-1,3)
            changed=np.any(a!=b,axis=1);self.assertEqual(int(changed.sum()),108+extra)
            self.assertTrue(np.all(b[changed][:,0]==b[changed][:,1]));self.assertTrue(np.all(b[changed][:,1]==b[changed][:,2]))

    def test_material_dependencies_are_available_without_phase_runner(self):
        from extract_native_material import NativePak
        pak=NativePak(OUT/'materials/build/composite_world.rpak')
        known={a['guid'] for a in pak.assets}
        for name in ('common.raw.rpak','coliseum.raw.rpak'):
            known.update(a['guid'] for a in NativePak(ROOT/'inputs/tf2-rpak-work'/name).assets)
        for asset in pak.assets:
            if asset['type']!='matl':continue
            spec,_=pak.material(asset)
            deps=[spec['shaderSet'],*spec['$textures'].values(),
                  *[spec[k] for k in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]]
            self.assertTrue(all(not int(g,16) or int(g,16) in known for g in deps),spec['name'])

    def test_alpha_materials_do_not_inherit_foreign_glass_channels(self):
        from extract_native_material import NativePak
        mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
        allowed={}
        for record in mapping.values():
            if record.get('transparent'):
                allowed.setdefault(record['name'],set()).update(record['textures'])
        pak=NativePak(OUT/'materials/build/composite_world.rpak')
        found=set()
        for asset in pak.assets:
            if asset['type']!='matl':continue
            spec,_=pak.material(asset)
            if spec['name'] in allowed:
                self.assertLessEqual(set(spec['$textures']),allowed[spec['name']])
                self.assertIn('13',spec['$textures']);found.add(spec['name'])
        self.assertEqual(found,set(allowed))

    def test_native_lightmaps_probes_and_shader_table_ranges(self):
        l=read_lumps(MAP,(4,0x36,0x53,0x62,0x65,0x67,0x68,0x69,0x7a));pages=len(l[0x53])//8;self.assertEqual(pages,4)
        self.assertEqual(len(l[0x62]),pages*2048*2048*8);self.assertEqual(len(l[0x69]),pages*(2048*2048*8+1024*1024*4))
        self.assertEqual(len(l[0x36])//112,64);self.assertEqual(len(l[0x65])//48,2907);self.assertEqual(len(l[0x68])//20,2907)
        self.assertEqual(struct.unpack('<63h',l[0x7a])[:62],tuple(range(62)))
        self.assertTrue(len(l[4]) and len(l[0x67]))

if __name__=='__main__':unittest.main()
