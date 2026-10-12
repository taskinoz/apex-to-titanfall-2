"""Native screenshots, source-collider contacts and gameplay checks for fill candidates."""
import argparse
import collections
import json
import shutil
import sys
import time
from pathlib import Path

from build_arena_fill import CONFIG, OUT, ROOT, VERSIONS
from package_player_mods import digest
from repair_preview_index_padding import read_lumps
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller
import numpy as np


def capture(ident):
    config=CONFIG[ident];c=Controller();state=c.wait_map(config['map'],300);time.sleep(20)
    work=OUT/ident/'runtime';work.mkdir(parents=True,exist_ok=True)
    source=ROOT/'r5-harness/output'/(ident+'-survey');comparison=json.loads((source/'comparison.json').read_text())
    staged=Path(c.session['game'])/c.session['profile']/'mods'/('PhaseRunner.Preview' if ident=='drop-off' else 'MapTest.Extra')
    signatures={}
    for name in ('mod/maps/'+config['map']+'.bsp','paks/'+ident.replace('-','_')+'_fill.rpak','paks/rpak.json'):
        wanted=digest(OUT/'candidates'/config['package']/name);assert wanted==digest(staged/name);signatures[name]=wanted
    gallery=OUT/ident/'comparison';gallery.mkdir(exist_ok=True)
    pairs=[];route=comparison['route'];native=[]
    for pair,shot in zip(comparison['pairs'],route['shots'],strict=True):
        c.camera(shot['origin'],shot['angles'],shot.get('fov',90),2)
        captured=c.capture(ident+'-fill-'+shot['name'])
        assert captured['state']['contexts']['client']['level']==config['map']
        assert captured['state']['contexts']['client']['alive']
        dst=gallery/(shot['name']+'-northstar.png');shutil.copy2(captured['path'],dst);assert digest(dst)==captured['sha256']
        src=source/pair['r5r']['gallery_path'];assert digest(src)==pair['r5r']['sha256']
        srcdest=gallery/(shot['name']+'-r5r.png');shutil.copy2(src,srcdest)
        meta={k:captured[k] for k in ('width','height','captured','sha256')};meta['gallery_path']=dst.name
        source_meta=dict(pair['r5r']);source_meta['gallery_path']=srcdest.name
        pairs.append(dict(name=shot['name'],r5r=source_meta,northstar=meta));native.append(dict(shot=shot,capture=captured))
        print('Native view',ident,shot['name'],str(dst),flush=True)
    (gallery/'comparison.json').write_text(json.dumps(dict(route=route,pairs=pairs),indent=2))
    # Complete camera-angle sweeps in a central location, without changing its position.
    center=([0,-2600,-1216] if ident=='phase-runner' else [0,1950,300]);sweep=[]
    for yaw in range(0,360,90):
        for pitch in (-25,25):
            c.camera(center,[pitch,yaw,0],90,1)
            sweep.append(c.capture(ident+'-fill-sweep-'+str(yaw)+'-'+('up' if pitch<0 else 'down')))
    plan=json.loads((OUT/ident/'plan.json').read_text());payload=np.load(OUT/ident/'addition.npz');physical=payload['collision'];payload.close()
    cursor=0;seen=collections.Counter();contacts=[]
    for prop in plan['placements']:
        n=prop['collision_triangles'];faces=physical[cursor:cursor+n];cursor+=n
        if not n or seen[prop['model']]>=2:continue
        seen[prop['model']]+=1
        normal=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);area=np.linalg.norm(normal,axis=1)
        scores=area*(1-np.abs(normal[:,2])/np.maximum(area,1e-9));candidates=np.argsort(scores)[-12:][::-1]
        accepted=None;attempts=[]
        for i in candidates:
            if area[i]<.01:continue
            axis=normal[i]/area[i];point=faces[i].mean(0)
            for side in (1,-1):
                start=point+axis*side*16;end=point-axis*side*16
                result=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),map(float,[*start,*end]))))
                attempts.append(result)
                if not result['data']['startSolid'] and .02<result['data']['fraction']<.99 and np.linalg.norm(np.asarray(result['data']['end'])-point)<4:
                    accepted=dict(index=prop['index'],model=prop['model'],expected_surface=point.tolist(),trace=result);break
            if accepted:break
        assert accepted is not None, f'No native surface contact for added prop {prop["index"]}: {attempts}'
        contacts.append(accepted)
    mode=c.command('server','mode_check');teams=[]
    c.command('client','camera_clear')
    for team in (2,3):
        result=c.command('server','respawn',team=team);assert result['data']['team']==team;teams.append(result)
    logs=c.export_logs();assert not logs['script_errors']
    report=dict(version=VERSIONS[ident],map=config['map'],game_pid=state['game_pid'],staged_sha256=signatures,
        matched_source_views=native,angle_sweeps=sweep,new_prop_collision_contacts=contacts,mode=mode,team_starts=teams,logs=logs)
    (work/'capture-validation.json').write_text(json.dumps(report,indent=2))
    print(ident,'native views',len(native),'angle checks',len(sweep),'collider contacts',len(contacts),'teams',len(teams),flush=True)


