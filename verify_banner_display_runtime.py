"""Verify focused native captures and same-process map reload evidence."""
import argparse,importlib.util,json
from pathlib import Path
from PIL import Image
from package_player_mods import ROOT,digest
from verify_area_survey import near

def record(first=False):
    spec=importlib.util.spec_from_file_location('northstar_harness',ROOT/'test-harness/harness.py');ns=importlib.util.module_from_spec(spec);spec.loader.exec_module(ns);controller=ns.Controller();state=controller.request('/status')
    path=ROOT/'output/banner-display-repair/reloads.json';data={'maps':[]} if first else json.loads(path.read_text());wanted=['mp_arena_composite','mp_phase_runner','mp_arena_composite'][len(data['maps'])]
    state=controller.wait_map(wanted,10);data['maps'].append(dict(map=wanted,game_pid=state['game_pid'],contexts=state['contexts']))
    if len(data['maps'])==3:
        data['logs']=controller.export_logs();data['tested_payloads']={}
        for name,folder in [('ArenaComposite','PhaseRunner.Preview'),('PhaseRunner','MapTest.Extra')]:
            package=ROOT/'northstar'/name;staged=Path(state['profile'])/'mods'/folder
            for sub in ('mod','paks'):
                for file in (package/sub).rglob('*'):
                    if file.is_file():
                        relative=file.relative_to(package);wanted=digest(file);assert digest(staged/relative)==wanted,'Staged test payload differs'
                        data['tested_payloads'][name+'/'+relative.as_posix()]=wanted
    path.write_text(json.dumps(data,indent=2));print('Recorded ready state:',wanted if isinstance(wanted,str) and wanted.startswith('mp_') else data['maps'][-1]['map'])

def captures():
    result={}
    for name in ('drop-off','phase-runner'):
        folder=ROOT/'r5-harness/output'/f'{name}-banner-displays'
        data=json.loads((folder/'comparison.json').read_text());job=data['route'];rows=[]
        assert len(data['pairs'])==len(job['shots'])
        for pair,shot in zip(data['pairs'],job['shots'],strict=True):
            assert pair['name']==shot['name'] and pair['route_camera']==shot
            for engine in ('r5r','northstar'):
                r=pair[engine];image=folder/r['gallery_path'];assert digest(image)==r['sha256']
                with Image.open(image) as im:assert im.size==(1280,720)==(r['width'],r['height'])
                if engine=='r5r':
                    assert r['map']==job['source_map']
                    for c in ('server','client'):assert r['state'][c]['map']==job['source_map'] and r['state'][c]['ready']
                    near(r['state']['client']['origin'],[a+b for a,b in zip(shot['origin'],job['source_offset'])]);near(r['state']['client']['angles'],shot['angles'],True)
                    assert r['camera']['fov']==shot.get('fov',90)
                else:
                    for c in ('ui','client','server'):assert r['state']['contexts'][c]['level']==job['target_map'] and r['state']['contexts'][c]['ready']
                    near(r['state']['contexts']['client']['origin'],shot['origin']);near(r['state']['contexts']['client']['angles'],shot['angles'],True)
                    near(r['state']['contexts']['server']['playerOrigin'],[shot['origin'][0],shot['origin'][1],shot['origin'][2]-64])
            rows.append(dict(view=pair['name'],source_sha256=pair['r5r']['sha256'],port_sha256=pair['northstar']['sha256']))
        result[name]=dict(pairs=len(rows),captures=rows)
    return result

def verify():
    records=captures();work=ROOT/'output/banner-display-repair'
    runtime=json.loads((work/'reloads.json').read_text())
    assert len(runtime['maps'])==3 and [m['map'] for m in runtime['maps']]==['mp_arena_composite','mp_phase_runner','mp_arena_composite']
    assert len({m['game_pid'] for m in runtime['maps']})==1
    assert not runtime['logs']['script_errors']
    assert runtime['tested_payloads']
    for relative,wanted in runtime['tested_payloads'].items():assert digest(ROOT/'northstar'/relative)==wanted,'Tested runtime changed after capture'
    for m in runtime['maps']:
        for context in ('ui','client','server'):assert m['contexts'][context]['level']==m['map'] and m['contexts'][context]['ready']
    result=dict(maps=records,native_pairs=sum(m['pairs'] for m in records.values()),same_process_reloads=True,no_script_errors=True)
    (work/'native-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',action='store_true');p.add_argument('--first',action='store_true');a=p.parse_args()
    if a.record:record(a.first)
    else:verify()
