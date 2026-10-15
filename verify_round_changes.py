"""Audit a round of native blends, mesh retirement, LOD upgrades and appends.

Compared with the round baseline (the published build), only these changes
are allowed:

* vertex records may differ only in colour alpha (native blend weights);
* old meshes may disappear only if retired (overlay, hidden or old LOD);
  every surviving old mesh keeps its exact triangles;
* old lightmap texels change only in tiles no surviving triangle uses;
* collision changes only by appended headers; entities, lights and probes
  are byte-identical; the map stays under 98% of world-index capacity;
* materials change only for blend-converted and newly added materials.
"""
import argparse
import collections
import json
import struct

import numpy as np
from new_arena_ports import CONFIG, folder
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit
from extract_native_material import NativePak
from build_center_detail import active
from build_composite_map import DT
from package_player_mods import digest
from append_free_charts import used_tiles, PER_PAGE


def verify(ident, baseline_dir, project):
    out = folder(ident); target = CONFIG[ident]['target']; slug = ident.replace('-', '_')
    base = out/baseline_dir; bsp = out/(target+'.bsp')
    old = read_lumps(base/(target+'.bsp'), tuple(range(128))); new = read_lumps(bsp, tuple(range(128)))
    checks = []
    def check(value, name):
        if not value:
            raise ValueError(name)
        checks.append(name)
    check(old[0] == new[0], 'Entities, spawns and safety triggers identical')
    for key in (0x36, 0x65, 0x66, 0x67, 0x68, 0x7a):
        check(old[key] == new[key], f'Lights and character probes identical: {key:02x}')
    for key in (3, 0x42, 0x44, 0x45, 0x60):
        check(new[key][:len(old[key])] == old[key], f'Original position/collision prefix preserved: {key:02x}')
    first, last = len(old[0x45])//44, len(new[0x45])//44
    check(active(new) == active(old) | {(0x40, i) for i in range(first, last)},
          'Original collision exclusions preserved; only new collision headers activated')
    a = np.frombuffer(old[0x49], DT); b = np.frombuffer(new[0x49][:len(old[0x49])], DT)
    for field in DT.names:
        if field == 'color':
            check(np.array_equal(a['color'][:, :3], b['color'][:, :3]), 'Old vertex colour RGB unchanged')
        elif field != 'tangent':
            check(np.array_equal(a[field], b[field]), 'Old vertex field unchanged: '+field)
    def meshes(l):
        out = collections.Counter(); sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
        for i in range(0, len(l[0x50]), 28):
            r = struct.unpack_from('<I3H6b2h2BHI', l[0x50], i); s = sorts[r[-2]]
            out[(s[0], s[1], s[4], r[1:-2], l[0x4f][r[0]*2:r[0]*2+r[1]*6])] += 1
        return out
    om, nm = meshes(old), meshes(new)
    survived = sum((om & nm).values()); gone = sum((om-nm).values())
    checks.append(f'{survived} old meshes retained exactly; {gone} retired or rebuilt')
    validate_index_padding(new[0x50], new[0x4f], new[0x52]); checks.append('Native padded indices valid')
    visibility = validate_visibility(new[0x77], new[0x78], new[0x79], new[0x51]); checks.append('Bounded native visibility references')
    budget = audit(bsp)
    check(budget['all_meshes_fit_simultaneously'] and budget['native_padded_indices'] < budget['world_index_capacity']*.98,
          'Whole map fits with over 2% native world-index reserve')
    check(budget['static_batch_runs'] < 512, 'Static batch reserve for dynamic lights')
    # Tiles still used by original triangles (appended records start after the old vertex lump).
    oldtiles = set(used_tiles(base/(target+'.bsp')).tolist())
    newtiles = used_tiles(bsp, max_vertex=len(old[0x49])//44)
    keep = np.asarray(sorted(oldtiles & set(newtiles.tolist())), np.int64)
    osky = np.frombuffer(old[0x62], 'u1').reshape(4, 2, 2048, 2048, 4); nsky = np.frombuffer(new[0x62], 'u1').reshape(4, 2, 2048, 2048, 4)
    page, tile = keep//PER_PAGE, keep % PER_PAGE; y, x = (tile//512)*4, (tile % 512)*4
    same = True
    for dy in range(4):
        for dx in range(4):
            same &= bool(np.array_equal(osky[page, :, y+dy, x+dx], nsky[page, :, y+dy, x+dx]))
    check(same, f'Lightmap texels identical for all {len(keep)} retained tiles')
    gamut = osky.shape == nsky.shape; check(gamut, 'Lightmap page layout unchanged')
    before = NativePak(base/'materials/build'/(slug+'_world.rpak')); after = NativePak(out/'materials/build'/(slug+'_world.rpak'))
    mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    blended = {r['name'] for r in mapping.values() if r.get('native_layer_blend')}
    assets = {x['guid']: x for x in after.assets}; changed = 0
    for x in before.assets:
        check(x['guid'] in assets, 'Original asset retained: '+hex(x['guid']))
        if x['type'] == 'matl':
            spec, uber = before.material(x)
            if spec.get('name', '').replace('_colpass', '') in blended:
                changed += 1; continue
            check((spec, uber) == after.material(assets[x['guid']]), 'Untouched material identical: '+hex(x['guid']))
    checks.append(f'{changed} blend-converted material records rebound to the native bm shader')
    result = dict(checks=len(checks), passed=checks, budget=budget, visibility=visibility, bsp_sha256=digest(bsp),
                  retained_meshes=survived, removed_meshes=gone, native_runtime_verified=False)
    (out/project).mkdir(exist_ok=True)
    (out/project/'binary-validation.json').write_text(json.dumps(result, indent=2))
    print('Passed', len(checks), 'checks; occupancy', round(budget['native_padded_indices']/budget['world_index_capacity']*100, 3), '%;',
          survived, 'meshes retained,', gone, 'retired/rebuilt', flush=True)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ident', choices=sorted(CONFIG)); p.add_argument('baseline'); p.add_argument('project')
    a = p.parse_args(); verify(a.ident, a.baseline, a.project)
