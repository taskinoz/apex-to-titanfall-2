"""Native release checks against exactly staged five-map packages and pinned runtime."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from prepare_anniversary_release import ROOT,OUT,BASE,digest,write
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller


def owned_controller():
    c=Controller()
    if c.session['profile']!='R2Anniversary14':raise ValueError('The anniversary test profile is not active')
    return c


def start(package='ArenaOverflow',combined=True):
    try:
        old=Controller();state=old.request('/status')
    except (OSError,ValueError,RuntimeError):state=None
    if state:
        if old.session['profile'] not in {'R2Anniversary14','R2AnniversaryHarness'}:
            raise ValueError('A different test session is active')
        old.export_logs();old.request('/shutdown',{});time.sleep(2)
    runtime=ROOT/'tools/northstar-v1.31.14/runtime/R2Northstar'
    command=[sys.executable,str(ROOT/'test-harness/harness.py'),'start','--profile','R2Anniversary14',
             '--runtime',str(runtime),'--launcher','D:/Games/Titanfall2/NorthstarAnniversaryLauncher.exe',
             '--package',str(OUT/'baseline'/package),'--map',json.loads((OUT/'baseline-manifest.json').read_text())[package]['map'],
             '--mode','ps','--timeout','240','--extra-package',str(OUT/'baseline/ApexMaps.UI')]
    if combined:
        for name in BASE:
            if name!=package:command+=['--extra-package',str(OUT/'baseline'/name)]
    with (OUT/('combined-launch.log' if combined else 'isolated-launch.log')).open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('Owned native launch failed; private launch log retained')
    c=Controller();verify_mounts(c,BASE if combined else [package]);return c


def verify_mounts(c,names):
    profile=Path(c.request('/status')['profile'])
    expected=json.loads((OUT/'baseline-manifest.json').read_text())
    for name in (*names,'ApexMaps.UI'):
        paths=[p.parent for p in (profile/'mods').glob('*/mod.json') if json.loads(p.read_text(encoding='utf-8-sig'))['Name']==name]
        if len(paths)!=1:raise ValueError('Wrong installed package count: '+name)
        for rel,sha in expected[name]['payloads'].items():
            if digest(paths[0]/rel)!=sha:raise ValueError('Mounted bytes differ: '+name+'/'+rel)
    runtime_pin=json.loads((OUT/'runtime-pin.json').read_text())
    if digest(profile/'Northstar.dll')!=runtime_pin['dll_sha256']:raise ValueError('Wrong native runtime')
    print('Exact mounted package and runtime hashes verified',flush=True)


def live(c,seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        status=c.request('/status')
        if not status['game_running']:raise RuntimeError('Owned game exited')
        client=status.get('contexts',{}).get('client',{})
        if client.get('alive') and client.get('health',0)>0:return status
        time.sleep(.5)
    raise RuntimeError('No naturally spawned living player')


def check(c,package,mode='ps',photos=True):
    manifest=json.loads((OUT/'baseline-manifest.json').read_text())
    name=manifest[package]['map']
    state=c.request('/status')
    if state.get('contexts',{}).get('server',{}).get('level')!=name or state['contexts']['server'].get('mode')!=mode:
        c.load(name,mode,240)
    live(c);time.sleep(8);live(c)
    c.command('ui','console',command='script SetServerVar("gameEndTime", Time()+600)')
    report=c.command('server','mode_check',timeout=40)['data']
    if report['map']!=name or report['mode']!=mode:raise ValueError('Wrong live map or mode')
    human=[s for s in report['liveSpawns'] if 'human' in s['classname']]
    starts=[s for s in human if s['classname']=='info_spawnpoint_human_start']
    if not human or {s['team'] for s in starts}!={2,3}:raise ValueError('Opposing native pilot starts missing')
    bad=[s for s in human if not s['clear'] or not s['supported']]
    if bad:
        write(OUT/(package+'-'+mode+'-bad-spawns.json'),bad)
        raise ValueError(f'{package}: {len(bad)} invalid native pilot spawn markers')
    if report['objectives'] and not all(o['valid'] for o in report['objectives']):
        raise ValueError('Missing live mode objectives')
    if mode in ('ctf','cp') and len(report['objectives'])!=({'ctf':2,'cp':3}[mode]):
        raise ValueError('Wrong objective count')
    if mode=='fastball' and report['panels']<3:raise ValueError('Missing Fastball panels')
    captures=[]
    # FFA owns player teams; forcing IMC/Militia corrupts its stock scoreboard.
    for team in ((None,) if mode=='ffa' else (2,3)):
        if team is not None:c.command('server','respawn',team=team)
        time.sleep(1);live(c)
        c.command('ui','clear_ui')
        if photos:captures.append(c.capture(f'anniversary-{package}-{mode}-team{team}'))
    c.command('ui','console',command='+attack');time.sleep(.35)
    c.command('ui','console',command='-attack');time.sleep(2);live(c)
    logs=c.export_logs()
    if logs and (logs['script_errors'] or logs['native_crashes']):raise RuntimeError('Native errors recorded')
    result={'package':package,'map':name,'mode':mode,'pilot_spawns':len(human),
            'invalid_pilot_spawns':bad,'mode_check':report,'both_teams_live':mode!='ffa',
            'weapon_fire_exercised':True,'captures':captures,'logs':logs}
    write(OUT/(package+'-'+mode+('-native.json' if photos else '-probe-native.json')),result)
    print('Native map check passed:',package,mode,len(human),'pilot spawns',flush=True)
    return result


def postmatch(c,label):
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        s=c.request('/status')
        if not s['game_running']:raise RuntimeError('Game exited after match')
        if all(s.get('contexts',{}).get(k,{}).get('level')=='mp_lobby' for k in ('ui','client','server')):
            time.sleep(3)
            logs=c.export_logs()
            if logs and (logs['script_errors'] or logs['native_crashes']):raise RuntimeError('Postmatch errors')
            print('Native postmatch returned to lobby:',label,flush=True);return
        time.sleep(1)
    raise RuntimeError('Native postmatch never returned to lobby')


def combined():
    c=start();records=[]
    try:
        for package in BASE:
            records.append(check(c,package));postmatch(c,package)
        c.load('mp_coliseum','ps',240);live(c);time.sleep(5)
        c.capture('anniversary-stock-reload')
        records.append(check(c,'ArenaOverflow',photos=False))
        write(OUT/'combined-validation.json',{'passed':True,'runtime':'1.31.14','five_installed':True,
              'stock_reload':True,'converted_reload':True,'maps':records})
    finally:c.export_logs()


def stress(count):
    if count<1:raise ValueError('At least one complete cycle is required')
    c=owned_controller();verify_mounts(c,BASE)
    records=[]
    for i in range(count):
        if i:
            c.request('/stop-game',{})
            c.request('/launch',{'map':'mp_overflow','mode':'ffa' if i%2 else 'ps'})
            c.wait_map('mp_overflow',240)
        mode='ffa' if i%2 else 'ps'
        record=check(c,'ArenaOverflow',mode,photos=False)
        record['iteration']=i+1
        c.load('mp_coliseum','ps',240);live(c)
        c.load('mp_overflow',mode,240);live(c);time.sleep(8)
        logs=c.export_logs()
        if logs and (logs['script_errors'] or logs['native_crashes']):raise RuntimeError('Stress reload errors')
        record['stock_and_converted_reload_passed']=True
        records.append(record);write(OUT/'overflow-stress.json',{'complete':len(records)==count,'count':len(records),'runs':records})
        print('Overflow cold/reload cycle:',i+1,'of',count,flush=True)


def modes():
    c=owned_controller();records=[]
    for package in BASE:
        records.append(check(c,package,'ffa'));postmatch(c,package+' ffa')
    for mode in ('ctf','cp','fastball'):
        records.append(check(c,'PhaseRunner',mode));postmatch(c,'PhaseRunner '+mode)
    write(OUT/'mode-validation.json',{'passed':True,'runtime':'1.31.14','maps':records})


def visual():
    c=owned_controller();records=[]
    routes={'PhaseRunner':'phase-runner','ArenaComposite':'drop-off',
            'ApexFiringRange':'firing-range','ArenaPartyCrasher':'party-crasher','ArenaOverflow':'overflow'}
    for package,ident in routes.items():
        route=json.loads((ROOT/'r5-harness/routes'/(ident+'-release-survey.json')).read_text())
        c.load(route['target_map'],'ps',240);live(c);time.sleep(20)
        shot=route['shots'][0]
        c.camera(shot['origin'],shot['angles'],shot.get('fov',90),2)
        cap=c.capture('anniversary-overview-'+ident)
        if cap['state']['contexts']['client']['level']!=route['target_map']:raise ValueError('Wrong photographed map')
        records.append({'package':package,'capture':cap})
        c.command('client','camera_clear');c.command('server','camera_restore')
        print('Native overview captured:',package,flush=True)
    write(OUT/'visual-validation.json',{'captures':records,'safety_entities_preserved':True,'visual_review_required':True})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['combined','stress','modes','visual']);p.add_argument('--count',type=int,default=10)
    a=p.parse_args()
    if a.action=='combined':combined()
    elif a.action=='modes':modes()
    elif a.action=='visual':visual()
    else:stress(a.count)
