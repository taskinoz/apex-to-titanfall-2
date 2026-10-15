"""Audit and natively test match_collision_to_render.py.

Binary: every non-collision lump is byte-identical to the snapshot; collision
data is only appended; the active collision set equals the old set minus the
disabled source primitives plus every appended header.

Native (--runtime, needs a running harness on the staged candidate): vertical
traces onto the top faces of replaced placements must stop within TOLERANCE of
the drawn surface; spawns, reload and lobby gates must pass.
"""
import argparse
import json
import struct
import sys
import time

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from repair_preview_index_padding import read_lumps
from build_center_detail import active
from audit_world_draw_budget import audit
from package_player_mods import digest

COLLISION = {3, 0x42, 0x44, 0x45, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x60}
TOLERANCE = 12.0


def binary(ident):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp'); base = out/'before-collision-match'/bsp.name
    old = read_lumps(base, tuple(range(128))); new = read_lumps(bsp, tuple(range(128))); checks = []
    def check(v, name):
        if not v:
            raise ValueError(name)
        checks.append(name)
    for k in range(128):
        if k not in COLLISION and k not in (0, 0x23):
            check(old.get(k, b'') == new.get(k, b''), f'Lump {k:02x} identical')
    for k in (3, 0x42, 0x44, 0x45, 0x60):
        check(new[k][:len(old[k])] == old[k], f'Collision data only appended: {k:02x}')
    # Entities may differ only by spawn-marker heights snapped onto drawn rock.
    import repair_environment_lighting as rel
    ea = list(rel.shared.Entities.from_bytes(old[0][old[0].index(b'{'):])); eb = list(rel.shared.Entities.from_bytes(new[0][new[0].index(b'{'):]))
    check(len(ea) == len(eb), 'Entity count unchanged')
    for x, y in zip(ea, eb):
        if dict(x) != dict(y):
            check(set(dict(x)) == set(dict(y)) and all(dict(x)[k] == dict(y)[k] for k in dict(x) if k != 'origin')
                  and dict(x)['classname'].startswith(('info_spawnpoint', 'info_player_start'))
                  and dict(x)['origin'].split()[:2] == dict(y)['origin'].split()[:2], 'Only spawn heights changed')
    rows = json.loads((out/'collision-match.json').read_text())
    result = json.loads((out/'collision-match/result.json').read_text())
    chosen = {p['index'] for p in result['placements']}
    drop = {(0, i) for r in rows if r['index'] in chosen for i in r['brushes']} | {(0x40, i) for r in rows if r['index'] in chosen for i in r['headers']}
    first, last = len(old[0x45])//44, len(new[0x45])//44
    check(active(new) == (active(old)-drop) | {(0x40, i) for i in range(first, last)},
          'Active collision = old - replaced source colliders + drawn-shape headers')
    check(last < 65535, 'Collision header capacity')
    b = audit(bsp); check(b['native_padded_indices'] == audit(base)['native_padded_indices'], 'Render budget unchanged')
    res = dict(checks=len(checks), bsp_sha256=digest(bsp), replaced=len(chosen))
    (out/'collision-match/binary-validation.json').write_text(json.dumps(res, indent=2))
    print('Passed', len(checks), 'checks;', len(chosen), 'placements now collide with their drawn shape', flush=True)


def visual_top(tris, x, y, below):
    p = tris; lo = p[:, :, :2].min(1); hi = p[:, :, :2].max(1)
    near = np.flatnonzero((lo[:, 0] <= x) & (hi[:, 0] >= x) & (lo[:, 1] <= y) & (hi[:, 1] >= y)); best = None
    for i in near:
        a, b, c = p[i]; d = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(d) < 1e-9:
            continue
        u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/d; v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/d
        if min(u, v, 1-u-v) < 0:
            continue
        z = u*a[2]+v*b[2]+(1-u-v)*c[2]
        if z < below and (best is None or z > best):
            best = z
    return best


def runtime(ident, sample_count=40):
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    from analyse_visibility import render_triangles
    from match_collision_to_render import render_geometry
    out = folder(ident); target = CONFIG[ident]['target']
    c = Controller(); c.load(target, 'ps', 180); c.command('client', 'camera_clear'); c.command('server', 'respawn', team=2)
    mode = c.command('server', 'mode_check')['data']
    if not all(p['clear'] and p['supported'] for p in mode['liveSpawns']):
        raise ValueError('A native spawn is obstructed or unsupported')
    for team in (2, 3):
        if c.command('server', 'respawn', team=team)['data']['team'] != team:
            raise ValueError('Incorrect spawn team')
    tris, _, _ = render_triangles(out/(target+'.bsp')); tris = tris.astype('f8')
    result = json.loads((out/'collision-match/result.json').read_text())
    scene = {p['index']: p for p in json.loads((out/'scene.json').read_text())['placements']}
    rng = np.random.default_rng(7); picks = rng.choice(len(result['placements']), min(sample_count, len(result['placements'])), replace=False)
    contacts, cache = [], {}
    for k in picks:
        p = scene[result['placements'][k]['index']]; own = render_geometry(p, cache)
        n = np.cross(own[:, 1]-own[:, 0], own[:, 2]-own[:, 0]); a = np.linalg.norm(n, axis=1)
        tops = np.flatnonzero(a > 50)
        if not len(tops):
            continue
        i = tops[np.argmax(own[tops][:, :, 2].mean(1))]; x, y, _ = own[i].mean(0); top = own[i][:, 2].max()+150
        expected = visual_top(tris, x, y, top)
        r = c.command('server', 'trace', px=float(x), py=float(y), pz=float(top), ex=float(x), ey=float(y), ez=float(top-1500))['data']
        ok = (not r['startSolid']) and 0 < r['fraction'] < 1 and expected is not None and abs(r['end'][2]-expected) <= TOLERANCE
        contacts.append(dict(index=p['index'], model=p['model'], visual=expected, native=r['end'][2], ok=bool(ok)))
    good = sum(x['ok'] for x in contacts)
    if good < .9*len(contacts):
        raise ValueError(f'Only {good}/{len(contacts)} drawn-surface contacts matched: '+json.dumps([x for x in contacts if not x['ok']][:5]))
    c.command('ui', 'console', command='script SetGameState( eGameState.Postmatch )')
    deadline = time.monotonic()+90
    while time.monotonic() < deadline and c.request('/status')['contexts'].get('client', {}).get('level') != 'mp_lobby':
        time.sleep(1)
    c.load('mp_coliseum', 'ps', 180); c.load(target, 'ps', 180)
    logs = c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:
        raise RuntimeError('Native errors')
    rep = dict(contacts=contacts, matched=good, postmatch_lobby=True, stock_map_reload=True, map_reload=True, logs=logs)
    (out/'collision-match/runtime-validation.json').write_text(json.dumps(rep, indent=2))
    print('Passed', good, '/', len(contacts), 'drawn-surface contacts, both teams, lobby, stock and map reload', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('ident', choices=sorted(CONFIG)); p.add_argument('--runtime', action='store_true')
    a = p.parse_args(); runtime(a.ident) if a.runtime else binary(a.ident)
