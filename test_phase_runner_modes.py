"""Regression checks for a gameplay-only BSP entity edit."""
import collections,json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.branches.shared import Entities

class Gameplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'northstar/PhaseRunner'
        if json.loads((base/'mod.json').read_text())['Version']!='1.0.0':
            base=ROOT/'output/installed-backups/PhaseRunner-1.0.0-before-gameplay'
        cls.base=base/'mod/maps/mp_phase_runner.bsp'
        cls.stage=ROOT/'northstar/PhaseRunner.GameModes'
        cls.new=cls.stage/'mod/maps/mp_phase_runner.bsp'
        with cls.new.open('rb') as f:
            cls.header=f.read(2064);o,n,_,_=struct.unpack_from('<4I',cls.header,16);f.seek(o)
            cls.entities=Entities.from_bytes(f.read(n))
    def test_entire_existing_body_and_non_entity_headers_unchanged(self):
        with self.base.open('rb') as a,self.new.open('rb') as b:
            old=a.read(2064);new=b.read(2064)
            self.assertEqual(old[:16],new[:16]);self.assertEqual(old[32:],new[32:])
            while chunk:=a.read(8*1024*1024):self.assertEqual(chunk,b.read(len(chunk)))
    def test_team_bases_and_spaced_starts(self):
        for team,sign in ((2,-1),(3,1)):
            starts=[e for e in self.entities if e.get('classname')=='info_spawnpoint_human_start' and e['teamnumber']==str(team)]
            self.assertEqual(len(starts),12)
            points=[list(map(float,e['origin'].split())) for e in starts]
            for p in points:self.assertGreater(sign*p[0],5400)
            for i,p in enumerate(points):
                for q in points[i+1:]:self.assertGreaterEqual((p[0]-q[0])**2+(p[1]-q[1])**2,96**2)
        names=[e.get('targetname') for e in self.entities if e.get('targetname','').startswith('phase_runner_')]
        self.assertEqual(len(names),len(set(names)))
    def test_objective_links_and_convex_native_trigger_volumes(self):
        flags=[e for e in self.entities if e.get('classname')=='info_spawnpoint_flag']
        self.assertEqual(sorted(e['teamnumber'] for e in flags),['2','3'])
        hp=[e for e in self.entities if e.get('classname')=='info_hardpoint']
        self.assertEqual(sorted(e['hardpointGroup'] for e in hp),['A','B','C'])
        for h in hp:
            trigger=next(e for e in self.entities if e.get('targetname')==h['triggerTarget'])
            self.assertEqual(trigger['classname'],'trigger_capture_point')
            self.assertEqual(sum(k.startswith('*trigger_brush_0_plane_') for k in trigger),6)
            self.assertEqual(trigger['triggerFilterTeamIMC'],trigger['triggerFilterTeamMilitia'])
    def test_objective_devices_do_not_overlap_pilot_spawn_hulls(self):
        devices=[list(map(float,e['origin'].split())) for e in self.entities if e.get('classname') in ('info_hardpoint','info_spawnpoint_flag')]
        for e in self.entities:
            if e.get('classname') not in ('info_spawnpoint_human','info_spawnpoint_human_start'):continue
            p=list(map(float,e['origin'].split()))
            for q in devices:self.assertGreater((p[0]-q[0])**2+(p[1]-q[1])**2,64**2)
    def test_harness_rejects_invalid_mode_and_team_or_probe_injection(self):
        sys.path.insert(0,str(ROOT/'test-harness'))
        from harness import validate_job,MODES
        for mode in MODES:self.assertEqual(validate_job('ui',dict(op='load',map='mp_phase_runner',mode=mode))['mode'],mode)
        for bad in (True,0,1,4,'2'):
            with self.assertRaises(ValueError):validate_job('server',dict(op='respawn',team=bad))
        for bad in ([],[[float('nan'),0,0]],[[0,0]],[[0,0,0]]*401):
            with self.assertRaises(ValueError):validate_job('server',dict(op='spawn_probe',points=bad))
        with self.assertRaises(ValueError):validate_job('ui',dict(op='load',map='mp_phase_runner',mode='ctf;quit'))
if __name__=='__main__':unittest.main()
