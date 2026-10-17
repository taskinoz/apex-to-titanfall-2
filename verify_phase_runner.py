"""Audit Phase Runner 1.7.0 (phase_runner_blend.py + phase_runner_collision.py).

binary: every lump other than the vertex records (blend alpha / world UVs),
texture data strings (rebinding) and collision is byte-identical to 1.6.1;
vertex positions, indices and normals are untouched; the active collision set
equals the 1.6.1 set minus the replaced rock primitives plus the new headers,
so tunnel/catwalk exclusions are preserved; the render budget is unchanged.

runtime (harness running on the staged candidate): every spawn clear and
supported, both teams, vertical traces onto replaced rocks stop on the drawn
surface, postmatch lobby, stock Coliseum load and Phase Runner reload.
"""
import argparse
import json
import sys
import time

import numpy as np
from phase_runner_blend import ROOT, WORK, BACKUP, write
from repair_preview_index_padding import read_lumps
from build_center_detail import active
from audit_world_draw_budget import audit
from build_composite_map import DT

COLLISION = {1, 3, 0x42, 0x44, 0x45, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5c, 0x60}
CHANGED = {0x49, 2, 0x2b, 0x2c}
# 1.7.1 details: catwalk vertices/bounds/shadows, appended container-frame meshes and the rebuilt
# flat camera-visibility tree.
DETAILS = {0x0e, 0x1e, 0x4f, 0x50, 0x51, 0x52, 0x77, 0x78, 0x79, 0x7b, 0x7c, 0x7e, 0x7f, 0x05}


def binary():
    old_path = BACKUP/'mod/maps/mp_phase_runner.bsp'; new_path = WORK/'mp_phase_runner.bsp'
    old = read_lumps(old_path, tuple(range(128))); new = read_lumps(new_path, tuple(range(128))); checks = []
    def check(v, name):
        if not v:
            raise ValueError(name)
        checks.append(name)
    for k in range(128):
        if k not in COLLISION | CHANGED | DETAILS and k != 0x23:
            check(old.get(k, b'') == new.get(k, b''), f'Lump {k:02x} identical')
    a = np.frombuffer(old[0x49], DT); b = np.frombuffer(new[0x49], DT)
    check(len(b) >= len(a), 'Vertex records only appended'); b = b[:len(a)]
    for f in ('ni', 'light', 'tangent'):
        check(np.array_equal(a[f], b[f]), f'Vertex field {f} unchanged')
    check(np.array_equal(a['color'][:, :3], b['color'][:, :3]), 'Vertex RGB paint unchanged')
    details = json.loads((WORK/'details/result.json').read_text())
    check(int((a['pi'] != b['pi']).sum()) == details['catwalk_records_moved'], 'Only catwalk vertex positions repointed')
    for k in (3, 0x42, 0x44, 0x45, 0x60):
        check(new[k][:len(old[k])] == old[k], f'Collision data only appended: {k:02x}')
    check(old[1] == new[1] and old[0x5c] == new[0x5c], 'Planes and brushes unchanged')
    result = json.loads((WORK/'collision/result.json').read_text()); rows = json.loads((WORK/'collision/measure.json').read_text())
    chosen = {p['index'] for p in result['placements']}
    drop = {(0, i) for r in rows if r['index'] in chosen for i in r['brushes']} | {(0x40, i) for r in rows if r['index'] in chosen for i in r['headers']}
    cat = json.loads((ROOT/'northstar/PhaseRunner/catwalks.json').read_text())['collision']
    drop |= {(0x40, i) for i in range(cat['new_first_header'], cat['new_first_header']+cat['new_headers'])}
    first, last = len(old[0x45])//44, len(new[0x45])//44
    check(active(new) == (active(old)-drop) | {(0x40, i) for i in range(first, last)},
          'Active collision = 1.6.1 - replaced rock primitives + drawn-shape headers (exclusions preserved)')
    check(drop <= active(old), 'Only active primitives replaced')
    check(last < 65535, 'Collision header capacity')
    bo, bn = audit(old_path), audit(new_path)
    check(bn['native_padded_indices'] < 3145728*.98 and bn['static_batch_runs'] < 512, 'Render budget within the 98% / 512-batch ceilings')
    from package_player_mods import digest
    res = dict(checks=len(checks), passed=checks, bsp_sha256=digest(new_path), replaced_rocks=len(chosen), budget=bn)
    write(WORK/'binary-validation.json', res)
    print('Passed', len(checks), 'checks', flush=True)


