"""Regression coverage for signed source volumes and native safety entities."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from decode_source_trigger_volumes import pieces,native
from repair_environment_lighting import entities

class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'output/composite/source-gameplay-volumes.json').read_text())

    def test_signed_source_fall_volume(self):
        e=next(e for e in self.source['dropoff'] if e['classname']=='trigger_hurt')
        p=np.concatenate([s['points'] for s in pieces(e)])
        # Unsigned decoding shifts the lower half by an entire quantization
        # range and incorrectly puts the kill plane above the playable map.
        self.assertLess(p[:,2].min(),-3300)
        self.assertGreater(p[:,2].max(),3300)
        top=p[:,2].max()+float(e['origin'].split()[2])
        self.assertAlmostEqual(top,-657.05,delta=.1)

    def test_native_planes_contain_each_clipped_piece(self):
        for key,shift in [('phase',(26000,19000,0)),('dropoff',(0,0,0))]:
            for e in self.source[key]:
                if not e['classname'].startswith('trigger_'):continue
                n=native(e,shift)
                if n is None:continue
                o=np.array(list(map(float,n['origin'].split())))
                lo=np.array(list(map(float,n['*trigger_bounds_mins'].split())))+o
                hi=np.array(list(map(float,n['*trigger_bounds_maxs'].split())))+o
                self.assertTrue(np.all(lo>=-16000.05))
                self.assertTrue(np.all(hi<=16000.05))
                self.assertTrue(np.all(hi>lo))
                self.assertFalse(any(k.startswith('*coll') for k in n))
                self.assertNotIn('model',n)

    def test_phase_has_original_mode_entities_and_source_boundaries(self):
        rows=entities(ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp')
        counts={kind:sum(e['classname']==kind for e in rows) for kind in
                ('trigger_out_of_bounds','trigger_hurt','info_spawnpoint_human_start','info_hardpoint','info_spawnpoint_flag')}
        self.assertEqual(counts,dict(trigger_out_of_bounds=82,trigger_hurt=1,
                                    info_spawnpoint_human_start=24,info_hardpoint=3,info_spawnpoint_flag=2))

    def test_boundary_application_preserves_original_behaviour(self):
        from apply_arena_boundaries import rope
        rows=rope([0,0,0],[0,0,500],'test_zip')
        self.assertEqual(rows[0]['NextKey'],rows[1]['targetname'])
        self.assertEqual(rows[0]['Zipline'],rows[1]['Zipline'])
        self.assertEqual(rows[0]['Slack'],'0')

    def test_dropoff_keeps_original_converted_source_volumes(self):
        rows=entities(ROOT/'output/composite/mp_arena_composite.bsp')
        expected=json.loads((ROOT/'output/composite/native-gameplay-volumes.json').read_text())['dropoff']
        actual=[e for e in rows if e.get('targetname','').startswith('dropoff_source_boundary_')]
        self.assertEqual(actual,expected)

if __name__=='__main__':unittest.main()
