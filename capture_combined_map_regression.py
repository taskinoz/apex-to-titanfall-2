"""Exercise all five installed maps in one owned process; retain native evidence."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS, audit

sys.path.insert(0, str(ROOT / 'test-harness'))
from harness import Controller


def run(package, expanded=False):
    c = Controller()
    map_name = MAPS[package]
    state = c.request('/status')
    if not all(state.get('contexts', {}).get(k, {}).get('level') == map_name for k in ('ui','client','server')):
        c.load(map_name, 'ps', 300)
    else:
        c.wait_map(map_name, 60)
    time.sleep(12)
    evidence = ROOT / 'output/atlas-lifetime'
    evidence.mkdir(exist_ok=True)
    state = c.request('/status')
    profile = Path(c.session['game']) / c.session['profile']
    companions = list((profile/'mods').glob('*/paks/apex_maps_ui.rpak'))
    if len(companions)!=1 or hashlib.sha256(companions[0].read_bytes()).hexdigest()!=hashlib.sha256((ROOT/'northstar/ApexMaps.UI/paks/apex_maps_ui.rpak').read_bytes()).hexdigest():
        raise RuntimeError('Exactly one matching shared UI atlas is required')
    mounted = {}
    for n, m in MAPS.items():
        paths = [p for p in (profile / 'mods').glob('*/mod.json')
                 if json.loads(p.read_text(encoding='utf-8-sig'))['Name'] == n]
        if len(paths) != 1:
            raise RuntimeError('Combined install lacks exactly one enabled ' + n)
        mounted[n] = audit(paths[0].parent / 'paks', m)
        mounted[n]['config_sha256'] = hashlib.sha256((paths[0].parent/'paks/rpak.json').read_bytes()).hexdigest()
    ident = next((n for n, p in [('firing-range','ApexFiringRange'), ('party-crasher','ArenaPartyCrasher'),
                               ('overflow','ArenaOverflow')] if p == package), None)
    if expanded and ident:
        route = json.loads((ROOT / 'r5-harness/routes' / (ident+'-expanded-survey.json')).read_text())
    else:
        poses = {'PhaseRunner': ([0,-5000,1400],[28,90,0]),
                 'ArenaComposite': ([0,2200,900],[22,90,0]),
                 'ApexFiringRange': ([2000,-5000,2200],[22,90,0]),
                 'ArenaPartyCrasher': ([3385.96,-1591.92,2220.45],[12,97.77,0]),
                 'ArenaOverflow': ([-324,-6295,1393],[15,61.89,0])}
        origin, angles = poses[package]
        route = dict(shots=[dict(name='combined-install',origin=origin,angles=angles,fov=90,settle=4)])
    shots = []
    for pose in route['shots']:
        c.camera(pose['origin'], pose['angles'], pose['fov'], pose['settle'])
        shot = c.capture(package.lower()+'-'+pose['name'])
        shots.append(dict(name=pose['name'], camera=pose, northstar=shot))
        print(package, pose['name'], shot['path'], flush=True)
    c.command('client','camera_clear')
    logs = c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:
        raise RuntimeError('Native errors: ' + str(logs))
    path = evidence / (package+'.json')
    path.write_text(json.dumps(dict(map=map_name, installed=mounted, process=state['game_pid'],
                                  shots=shots, logs=logs, capture_only=True),indent=2))
    print('Saved', path, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package', choices=MAPS)
    p.add_argument('--expanded', action='store_true')
    a = p.parse_args()
    run(a.package, a.expanded)
