"""Withdraw 0.1.35 using the exact, hash-verified confirmed-lighting package."""
import json,shutil
from pathlib import Path
from finalize_lighting_release import ROOT,digest

def restore():
    source=ROOT/'northstar/PhaseRunner.InteriorRelease'
    if json.loads((source/'mod.json').read_text())['Version']!='0.1.34':raise ValueError('Wrong lighting baseline')
    checks=json.loads((source/'checksums.json').read_text())
    for relative,sha in checks.items():
        if digest(source/relative)!=sha:raise ValueError('Baseline hash mismatch '+relative)
    for destination in (ROOT/'northstar/PhaseRunner.Preview',Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in source.rglob('*'):
            if p.is_file():
                target=destination/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for relative,sha in checks.items():
            if digest(destination/relative)!=sha:raise ValueError('Restored hash mismatch '+relative)
    report=dict(restored_version='0.1.34',withdrawn_version='0.1.35',files_verified=len(checks),
        user_feedback='Portals cull out the skybox and cause hall of mirrors; remove portals.',
        lighting_collision_and_walkways_preserved=True,client_rendering_failed_in_0_1_35=True)
    (ROOT/'logs/portal-0.1.35-withdrawal.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':restore()
