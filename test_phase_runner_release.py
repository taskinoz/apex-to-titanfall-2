"""Grounded release checks: visual/physics alignment and preserved established map data."""
import json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from build_phase_runner_catwalks import mesh_faces,face_key
from build_center_detail import active
from audit_tree_grounding import audit
from stage_prop_geometry import rotation
from build_phase_runner_firs import tree_physics
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from preview_visibility import validate_visibility
from finalize_lighting_release import digest

PACKAGE=ROOT/'northstar/PhaseRunner'
OUT=ROOT/'output/phase-runner/release-1.0.0'
BASE=ROOT/'northstar/PhaseRunner.ArtSupportsLoadingRelease'

class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(1,2,3,0x1e,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x57,0x59,0x5c,0x42,0x45,0x77,0x78,0x79,0x7b)
        cls.old=read_lumps(BASE/'mod/maps/mp_phase_runner.bsp',ids)
        cls.new=read_lumps(OUT/'mp_phase_runner.bsp',ids)
        cls.report=json.loads((OUT/'trees.json').read_text())

    def test_only_intended_vertical_placement_changes(self):
        before=json.loads((ROOT/'northstar/PhaseRunner.FirsRelease/trees.json').read_text())
        old={p['index']:p for p in before['source_placements']}
        source=np.load(ROOT/'output/phase-runner/firs/source-geometry.npz')['data']
        actual=np.load(OUT/'source-geometry.npz')['data']
        self.assertEqual(len(self.report['source_placements']),20)
        self.assertEqual(self.report['trees_moved'],9)
        for p in self.report['source_placements']:
            q=old[p['index']]
            for key in ('angles','scale','skin','model'):self.assertEqual(p[key],q[key])
            self.assertEqual(p['origin'][:2],q['origin'][:2])
            self.assertLessEqual(p['grounding_delta_z'],0)
            begin=p['first_triangle'];end=begin+p['triangles']
            self.assertTrue(np.array_equal(actual[begin:end,:,[0,1,3,4,5,6,7]],source[begin:end,:,[0,1,3,4,5,6,7]]))
            self.assertTrue(np.allclose(actual[begin:end,:,2],source[begin:end,:,2]+p['grounding_delta_z'],atol=.0002,rtol=0))

    def test_all_roots_are_embedded_in_existing_rendered_support(self):
        r=audit(OUT/'mp_phase_runner.bsp',self.report)
        self.assertEqual(r['floating_trees'],0)
        for p in r['placements']:self.assertLessEqual(p['rendered_root_z'],p['surface_min_z']-7.99)

    def test_exact_tree_geometry_and_existing_meshes_preserved(self):
        for before,after in enumerate(self.report['retained_meshes']):
            self.assertEqual(self.old[0x50][before*28:(before+1)*28],self.new[0x50][after*28:(after+1)*28])
            self.assertEqual(self.old[0x51][before*32:(before+1)*32],self.new[0x51][after*32:(after+1)*32])
        wanted={face_key(t[:,:3]) for t in np.load(OUT/'source-geometry.npz')['data']}
        got={face_key(t) for i,r,raw,vi,tri in mesh_faces(self.new) if i in set(self.report['new_meshes']) for t in tri}
        self.assertEqual(got,wanted)

    def test_translated_source_trunk_collision_and_grid(self):
        local,_=tree_physics();pos=np.frombuffer(self.new[3],'<f4').reshape(-1,3)
        heads=list(struct.iter_unpack('<6h4i4f',self.new[0x45]));owners={p['index']:p for p in self.report['collision']['owners']};added=set()
        for p in self.report['source_placements']:
            expected=(local@np.asarray(rotation(p['angles'])).T*p['scale']+p['origin']).astype('<f4')
            actual=[];owner=owners[p['index']]
            for hi in range(owner['first_header'],owner['first_header']+owner['headers']):
                added.add((0x40,hi));h=heads[hi];actual.extend(pos[h[6]:h[6]+h[3]].reshape(-1,3,3))
            self.assertEqual({face_key(t) for t in expected},{face_key(t) for t in actual})
        self.assertEqual(active(self.new),active(self.old)|added)
        self.assertEqual(self.old[0x5c],self.new[0x5c])

    def test_existing_lighting_prefix_and_asset_packages_preserved(self):
        for index in (0x53,0x62,0x69):self.assertEqual(self.new[index][:len(self.old[index])],self.old[index])
        for p in (BASE/'paks').glob('*.rpak'):self.assertEqual(digest(p),digest(PACKAGE/'paks'/p.name))
        self.assertEqual(digest(ROOT/'northstar/PhaseRunner.FirsRelease/paks/phase_runner_firs.rpak'),digest(PACKAGE/'paks/phase_runner_firs.rpak'))
        self.assertEqual(digest(ROOT/'northstar/PhaseRunner.FirsRelease/mod/maps/mp_phase_runner.stbsp'),digest(PACKAGE/'mod/maps/mp_phase_runner.stbsp'))

    def test_visibility_index_padding_and_draw_margin(self):
        validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        v=validate_visibility(self.new[0x77],self.new[0x78],self.new[0x79],self.new[0x51])
        self.assertEqual(v['reachable_meshes'],len(self.new[0x50])//28)
        b=enforce_camera_bypass_budget(OUT/'mp_phase_runner.bsp')
        self.assertEqual(b['real_triangles'],972628)
        self.assertLess(b['native_padded_indices'],WORLD_INDEX_CAPACITY*.95)
        self.assertLess(b['static_batch_runs'],512)

    def test_release_mod_and_local_test_is_opt_in(self):
        meta=json.loads((PACKAGE/'mod.json').read_text())
        self.assertEqual((meta['Name'],meta['Version']),('PhaseRunner','1.0.0'))
        self.assertEqual(meta['ConVars'][0]['DefaultValue'],'0')
        self.assertTrue((PACKAGE/'mod/maps/mp_phase_runner.bsp').is_file())
        self.assertTrue((PACKAGE/'mod/maps/mp_phase_runner.stbsp').is_file())

if __name__=='__main__':unittest.main()