def modes(resume=False):
    sys.path.insert(0,str(ROOT/'tools/bsp_tool'));from bsp_tool.branches.shared import Entities
    c=Controller();report=json.loads((OUT/'mode-validation.json').read_text()) if resume else []
    wanted={config['map']:digest(OUT/'candidates'/config['package']/'mod/maps'/(config['map']+'.bsp')) for config in CONFIG.values()}
    report=[r for r in report if r.get('bsp_sha256')==wanted[r['map']]]
    assert all(not r['logs']['script_errors'] for r in report)
    for ident,modes in [('drop-off',('ps','ffa')),('phase-runner',('tdm','ps','ctf','cp','fastball','aitdm'))]:
        config=CONFIG[ident];l=read_lumps(OUT/'candidates'/config['package']/'mod/maps'/(config['map']+'.bsp'),(0,))
        staged=Path(c.session['game'])/c.session['profile']/'mods'/('PhaseRunner.Preview' if ident=='drop-off' else 'MapTest.Extra')
        assert digest(staged/'mod/maps'/(config['map']+'.bsp'))==digest(OUT/'candidates'/config['package']/'mod/maps'/(config['map']+'.bsp'))
        markers=[e for e in Entities.from_bytes(l[0]) if 'spawnpoint' in e.get('classname','') and 'origin' in e]
        for mode in modes:
            if any(r['map']==config['map'] and r['mode']==mode for r in report):continue
            current=c.request('/status')
            if current['contexts'].get('server',{}).get('mode')==mode and current['contexts'].get('client',{}).get('level')==config['map'] and current['contexts']['client']['alive']:
                state=c.wait_map(config['map'],300)
            else:state=c.load(config['map'],mode,300)
            time.sleep(20)
            counts=c.command('server','mode_check');assert counts['data']['map']==config['map'] and counts['data']['mode']==mode
            pilot=[];titan=[]
            for ent in markers:
                point=list(map(float,ent['origin'].split()))
                (titan if 'titan' in ent['classname'] else pilot).append(point)
            hulls=c.command('server','spawn_probe',points=pilot+titan,timeout=40)['data']
            live_spawn_checks=None
            if ident=='phase-runner':
                # The native spawn loader has already grounded the live entities.
                # Reprojecting raw BSP positions from +96 can hit an overhang
                # instead of the actual spawn floor. Validate the live entities.
                live_spawn_checks=counts['data']['liveSpawns']
                assert len(live_spawn_checks)==84
                assert all(p['clear'] and p['supported'] for p in live_spawn_checks),live_spawn_checks
                assert all(o['valid'] for o in counts['data']['objectives']),counts
                if mode=='fastball':assert counts['data']['panels']==3
            else:
                assert all(p['floor'] and p['pilot'] for p in hulls[:len(pilot)]), (ident,mode,'Pilot hull obstruction',hulls)
            if mode=='ctf':assert counts['data']['entities']['info_spawnpoint_flag']==2
            if mode=='cp':assert counts['data']['entities']['info_hardpoint']==3
            logs=c.export_logs();assert not logs['script_errors']
            result=dict(map=config['map'],mode=mode,bsp_sha256=wanted[config['map']],game_pid=state['game_pid'],counts=counts,raw_position_ground_probes=hulls,live_spawn_checks=live_spawn_checks,logs=logs)
            report.append(result);(OUT/'mode-validation.json').write_text(json.dumps(report,indent=2))
            print('Native mode',ident,mode,'spawn/flag hull checks',len(hulls),'passed',flush=True)
    return report


