"""Refresh every published camera against current mods without rewriting history.

Existing hash-verified Apex references retain their original capture dates.
Native captures use one map per cold owned game, with safety triggers removed
only in the diagnostic runtime so exterior gallery cameras remain alive.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from package_player_mods import ROOT,RELEASES,digest

SNAPSHOT='2026-10-18-release-refresh'
OUT=ROOT/'output/site-refresh-2026-10-18'
CATALOGUE=ROOT/'site/dist/catalogue.json'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.new')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def module(name,relative):
    parent=str((ROOT/relative).parent)
    if parent not in sys.path:sys.path.insert(0,parent)
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def near(a,b,angles=False):
    if len(a)!=len(b) or any(abs((x-y+180)%360-180 if angles else x-y)>.05 for x,y in zip(a,b)):
        raise ValueError('Captured camera differs from route')


def plan():
    public=json.loads(CATALOGUE.read_text());config=json.loads((ROOT/'site/maps.json').read_text())
    by_id={m['id']:m for m in config['maps']};summary={}
    for m in public['maps']:
        ident=m['id'];root=OUT/ident;gallery=root/'comparison';gallery.mkdir(parents=True,exist_ok=True)
        seen={}
        for snapshot in reversed(m['snapshots']):
            for shot in snapshot['shots']:
                key=tuple(shot['origin']+shot['angles']+[shot['fov']]);seen.setdefault(key,shot)
        shots=list(seen.values())
        hero={'drop-off':'court-overview','phase-runner':'arena-overview'}.get(ident,'view-0')
        shots.sort(key=lambda s:s['name']!=hero)
        if len({s['name'] for s in shots})!=len(shots):raise ValueError('Ambiguous camera name')
        route=dict(title=m['name']+' current-release site survey',source_map=m['source_map'],
                   target_map=m['target_map'],source_offset=m['source_offset'],mode='ps',shots=[])
        refs={}
        for shot in shots:
            meta=shot['r5r'];path=ROOT/'site/dist'/meta['image']
            if digest(path)!=meta['sha256']:raise ValueError('Archived source reference changed')
            dest=gallery/(shot['name']+'-r5r.png');shutil.copy2(path,dest)
            refs[shot['name']]={k:meta[k] for k in ('width','height','captured','sha256')}
            refs[shot['name']]['gallery_path']=dest.name
            route['shots'].append({k:shot[k] for k in ('name','origin','angles','fov')})
        if ident=='party-crasher':
            from new_arena_ports import folder
            previous=json.loads((folder(ident)/'northstar-screen-v1/runtime-captures.json').read_text())
            cap=next(s for s in previous['captures'] if 'screen-framed-' in s['path'])
            client=cap['state']['contexts']['client']
            route['shots'].append(dict(name='northstar-screen',origin=client['origin'],angles=client['angles'],fov=90))
        write(root/'route.json',route);write(root/'source-references.json',refs)
        write(ROOT/'r5-harness/routes'/(ident+'-release-survey.json'),route)
        write(root/'package.json',dict(package=by_id[ident]['package'],version=json.loads((ROOT/'northstar'/by_id[ident]['package']/'mod.json').read_text())['Version']))
        summary[ident]=len(route['shots'])
    write(OUT/'plan.json',summary);print(json.dumps(summary),flush=True)


def source_screen():
    r5=module('release_r5_harness','r5-harness/harness.py')
    r5.launch('mp_rr_party_crasher')
    c=r5.Controller()
    try:
        route=json.loads((OUT/'party-crasher/route.json').read_text());shot=route['shots'][-1]
        c.camera(shot['origin'],shot['angles'],shot['fov'],2);cap=c.capture('release-northstar-screen')
        near(cap['state']['client']['origin'],shot['origin']);near(cap['state']['client']['angles'],shot['angles'],True)
        if cap['map']!=route['source_map']:raise ValueError('Wrong source map')
        gallery=OUT/'party-crasher/comparison';dest=gallery/'northstar-screen-r5r.png';shutil.copy2(cap['path'],dest)
        refs=json.loads((OUT/'party-crasher/source-references.json').read_text());refs['northstar-screen']={k:cap[k] for k in ('width','height','captured','sha256')}
        refs['northstar-screen']['gallery_path']=dest.name;write(OUT/'party-crasher/source-references.json',refs)
        write(OUT/'party-crasher/new-source-capture.json',dict(capture=cap,diagnostic_safety_disabled=False))
        print('New matched Apex screen reference captured',flush=True)
    finally:
        c.export_logs();r5.stop()


def capture(ident,names=None):
    root=OUT/ident;route=json.loads((root/'route.json').read_text());package=json.loads((root/'package.json').read_text())
    ns=module('release_native_harness','test-harness/harness.py')
    try:
        old=ns.Controller();state=old.request('/status')
    except (OSError,ValueError,RuntimeError):state=None
    if state:
        if state['game_running']:raise ValueError('An owned harness game is still running; do not interrupt unrelated testing')
        old.request('/shutdown',{})
    cmd=[sys.executable,str(ROOT/'test-harness/harness.py'),'start','--profile','R2AtlasHarness',
         '--package',str(ROOT/'northstar'/package['package']),'--extra-package',str(ROOT/'northstar/ApexMaps.UI'),
         '--map',route['target_map'],'--mode','ps','--timeout','240']
    log=root/'launch.log'
    with log.open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    c=ns.Controller();captures=[]
    try:
        state=c.request('/status');mounted=Path(state['profile'])/'mods/PhaseRunner.Preview';accepted=ROOT/'northstar'/package['package']
        expected={p.relative_to(accepted).as_posix():digest(p) for p in accepted.rglob('*') if p.is_file() and p.suffix in ('.bsp','.stbsp','.rpak')}
        for rel,sha in expected.items():
            if digest(mounted/rel)!=sha:raise ValueError('Mounted build differs: '+rel)
        c.command('ui','console',command='script SetServerVar("gameEndTime", Time()+600)')
        c.command('ui','console',command='script foreach(string cls in ["trigger_out_of_bounds","trigger_hurt"]) foreach(entity t in GetEntArrayByClass_Expensive(cls)) t.Destroy()')
        client=c.request('/status')['contexts'].get('client',{})
        if not client.get('alive'):
            c.command('ui','console',command='script foreach(entity p in GetPlayerArray()) if(!IsAlive(p)) p.RespawnPlayer(null)')
        # Closing menus does not clear the game-mode introduction banner.
        # Let that native presentation finish before photographing the first view.
        time.sleep(15)
        refs=json.loads((root/'source-references.json').read_text());gallery=root/'comparison';pairs=[]
        if names:
            if not set(names)<={s['name'] for s in route['shots']}:raise ValueError('Unknown requested camera')
            captures=json.loads((root/'native-captures.json').read_text())['captures']
            pairs=json.loads((gallery/'comparison.json').read_text())['pairs']
        for shot in route['shots']:
            if names and shot['name'] not in names:continue
            if shot['name'] not in refs:raise ValueError('Missing matching Apex reference')
            c.camera(shot['origin'],shot['angles'],shot.get('fov',90),2)
            cap=c.capture('site-'+shot['name']);contexts=cap['state']['contexts'];client=contexts['client']
            if client['level']!=route['target_map'] or not client.get('alive'):raise ValueError('Invalid native map/player state')
            near(client['origin'],shot['origin']);near(client['angles'],shot['angles'],True)
            source=refs[shot['name']]
            if (cap['width'],cap['height'])!=(source['width'],source['height']):raise ValueError('Comparison resolution mismatch')
            dest=gallery/(shot['name']+'-northstar.png');shutil.copy2(cap['path'],dest)
            if digest(dest)!=cap['sha256']:raise ValueError('Capture hash changed')
            meta={k:cap[k] for k in ('width','height','captured','sha256')};meta['gallery_path']=dest.name
            pairs=[p for p in pairs if p['name']!=shot['name']]+[dict(name=shot['name'],r5r=source,northstar=meta)]
            captures=[p for p in captures if p['shot']['name']!=shot['name']]+[dict(shot=shot,capture=cap)]
            order={s['name']:i for i,s in enumerate(route['shots'])};pairs.sort(key=lambda p:order[p['name']]);captures.sort(key=lambda p:order[p['shot']['name']])
            write(gallery/'comparison.json',dict(route=route,pairs=pairs))
            write(root/'native-captures.json',dict(version=package['version'],captures=captures,mounted_payloads=expected,
                  diagnostic_safety_disabled=True,gameplay_validation=False))
            print(ident,str(len(pairs))+'/'+str(len(route['shots'])),shot['name'],flush=True)
        logs=c.export_logs()
        if logs['script_errors'] or logs['native_crashes']:raise ValueError('Native errors recorded in survey')
        write(root/'validated.json',dict(version=package['version'],shots=len(captures),mounted_payload_verified=True,
              native_cameras_verified=True,diagnostic_safety_disabled=True,logs_clean=True))
    finally:
        c.export_logs();c.request('/shutdown',{})


def publish():
    from publish_comparison_site import export
    config=json.loads((ROOT/'site/maps.json').read_text());overrides={};summary={}
    for m in config['maps']:
        ident=m['id'];proof=json.loads((OUT/ident/'validated.json').read_text());route=json.loads((OUT/ident/'route.json').read_text())
        if proof['shots']!=len(route['shots']):raise ValueError('Incomplete native gallery')
        current=json.loads((ROOT/'northstar'/m['package']/'mod.json').read_text())['Version']
        if proof['version']!=current:raise ValueError('Map version changed after capture')
        payload=json.loads((OUT/ident/'native-captures.json').read_text())['mounted_payloads']
        for rel,sha in payload.items():
            if digest(ROOT/'northstar'/m['package']/rel)!=sha:raise ValueError('Runtime changed after capture')
        if ident=='drop-off':
            route['shots'].sort(key=lambda s:s['name']!='court-overview')
            comparison_path=OUT/ident/'comparison/comparison.json'
            comparison=json.loads(comparison_path.read_text());comparison['route']=route
            order={s['name']:i for i,s in enumerate(route['shots'])}
            comparison['pairs'].sort(key=lambda p:order[p['name']]);write(comparison_path,comparison)
            write(OUT/ident/'route.json',route)
            write(ROOT/'r5-harness/routes'/(ident+'-release-survey.json'),route)
        m['comparison']=(OUT/ident/'comparison').relative_to(ROOT).as_posix()
        m['route']='r5-harness/routes/'+ident+'-release-survey.json';m['notes']=RELEASES[m['package']]['notes']
        overrides[ident]=m['comparison'];summary[ident]=dict(version=current,shots=proof['shots'])
    write(ROOT/'site/maps.json',config)
    export(SNAPSHOT,overrides)
    write(ROOT/'docs/site-image-refresh-2026-10-18.json',dict(snapshot=SNAPSHOT,maps=summary,
          all_native_images_recaptured=True,existing_apex_reference_dates_preserved=True,
          native_payloads_and_camera_poses_verified=True,diagnostic_safety_disabled=True,gameplay_validation=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['plan','source-screen','capture','publish']);p.add_argument('map',nargs='?');p.add_argument('--shots',nargs='+')
    a=p.parse_args();{'plan':plan,'source-screen':source_screen,'capture':lambda:capture(a.map,a.shots),'publish':publish}[a.action]()
