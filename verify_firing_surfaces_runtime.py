"""Native checks for Firing Range 0.4.0: restored visuals sit on source collision.

The landing pad adds no colliders; its deck and stairs already existed in the
source world collision. Vertical native traces must stop on the new visible
surfaces. Spawns, safety entities and reload/lobby transitions are rechecked.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
from new_arena_ports import ROOT, folder
sys.path.insert(0, str(ROOT/'test-harness'))
from harness import Controller
from verify_new_arena_runtime import mounted_bsp, mounted_material_pack

PROBE_MODELS = ('tday_vtol_landing_pad_square_01', 'landing_pad_tarmac_nobase', 'sewer_staircase_96_quad')
TOLERANCE = 16.0


def visual_top(triangles, x, y, below):
    """Highest visible surface crossing the vertical line (x, y) below a height."""
    p = triangles[:, :, :3].astype('f8')
    lo, hi = p[:, :, :2].min(1), p[:, :, :2].max(1)
    near = np.flatnonzero((lo[:, 0] <= x) & (hi[:, 0] >= x) & (lo[:, 1] <= y) & (hi[:, 1] >= y))
    best = None
    for i in near:
        a, b, c = p[i]
        d = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(d) < 1e-9:
            continue
        u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/d
        v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/d
        if min(u, v, 1-u-v) < 0:
            continue
        z = u*a[2]+v*b[2]+(1-u-v)*c[2]
        if z < below and (best is None or z > best):
            best = z
    return best


def run():
    out = folder('firing-range')/'surface-repair'
    c = Controller()
    c.load('mp_apex_firing_range', 'ps', 180)
    sha = mounted_bsp(c, 'firing-range'); pack = mounted_material_pack(c, 'firing-range')
    c.command('client', 'camera_clear')
    c.command('server', 'respawn', team=2)
    mode = c.command('server', 'mode_check')['data']
    entities = mode['entities']
    if entities.get('trigger_hurt') != 1 or entities.get('move_rope') != 7 or entities.get('keyframe_rope') != 7:
        raise ValueError('Source safety triggers and zipline ropes must be unchanged: '+json.dumps(entities))
    if not all(p['clear'] and p['supported'] for p in mode['liveSpawns']):
        raise ValueError('A native spawn is obstructed or unsupported')
    teams = []
    for team in (2, 3):
        result = c.command('server', 'respawn', team=team)
        if result['data']['team'] != team:
            raise ValueError('Incorrect spawn team')
        teams.append(result)
    plan = json.loads((out/'plan.json').read_text())
    addition = np.load(out/'addition.npz'); triangles = addition['triangles']; addition.close()
    contacts = []
    cursor = 0
    for prop in plan['placements']:
        own = triangles[cursor:cursor+prop['triangles'], :, :3].astype('f8'); cursor += prop['triangles']
        if Path(prop['model']).stem.lower() not in PROBE_MODELS:
            continue
        # Probe the centres of this placement's largest walkable faces.
        n = np.cross(own[:, 1]-own[:, 0], own[:, 2]-own[:, 0]); area = np.linalg.norm(n, axis=1)
        up = np.flatnonzero((area > 1) & (n[:, 2] > .7*area))
        for i in up[np.argsort(area[up])[-2:]]:
            x, y, _ = own[i].mean(0); top = own[i][:, 2].max()+200
            expected = visual_top(triangles, x, y, top)
            r = c.command('server', 'trace', px=float(x), py=float(y), pz=float(top), ex=float(x), ey=float(y), ez=float(top-1200))['data']
            hit = r['end'][2]
            if r['startSolid'] or not 0 < r['fraction'] < 1 or abs(hit-expected) > TOLERANCE:
                raise ValueError(f"Collision does not match restored surface at {prop['index']}: visual {expected:.1f}, native {hit:.1f}")
            contacts.append(dict(index=prop['index'], model=prop['model'], visual_z=expected, native_z=hit, trace=r))
    if len({c['index'] for c in contacts}) < 10:
        raise ValueError('Too few landing pad contacts were exercised')
    report = dict(bsp_sha256=sha, material_pack_sha256=pack, mounted_payload_verified=True, mode=mode,
                  teams=teams, contacts=contacts, tolerance=TOLERANCE,
                  postmatch_lobby=False, stock_map_reload=False, firing_reload=False)
    (out/'runtime-validation.json').write_text(json.dumps(report, indent=2))
    c.command('ui', 'console', command='script SetGameState( eGameState.Postmatch )')
    deadline = time.monotonic()+90
    while time.monotonic() < deadline:
        state = c.request('/status')
        if not state['game_running']:
            raise RuntimeError('Game exited after match')
        if state['contexts'].get('client', {}).get('level') == 'mp_lobby':
            break
        time.sleep(1)
    else:
        raise TimeoutError('Postmatch did not return to lobby')
    report['postmatch_lobby'] = True
    state = c.load('mp_coliseum', 'ps', 180)
    if not state['contexts']['client']['alive']:
        raise RuntimeError('Stock reload failed')
    report['stock_map_reload'] = True
    c.load('mp_apex_firing_range', 'ps', 180)
    mounted_bsp(c, 'firing-range'); mounted_material_pack(c, 'firing-range')
    report['firing_reload'] = True
    report['logs'] = c.export_logs()
    if report['logs']['script_errors'] or report['logs']['native_crashes']:
        raise RuntimeError('Native errors')
    (out/'runtime-validation.json').write_text(json.dumps(report, indent=2))
    print('Passed', len(contacts), 'landing-pad surface contacts, both teams, postmatch lobby, stock reload and Firing Range reload', flush=True)


if __name__ == '__main__':
    run()
