"""Finish the five-map UI regression through multiplayer lobby and stock reload."""
import hashlib
import json
import sys
import time
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS, audit_shared
sys.path.insert(0,str(ROOT/'test-harness'))
from harness import Controller


def verify():
    c=Controller()
    records={n:json.loads((ROOT/'output/atlas-lifetime'/(n+'.json')).read_text()) for n in MAPS}
    pids={d['process'] for d in records.values()}
    if len(pids)!=1 or c.request('/status')['game_pid'] not in pids:
        raise ValueError('All five maps must pass in one owned process')
    c.command('client','camera_clear')
    c.command('server','camera_restore')
    c.command('ui','console',command='script SetGameState( eGameState.Postmatch )')
    deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        s=c.request('/status')
        if not s['game_running']:raise RuntimeError('Game exited during postmatch')
        if all(s.get('contexts',{}).get(k,{}).get('level')=='mp_lobby' for k in ('ui','server','client')):break
        time.sleep(1)
    else:raise RuntimeError('Multiplayer lobby was not reached')
    time.sleep(5)
    lobby=c.capture('five-maps-multiplayer-lobby')
    print('All five maps returned to multiplayer lobby',flush=True)
    c.load('mp_coliseum','ps',180)
    time.sleep(8)
    stock=c.capture('five-maps-stock-coliseum')
    c.load('mp_apex_firing_range','ps',180)
    time.sleep(12)
    c.camera([500,-1500,-30],[8,80,0],90,4)
    reloaded=c.capture('five-maps-firing-range-reloaded')
    c.command('client','camera_clear')
    logs=c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:
        raise RuntimeError('Native lifecycle errors: '+str(logs))
    result=dict(passed=True,multiplayer_lobby_verified=True,stock_reload_verified=True,
                shared=audit_shared(),shared_pack_sha256=hashlib.sha256((ROOT/'northstar/ApexMaps.UI/paks/apex_maps_ui.rpak').read_bytes()).hexdigest(),
                maps={n:dict(map=d['map'],config_sha256=d['installed'][n]['config_sha256'],
                             native_views=len(d['shots']),all_five_installed=True,ui_companion_verified=True,
                             screenshots=[dict(name=s['name'],sha256=s['northstar']['sha256']) for s in d['shots']])
                      for n,d in records.items()},
                lifecycle_captures=[dict(sha256=s['sha256'],width=s['width'],height=s['height']) for s in (lobby,stock,reloaded)],
                single_client=True,multiplayer_load_verified=False,ai_verified=False,
                prior_failures=['Native 20-atlas pool error','Minimap-only filtering insufficient',
                                'Early world-regex candidate had fallback materials',
                                'UI-only filtering still loaded unwanted presentations through shared dependency path'])
    path=ROOT/'docs/conversion/ui-atlas-lifetime-validation.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'output/atlas-lifetime/lifecycle-private.json').write_text(json.dumps(dict(lobby=lobby,stock=stock,reloaded=reloaded,logs=logs),indent=2))
    print('Shared UI atlas, five maps, multiplayer lobby and stock reload passed',flush=True)


if __name__=='__main__':verify()
