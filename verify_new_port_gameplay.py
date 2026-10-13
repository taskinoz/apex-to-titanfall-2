"""Validate the exact staged preview in the owned native game, without claiming AI or Titan modes."""
import argparse
import hashlib
import json
import sys
import time
from new_arena_ports import CONFIG, ROOT, folder
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller
from verify_new_arena_runtime import mounted_bsp,mounted_material_pack


def verify(ident):
    c=Controller();cfg=CONFIG[ident];out=folder(ident)/'runtime';out.mkdir(exist_ok=True)
    sha=mounted_bsp(c,ident);records=[]
    for mode in ('ps','ffa'):
        c.load(cfg['target'],mode,120);time.sleep(20)
        live=c.command('server','mode_check')['data']
        starts=[p for p in live['liveSpawns'] if p['classname']=='info_spawnpoint_human_start']
        if {p['team'] for p in starts}!={2,3}:raise RuntimeError('Opposing team starts missing')
        if not all(p['clear'] and p['supported'] for p in live['liveSpawns']):
            raise RuntimeError('Blocked or unsupported live spawn')
        # FFA assigns its own player teams. Forcing a two-team player in FFA
        # breaks the stock scoreboard; exercise team selection only in PS.
        teams=[c.command('server','respawn',team=t)['data'] for t in (2,3)] if mode=='ps' else []
        contacts=[];screens=[]
        for team in (2,3):
            p=next(p for p in starts if p['team']==team)['origin']
            trace=c.command('server','trace',px=p[0],py=p[1],pz=p[2],ex=p[0],ey=p[1],ez=p[2]-32)['data']
            if trace['startSolid'] or trace['fraction']>=1:raise RuntimeError('Spawn floor contact failed')
            contacts.append(trace)
            if mode=='ps':
                for pitch in (-60,0,60):
                    c.camera([p[0],p[1],p[2]+60],[pitch,0 if team==2 else 180,0],90,1)
                    shot=c.capture(ident+'-team-'+str(team)+'-pitch-'+str(pitch))
                    screens.append(shot)
        c.command('client','camera_clear');c.command('server','camera_restore')
        logs=c.export_logs()
        if logs['script_errors'] or logs['native_crashes']:raise RuntimeError('Native gameplay log errors')
        records.append(dict(mode=mode,live=live,teams=teams,floor_contacts=contacts,angle_captures=screens))
        print(ident,mode,'live spawn, team selection, floor checks passed',flush=True)
    c.load(cfg['target'],'ps',120);time.sleep(15)
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+70
    while time.monotonic()<deadline:
        state=c.request('/status')
        if all(state.get('contexts',{}).get(ctx,{}).get('level')=='mp_lobby' for ctx in ('ui','server','client')):break
        if not state['game_running']:raise RuntimeError('Game exited after postmatch')
        time.sleep(1)
    else:raise RuntimeError('Postmatch did not return to lobby')
    c.load('mp_coliseum','ps',120);time.sleep(12)
    c.load(cfg['target'],'ps',120);time.sleep(15)
    logs=c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:raise RuntimeError('Native reload log errors')
    result=dict(map=cfg['target'],bsp_sha256=sha,material_pack_sha256=mounted_material_pack(c,ident),mounted_payload_verified=True,
                modes=records,postmatch_lobby=True,stock_map_reload=True,logs=logs,
                limitations=['One local client; multiplayer load and balance not tested',
                             'AI, Titan modes and Apex training interactions not validated',
                             'Safety entity presence checked; every hazard not physically exercised'])
    (out/'gameplay-validation.json').write_text(json.dumps(result,indent=2))
    print(ident,'postmatch and stock-map reload passed',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=CONFIG);verify(p.parse_args().map)
