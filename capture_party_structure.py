"""Capture edge/roof views in explicitly marked isolated diagnostic sessions.

Remote camera poses cross source safety areas. Remove their trigger entities
only from this owned runtime; the map file is unchanged. Reload before gameplay
validation. Source and native run serially. These shots do not test safety areas.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANCHOR = [-2537.5, 3894.8, 651]


def capture(engine, names=None):
    sys.path.insert(0, str(ROOT/('r5-harness' if engine=='source' else 'test-harness')))
    from harness import Controller
    c = Controller()
    identity = {}
    if engine == 'native':
        from verify_new_arena_runtime import mounted_bsp, mounted_material_pack
        identity = dict(bsp_sha256=mounted_bsp(c,'party-crasher'),
                        material_pack_sha256=mounted_material_pack(c,'party-crasher'),
                        mounted_payload_verified=True)
    route = json.loads((ROOT/'r5-harness/routes/party-crasher-edge-roof-survey.json').read_text())
    if engine == 'native':
        c.command('ui','console',command='script foreach(string cls in ["trigger_out_of_bounds","trigger_hurt"]) foreach(entity t in GetEntArrayByClass_Expensive(cls)) t.Destroy()')
        c.command('server','respawn',team=2)
        counts=c.command('server','mode_check')['data']['entities']
        if counts['trigger_out_of_bounds'] or counts['trigger_hurt']:
            raise RuntimeError('Diagnostic safety removal did not execute')
    else:
        c.script('server','foreach(string cls in ["trigger_out_of_bounds","trigger_hurt"]) foreach(entity t in GetEntArrayByClass_Expensive(cls)) t.Destroy(); R5H_Status($TICKET)')
    identity['diagnostic_boundary_triggers_removed']=True
    identity['diagnostic_hurt_triggers_removed']=True
    identity['map_file_safety_unchanged']=True
    # Keep a short, equal settling interval in both engines. Full map assets
    # are already loaded; the return to spawn prevents accumulated OOB deaths.
    for shot in route['shots']:
        shot['settle'] = 2
    out = ROOT/'output/party-edge-roof'
    out.mkdir(exist_ok=True)
    selected=[s for s in route['shots'] if names is None or s['name'] in names]
    if names and set(names)!={s['name'] for s in selected}:
        raise ValueError('Unknown survey shot')
    previous=out/(engine+'.json')
    key='captures' if engine=='source' else 'shots'
    results=[]
    if names and previous.exists():
        prior=json.loads(previous.read_text())
        results=[r for r in prior[key] if r['name'] not in names]
    for shot in selected:
        c.camera(shot['origin'], shot['angles'], shot['fov'], shot['settle'])
        meta = c.capture('party-structure-'+shot['name'])
        results.append(dict(name=shot['name'], camera=shot,
                            **{('source' if engine=='source' else 'northstar'):meta}))
        if engine=='native' and not meta['state']['contexts']['client'].get('alive'):
            raise RuntimeError('The test player died before the capture; do not accept this view')
        (out/(engine+'.json')).write_text(json.dumps(dict(route=route, **identity, **{key:results}), indent=2))
        print(engine, shot['name'], meta['path'], flush=True)
    logs = c.export_logs()
    if engine=='native' and (logs['script_errors'] or logs['native_crashes']):
        raise RuntimeError('Native errors during the accepted survey')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('engine', choices=['source','native'])
    p.add_argument('--shots',nargs='+')
    args=p.parse_args()
    capture(args.engine,args.shots)
