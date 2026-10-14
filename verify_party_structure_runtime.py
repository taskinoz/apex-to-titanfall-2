"""Check native collider contacts, both team spawns and reloads for the append."""
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np
from new_arena_ports import ROOT, folder
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller
from verify_new_arena_runtime import mounted_bsp, mounted_material_pack


def run():
    out=folder('party-crasher')/'structure-recovery'
    c=Controller()
    # Restore original trigger entities after the explicitly marked camera run.
    c.load('mp_party_crasher','ps',180)
    sha=mounted_bsp(c,'party-crasher');pack=mounted_material_pack(c,'party-crasher')
    c.command('client','camera_clear')
    c.command('server','respawn',team=2)
    mode=c.command('server','mode_check')['data']
    if mode['entities']['trigger_out_of_bounds']!=67 or mode['entities']['trigger_hurt']!=2:
        raise ValueError('Source safety triggers must be restored for gameplay checks')
    if not all(p['clear'] and p['supported'] for p in mode['liveSpawns']):
        raise ValueError('A native spawn is obstructed or unsupported')
    teams=[]
    for team in (2,3):
        result=c.command('server','respawn',team=team)
        if result['data']['team']!=team:
            raise ValueError('Incorrect spawn team')
        teams.append(result)
    plan=json.loads((out/'plan.json').read_text());a=np.load(out/'addition.npz');physical=a['collision'];a.close()
    cursor=0;seen=collections.Counter();contacts=[]
    for prop in plan['placements']:
        n=prop['collision_triangles'];faces=physical[cursor:cursor+n];cursor+=n
        if not n or seen[prop['model']]>=1:
            continue
        seen[prop['model']]+=1
        normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]);areas=np.linalg.norm(normals,axis=1)
        accepted=None
        for i in np.argsort(areas)[-16:][::-1]:
            if areas[i]<.01:continue
            axis=normals[i]/areas[i];point=faces[i].mean(0)
            for side in (1,-1):
                start=point+axis*side*16;end=point-axis*side*16
                result=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),map(float,[*start,*end]))))
                r=result['data']
                if not r['startSolid'] and .02<r['fraction']<.99 and np.linalg.norm(np.asarray(r['end'])-point)<4:
                    accepted=dict(index=prop['index'],model=prop['model'],expected_surface=point.tolist(),trace=result)
                    break
            if accepted:break
        if not accepted:
            raise ValueError('No native surface contact for added source prop '+str(prop['index']))
        contacts.append(accepted)
    report=dict(bsp_sha256=sha,material_pack_sha256=pack,mounted_payload_verified=True,
                mode=mode,teams=teams,contacts=contacts,postmatch_lobby=False,stock_map_reload=False)
    (out/'runtime-validation.json').write_text(json.dumps(report,indent=2))
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        state=c.request('/status')
        if not state['game_running']:raise RuntimeError('Game exited after match')
        if state['contexts'].get('client',{}).get('level')=='mp_lobby':break
        time.sleep(1)
    else:raise TimeoutError('Postmatch did not return to lobby')
    report['postmatch_lobby']=True
    state=c.load('mp_coliseum','ps',180)
    if not state['contexts']['client']['alive']:raise RuntimeError('Stock reload failed')
    report['stock_map_reload']=True
    c.load('mp_party_crasher','ps',180)
    mounted_bsp(c,'party-crasher');mounted_material_pack(c,'party-crasher')
    report['party_reload']=True
    report['logs']=c.export_logs()
    if report['logs']['script_errors'] or report['logs']['native_crashes']:raise RuntimeError('Native errors')
    (out/'runtime-validation.json').write_text(json.dumps(report,indent=2))
    print('Passed',len(contacts),'source-collider contacts, both teams, postmatch lobby, stock reload and Party Crasher reload',flush=True)


if __name__=='__main__':run()
