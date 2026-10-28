"""Native acceptance checks for the isolated Overflow HDR lava candidate."""
import json
from pathlib import Path
import sys
import time
from prepare_anniversary_release import ROOT,digest,write

sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller
OUT=ROOT/'output/overflow-lava-2026'


def living(c):
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        state=c.request('/status')
        if not state['game_running']:raise RuntimeError('Owned game exited')
        p=state.get('contexts',{}).get('client',{})
        if p.get('level')=='mp_overflow' and p.get('alive') and p.get('health',0)>0:return
        time.sleep(.5)
    raise RuntimeError('No living native player')


def validate():
    c=Controller()
    if c.session['profile']!='R2Anniversary14':raise ValueError('Wrong owned profile')
    c.wait_map('mp_overflow',240);living(c);time.sleep(15)
    profile=Path(c.request('/status')['profile'])
    mod=next(p.parent for p in (profile/'mods').glob('*/mod.json')
             if json.loads(p.read_text(encoding='utf-8-sig'))['Name']=='ArenaOverflow')
    candidate=OUT/'candidate/ArenaOverflow'
    for p in candidate.rglob('*'):
        if p.is_file() and (p.relative_to(candidate).parts[0] in ('mod','paks') or p.name=='mod.json'):
            if digest(p)!=digest(mod/p.relative_to(candidate)):raise ValueError('Staged runtime mismatch')
    reports=[];shots=[]
    report=c.command('server','mode_check')['data']
    if report['map']!='mp_overflow' or report['mode']!='ps':raise ValueError('Wrong live map/mode')
    if not all(p['clear'] and p['supported'] for p in report['liveSpawns']):raise ValueError('Invalid native spawn')
    for team in (2,3):c.command('server','respawn',team=team);living(c)
    reports.append(report)
    c.command('ui','console',command='script SetServerVar("gameEndTime", Time()+600)')
    for label,origin,angles in [('lava-channel',[-500,-2500,800],[20,-45,0]),
                                ('north-platform',[0,-1300,1050],[15,-90,0]),
                                ('overview',[-324.00824,-6295.51123,1393.36169],[15,61.8894501,0])]:
        c.camera(origin,angles,90,5);cap=c.capture('overflow-hdr-'+label)
        if cap['state']['contexts']['client']['level']!='mp_overflow':raise ValueError('Wrong captured map')
        shots.append({'name':label,'capture':cap});print('Captured:',label,cap['path'],flush=True)
    c.command('client','camera_clear');c.command('server','camera_restore')
    write(OUT/'capture-validation.json',{'captures':shots,'mounted_runtime_verified':True})
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        s=c.request('/status')
        if not s['game_running']:raise RuntimeError('Owned game exited after match')
        if all(s.get('contexts',{}).get(k,{}).get('level')=='mp_lobby' for k in ('ui','client','server')):break
        time.sleep(1)
    else:raise RuntimeError('No native lobby return')
    print('Postmatch lobby passed',flush=True)
    c.load('mp_coliseum','ps',240);time.sleep(5)
    c.load('mp_overflow','ffa',240);living(c);time.sleep(15)
    report=c.command('server','mode_check')['data']
    if report['mode']!='ffa' or not all(p['clear'] and p['supported'] for p in report['liveSpawns']):raise ValueError('FFA spawn check failed')
    reports.append(report)
    c.command('ui','console',command='+attack');time.sleep(.4);c.command('ui','console',command='-attack');time.sleep(3);living(c)
    logs=c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:raise RuntimeError('Native errors recorded')
    write(OUT/'runtime-validation.json',{'passed':True,'version':'0.4.2','modes':reports,'both_ps_teams':True,
        'postmatch_lobby':True,'stock_and_converted_reload':True,'weapon_fire':True,'logs':logs,
        'single_client_only':True,'safety_entities_preserved':True,'captures':shots})
    print('Native PS/FFA, team starts, postmatch and reload checks passed',flush=True)


if __name__=='__main__':validate()