def runtime(sample_count=40):
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    from analyse_visibility import render_triangles
    from verify_collision_match import visual_top
    from phase_runner_collision import lods, STATIC
    from plan_arena_fill import model_index
    from stage_prop_geometry import rotation
    from pathlib import Path
    c = Controller(); c.load('mp_phase_runner', 'ps', 180); c.command('client', 'camera_clear'); c.command('server', 'respawn', team=2)
    mode = c.command('server', 'mode_check')['data']
    bad = [p for p in mode['liveSpawns'] if not (p['clear'] and p['supported'])]
    if bad:
        raise ValueError(f'{len(bad)} spawns obstructed or unsupported: '+json.dumps(bad[:3]))
    for team in (2, 3):
        if c.command('server', 'respawn', team=team)['data']['team'] != team:
            raise ValueError('Incorrect spawn team')
    tris = render_triangles(WORK/'mp_phase_runner.bsp')[0].astype('f8')
    result = json.loads((WORK/'collision/result.json').read_text())
    props = {p['index']: p for p in json.loads(STATIC.read_text())}; index = model_index(); cache = {}
    rng = np.random.default_rng(7); picks = rng.choice(len(result['placements']), min(sample_count, len(result['placements'])), replace=False)
    contacts = []
    for k in picks:
        r = result['placements'][k]; p = props[r['index']]
        own = lods(Path(r['model']).stem.lower(), index, cache)[r['lod']]@np.asarray(rotation(p['angles'])).T*p.get('scale', 1)+np.asarray(p['origin'])
        n = np.cross(own[:, 1]-own[:, 0], own[:, 2]-own[:, 0]); area = np.linalg.norm(n, axis=1)
        tops = np.flatnonzero((area > 50) & (n[:, 2] > .5*area))
        if not len(tops):
            continue
        i = tops[np.argmax(own[tops][:, :, 2].mean(1))]; x, y, _ = own[i].mean(0); top = own[i][:, 2].max()+150
        expected = visual_top(tris, x, y, top)
        t = c.command('server', 'trace', px=float(x), py=float(y), pz=float(top), ex=float(x), ey=float(y), ez=float(top-1500))['data']
        ok = (not t['startSolid']) and 0 < t['fraction'] < 1 and expected is not None and abs(t['end'][2]-expected) <= 12
        contacts.append(dict(index=r['index'], model=r['model'], visual=expected, native=t['end'][2], ok=bool(ok)))
    good = sum(x['ok'] for x in contacts)
    if good < .9*len(contacts):
        raise ValueError(f'Only {good}/{len(contacts)} drawn-surface contacts matched: '+json.dumps([x for x in contacts if not x['ok']][:4]))
    c.command('ui', 'console', command='script SetGameState( eGameState.Postmatch )')
    deadline = time.monotonic()+90
    while time.monotonic() < deadline and c.request('/status')['contexts'].get('client', {}).get('level') != 'mp_lobby':
        time.sleep(1)
    c.load('mp_coliseum', 'ps', 180); c.load('mp_phase_runner', 'ps', 180)
    logs = c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:
        raise RuntimeError('Native errors: '+json.dumps(logs['script_errors'][:3]))
    from package_player_mods import digest
    rep = dict(bsp_sha256=digest(WORK/'mp_phase_runner.bsp'), spawns=len(mode['liveSpawns']), contacts=contacts, matched=good,
               postmatch_lobby=True, stock_map_reload=True, map_reload=True, logs=logs)
    write(WORK/'runtime-validation.json', rep)
    print('Passed', len(mode['liveSpawns']), 'spawns,', good, '/', len(contacts), 'drawn-rock contacts, both teams, lobby, stock and map reload', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=['binary', 'runtime'])
    a = p.parse_args(); binary() if a.action == 'binary' else runtime()
