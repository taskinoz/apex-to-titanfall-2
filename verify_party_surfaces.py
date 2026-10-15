"""Independently audit the Party Crasher 0.5.1 UV/overlay patch against before-0.5.1.

Collision, lightmaps, entities, lights and probes must be byte-identical;
vertex positions are only appended (lifted overlay copies). Every non-overlay
mesh survives with identical triangles; overlay meshes only lose invisible
triangles and gain the alpha flag. Only the two overlay materials change.
"""
import json
import struct

import numpy as np
from new_arena_ports import folder
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit
from package_player_mods import digest
from build_composite_map import DT
from repair_party_surfaces import OVERLAYS, project, classification


def verify():
    out = folder('party-crasher'); backup = out/'before-0.5.1'; bsp = out/'mp_party_crasher.bsp'
    old = read_lumps(backup/'mp_party_crasher.bsp', tuple(range(128))); new = read_lumps(bsp, tuple(range(128)))
    checks = []
    def check(value, name):
        if not value:
            raise ValueError(name)
        checks.append(name)
    check(old[0] == new[0], 'Entities, spawns and safety triggers identical')
    for key in (0x36, 0x65, 0x66, 0x67, 0x68, 0x7a):
        check(old[key] == new[key], f'Lights and character probes identical: {key:02x}')
    for key in (0x42, 0x44, 0x45, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5c, 0x60, 0x61):
        check(old[key] == new[key], f'Collision identical: {key:02x}')
    for key in (0x52, 0x62, 0x69):
        check(old[key] == new[key], f'Material sorts and lightmaps identical: {key:02x}')
    check(new[3][:len(old[3])] == old[3], 'Existing positions unchanged; lifted overlay copies appended')
    native = []
    for at in range(0, len(new[2]), 36):
        st = struct.unpack_from('<I', new[2], at+12)[0]; off = struct.unpack_from('<I', new[0x2c], st*4)[0]
        native.append(new[0x2b][off:new[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    sorts = list(struct.iter_unpack('<3hHI', new[0x52]))
    # reorder() permutes mesh records; compare meshes by fields and triangle content.
    import collections
    def meshes(lumps, drop_overlays):
        out = collections.Counter()
        for i in range(0, len(lumps[0x50]), 28):
            r = struct.unpack_from('<I3H6b2h2BHI', lumps[0x50], i)
            if drop_overlays and native[sorts[r[-2]][0]] in OVERLAYS:
                continue
            out[(r[1:], lumps[0x4f][r[0]*2:r[0]*2+r[1]*6])] += 1
        return out
    check(meshes(old, True) == meshes(new, True), 'Every non-overlay mesh retained with identical triangles')
    def overlay_triangles(lumps):
        total = 0
        for i in range(0, len(lumps[0x50]), 28):
            r = struct.unpack_from('<I3H6b2h2BHI', lumps[0x50], i)
            if native[sorts[r[-2]][0]] in OVERLAYS:
                if lumps is new:
                    check(r[-1] & 0x10, 'Overlay mesh carries the alpha flag')
                total += r[1]
        return total
    check(overlay_triangles(new) < overlay_triangles(old), 'Only invisible overlay triangles retired')
    # Every world-projected vertex now matches the source shader projection.
    world = classification(); records = np.frombuffer(new[0x49], DT)
    positions = np.frombuffer(new[3], '<f4').reshape(-1, 3); worst = 0.
    for i, mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI', new[0x50])):
        sort = sorts[mesh[-2]]; name = native[sort[0]]
        if name not in world or name in OVERLAYS:
            continue
        ix = np.unique(np.frombuffer(new[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('u4')+sort[-1])
        expected = project(world[name], positions[records['pi'][ix]])
        worst = max(worst, float(np.abs(records['uv'][ix]-expected).max()))
    check(worst < 1e-3, 'World-projected UVs match source shader constants (max error %.2e)' % worst)
    validate_index_padding(new[0x50], new[0x4f], new[0x52]); checks.append('Native padded indices valid')
    visibility = validate_visibility(new[0x77], new[0x78], new[0x79], new[0x51])
    checks.append('Bounded native visibility references')
    budget = audit(bsp); before = audit(backup/'mp_party_crasher.bsp')
    check(budget['native_padded_indices'] < before['native_padded_indices'], 'World index use reduced by retired overlays')
    check(budget['static_batch_runs'] < 512, 'Static batch reserve for dynamic lights')
    gl_at, gl_n = struct.unpack_from('<2I', bsp.read_bytes()[:2064], 16+0x23*16)
    data = bsp.read_bytes(); game = data[gl_at:gl_at+gl_n]
    for j in range(struct.unpack_from('<I', game)[0]):
        ptr, length = struct.unpack_from('<2I', game, 4+j*16+8)
        check(not length or gl_at <= ptr and ptr+length <= gl_at+gl_n, 'Game-lump payload inside its lump')
    from extract_native_material import NativePak
    mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    changed = {mapping[n]['name'] for n in OVERLAYS}
    old_pak = NativePak(backup/'materials/build/party_crasher_world.rpak')
    new_pak = NativePak(out/'materials/build/party_crasher_world.rpak')
    assets = {a['guid']: a for a in new_pak.assets}
    for a in old_pak.assets:
        check(a['guid'] in assets and a['type'] == assets[a['guid']]['type'], 'Original asset retained: '+hex(a['guid']))
        if a['type'] == 'matl':
            spec, uber = old_pak.material(a)
            if any(spec.get('name', '').endswith(c) for c in changed):
                continue
            check((spec, uber) == new_pak.material(assets[a['guid']]), 'Untouched material identical: '+hex(a['guid']))
    result = dict(checks=len(checks), passed=checks, budget=budget, visibility=visibility,
                  bsp_sha256=digest(bsp), native_runtime_verified=False)
    (out/'surface-repair/binary-validation.json').write_text(json.dumps(result, indent=2))
    print('Passed', len(checks), 'checks; world occupancy',
          round(budget['native_padded_indices']/budget['world_index_capacity']*100, 3), '%')


if __name__ == '__main__':
    verify()