def reload():
    c=Controller();state=c.load(CONFIG['drop-off']['map'],'ps',300);time.sleep(20)
    pid=state['game_pid'];report=dict(pid_before=pid)
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+75
    while time.monotonic()<deadline:
        state=c.request('/status')
        if not state['game_running']:raise RuntimeError('Game exited after match')
        if state['contexts'].get('client',{}).get('level')=='mp_lobby':break
        time.sleep(1)
    else:raise TimeoutError('Postmatch did not return to lobby')
    report['postmatch']=dict(level=state['contexts']['client']['level'],pid=state['game_pid'])
    print('Postmatch lobby passed',flush=True)
    report['reloads']=[]
    for name in ('mp_coliseum',CONFIG['drop-off']['map'],CONFIG['phase-runner']['map']):
        state=c.load(name,'ps',300);time.sleep(20)
        assert state['game_pid']==pid and state['contexts']['client']['alive']
        package='MapTest.Extra' if name=='mp_phase_runner' else 'PhaseRunner.Preview'
        sha=digest(Path(c.session['game'])/c.session['profile']/'mods'/package/'mod/maps'/(name+'.bsp')) if name!='mp_coliseum' else None
        report['reloads'].append(dict(map=name,pid=state['game_pid'],bsp_sha256=sha))
        print('Same-process reload',name,'passed',flush=True)
    report['pid_after']=state['game_pid'];report['logs']=c.export_logs();assert not report['logs']['script_errors']
    (OUT/'reload-validation.json').write_text(json.dumps(report,indent=2))


def details():
    import math
    c=Controller();c.wait_map(CONFIG['phase-runner']['map'],300)
    work=OUT/'phase-runner';plan=json.loads((work/'plan.json').read_text())
    payload=np.load(work/'addition.npz');geometry=payload['data'];payload.close();report=[]
    for name in ('ground_plant_desertlands_01_group_01','flowers_ground_01','power_cell_64'):
        choices=[p for p in plan['placements'] if p['model'].endswith('/'+name+'.rmdl')]
        if name=='ground_plant_desertlands_01_group_01':
            choices=[p for p in choices if abs(p['angles'][0])<8 and abs(p['angles'][2])<8]
        goal_y=1000 if name=='ground_plant_desertlands_01_group_01' else -2600
        prop=min(choices,key=lambda p:abs(p['origin'][0])+abs(p['origin'][1]-goal_y))
        faces=geometry[prop['first_triangle']:prop['first_triangle']+prop['triangles'],:,:3]
        center=(faces.min((0,1))+faces.max((0,1)))/2
        extent=float(np.linalg.norm(faces.max((0,1))-faces.min((0,1))))
        offset=np.asarray([0,-max(110,extent*1.2),max(65,extent*.5)])
        origin=center+offset;angles=[math.degrees(math.atan2(offset[2],abs(offset[1]))),90,0]
        c.camera(origin.tolist(),angles,75,2);r=c.capture('phase-runner-fill-detail-'+name)
        report.append(dict(model=name,source_index=prop['index'],capture=r))
        print('Native added-detail view',name,r['path'],flush=True)
    logs=c.export_logs();assert not logs['script_errors'] and not logs.get('native_crashes')
    (work/'runtime/detail-validation.json').write_text(json.dumps(dict(views=report,logs=logs),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('capture','modes','reload','details'));parser.add_argument('map',choices=CONFIG,nargs='?');parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.action=='capture':capture(args.map)
    elif args.action=='modes':modes(args.resume)
    elif args.action=='reload':reload()
    else:details()
