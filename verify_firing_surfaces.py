"""Independently audit the Firing Range 0.4.0 surface repair against its baseline.

Unlike a pure append, this repair intentionally edits old render records: it
retires replaced LODs, rebinds sand/rib UVs and filters the shadow stream. The
audit therefore pins everything else: entities, lights, probes, collision,
old lightmap charts and every untouched material.
"""
import collections
import json
from pathlib import Path

import numpy as np
from new_arena_ports import folder
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit
from extract_native_material import NativePak
from package_player_mods import digest
from build_center_detail import active

CHANGED_MATERIALS = {'sand_desert_02_bm_transparent'}


def verify():
    out = folder('firing-range')
    backup = out/'before-0.4.0'
    bsp = out/'mp_apex_firing_range.bsp'
    old = read_lumps(backup/'mp_apex_firing_range.bsp', tuple(range(128)))
    new = read_lumps(bsp, tuple(range(128)))
    checks = []
    def check(value, name):
        if not value:
            raise ValueError(name)
        checks.append(name)
    check(old[0] == new[0], 'All entities, spawns, ropes and safety triggers preserved')
    for key in (0x36, 0x65, 0x66, 0x67, 0x68, 0x7a):
        check(old[key] == new[key], f'World lights and character probes preserved: {key:02x}')
    # Only the stairs append their source IRPS collider; all else is unchanged.
    for key in (0x42, 0x44, 0x45, 0x60):
        check(new[key][:len(old[key])] == old[key], f'Original collision prefix preserved: {key:02x}')
    check(old[0x5c] == new[0x5c], 'Collision brushes unchanged')
    first, last = len(old[0x45])//44, len(new[0x45])//44
    check(active(new) == active(old) | {(0x40, i) for i in range(first, last)},
          'Original collision exclusions preserved; only new stair headers activated')
    check(last < 65000, 'Collision header reserve')
    for key in (2, 0x1e, 0x2b, 0x2c, 0x49, 0x52):
        check(len(new[key]) >= len(old[key]), f'Render stream extended, not truncated: {key:02x}')
    validate_index_padding(new[0x50], new[0x4f], new[0x52])
    checks.append('Native padded indices valid')
    visibility = validate_visibility(new[0x77], new[0x78], new[0x79], new[0x51])
    checks.append('All geometry covered by bounded native visibility references')
    budget = audit(bsp)
    check(budget['all_meshes_fit_simultaneously'] and
          budget['native_padded_indices'] < budget['world_index_capacity']*.98,
          'Whole map fits with over 2% native world-index reserve')
    check(budget['static_batch_runs'] < 512, 'Static batch reserve for dynamic lights')
    before = NativePak(backup/'materials/build/firing_range_world.rpak')
    after = NativePak(out/'materials/build/firing_range_world.rpak')
    assets = {a['guid']: a for a in after.assets}
    mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    changed = {mapping[n]['name'] for n in CHANGED_MATERIALS}
    for a in before.assets:
        check(a['guid'] in assets and a['type'] == assets[a['guid']]['type'],
              'Original asset retained: '+hex(a['guid']))
        if a['type'] == 'matl':
            spec, uber = before.material(a)
            if any(spec.get('name', '').endswith(c) for c in changed):
                continue
            check((spec, uber) == after.material(assets[a['guid']]),
                  'Untouched material bindings/uber buffer identical: '+hex(a['guid']))
    scene = json.loads((out/'scene.json').read_text())
    plan = json.loads((out/'surface-repair/plan.json').read_text())
    surface = json.loads((out/'surface-repair/surface-result.json').read_text())
    check(len({p['index'] for p in scene['placements']}) == len(scene['placements']),
          'Unique source placement ownership')
    check(sum(scene['materials'].values()) == scene['triangles'], 'Canonical material counts cover full scene')
    kinds = collections.Counter(p['recovery'] for p in plan['placements'])
    check(kinds['Stripless source VG author LOD (decoder repair)'] == 74, 'Complete landing-pad complex recovered')
    check(kinds['Source authored LOD1 replacement'] == 31, 'All reported bone/rock replacements applied')
    check(surface['retired_render_triangles'] == plan['retired_triangles'], 'Exactly the replaced LOD triangles retired')
    stairs = [p for p in plan['placements'] if 'sewer_staircase' in p['model']]
    check(len(stairs) == 8 and all(p['collision_triangles'] > 0 for p in stairs), 'All stairs carry source colliders')
    check(all(p['collision_triangles'] == 0 for p in plan['placements'] if p not in stairs),
          'No guessed or duplicate collider elsewhere')
    for p in plan['placements']:
        check(np.allclose(np.asarray(p['origin'])-[-32000, 7000, 28000], p['original_apex_origin'], atol=.01),
              'Exact recentered source origin: '+str(p['index']))
    # Old charts keep their tiles; only appended triangles receive new texels.
    old_sky = np.frombuffer(old[0x62], 'u1').reshape(4, 2, 2048, 2048, 4)
    new_sky = np.frombuffer(new[0x62], 'u1').reshape(4, 2, 2048, 2048, 4)
    count = json.loads((backup/'scene.json').read_text())['triangles']
    for page in range(4):
        tiles = max(0, min(262144, count-page*262144)); rows, cols = divmod(tiles, 512)
        check(np.array_equal(old_sky[page, :, :rows*4], new_sky[page, :, :rows*4]),
              'Old lightmap rows identical: '+str(page))
        if cols:
            check(np.array_equal(old_sky[page, :, rows*4:(rows+1)*4, :cols*4],
                                 new_sky[page, :, rows*4:(rows+1)*4, :cols*4]),
                  'Old partial lightmap row identical: '+str(page))
    result = dict(checks=len(checks), passed=checks, budget=budget, visibility=visibility,
                  bsp_sha256=digest(bsp), added_placements=plan['added_props'],
                  skipped=plan['skipped'], native_runtime_verified=False)
    (out/'surface-repair/binary-validation.json').write_text(json.dumps(result, indent=2))
    print('Passed', len(checks), 'checks; world occupancy',
          round(budget['native_padded_indices']/budget['world_index_capacity']*100, 3), '%')
    return result


if __name__ == '__main__':
    verify()
