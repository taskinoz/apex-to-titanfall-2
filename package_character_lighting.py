"""Stage only the character-lighting BSP over the complete 0.1.37 package."""
import json,os,shutil
from build_character_lighting import ROOT,SOURCE,TARGET,OUT
BASE=ROOT/'northstar/PhaseRunner.Preview'
PACKAGE=ROOT/'northstar/PhaseRunner.CharacterLightingRelease'
def build():
    if json.loads((BASE/'mod.json').read_text())['Version']!='0.1.37':raise ValueError('Unexpected baseline')
    for source in BASE.rglob('*'):
        if not source.is_file():continue
        rel=source.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else source
        if dest.exists():
            if os.path.samefile(actual,dest):continue
            dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    mod=json.loads((PACKAGE/'mod.json').read_text());mod['Version']='0.1.38'
    mod['Description']='Phase Runner with native player/weapon lighting probes, lit tunnel catwalks and loading artwork.'
    (PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());report=json.loads((OUT/'character-lighting.json').read_text())
    status['character_light_repair']=report;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(OUT/'character-lighting.json',PACKAGE/'character-lighting.json')
    print(json.dumps(dict(version=mod['Version'],map_name=TARGET.stem,gameplay_probes=report['gameplay_probes']),indent=2),flush=True)
if __name__=='__main__':build()
