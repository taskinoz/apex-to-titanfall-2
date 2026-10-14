"""Independently audit the Party Crasher append against its immutable baseline."""
import collections
import json
import struct

import numpy as np
from new_arena_ports import folder
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit
from extract_native_material import NativePak
from build_center_detail import active
from package_player_mods import digest


def verify():
    out = folder('party-crasher')
    backup = out/'before-0.4.0'
    old = read_lumps(backup/'mp_party_crasher.bsp', tuple(range(128)))
    new = read_lumps(out/'mp_party_crasher.bsp', tuple(range(128)))
    checks = []
    def check(value, name):
        if not value:
            raise ValueError(name)
        checks.append(name)
    check(old[0]==new[0], 'All entities, spawns and safety triggers preserved')
    for key in (0x36,0x65,0x66,0x67,0x68,0x7a):
        check(old[key]==new[key], f'World lights and character probes preserved: {key:02x}')
    for key in (2,3,0x1e,0x2b,0x2c,0x42,0x44,0x45,0x49,0x4f,0x52,0x60,0x7c,0x7e,0x7f):
        check(new[key][:len(old[key])]==old[key],f'Original geometry/collision prefix preserved: {key:02x}')
    def meshes(lumps):
        return collections.Counter(lumps[0x50][i:i+28]+lumps[0x51][i//28*32:i//28*32+32]
                                   for i in range(0,len(lumps[0x50]),28))
    check(not (meshes(old)-meshes(new)), 'All old meshes, attribute references and bounds retained')
    first, last = len(old[0x45])//44, len(new[0x45])//44
    check(active(new)==active(old)|{(0x40,i) for i in range(first,last)},
          'Original collision exclusions preserved; only new headers activated')
    check(last<65000, 'Collision header reserve')
    validate_index_padding(new[0x50],new[0x4f],new[0x52])
    checks.append('Native padded indices valid')
    visibility = validate_visibility(new[0x77],new[0x78],new[0x79],new[0x51])
    checks.append('All geometry covered by bounded native visibility references')
    budget = audit(out/'mp_party_crasher.bsp')
    check(budget['all_meshes_fit_simultaneously'] and
          budget['native_padded_indices']<budget['world_index_capacity']*.98,
          'Whole map fits with over 2% native world-index reserve')
    check(budget['static_batch_runs']<512, 'Static batch reserve for dynamic lights')
    before = NativePak(backup/'materials/build/party_crasher_world.rpak')
    after = NativePak(out/'materials/build/party_crasher_world.rpak')
    assets = {a['guid']:a for a in after.assets}
    for a in before.assets:
        check(a['guid'] in assets and a['type']==assets[a['guid']]['type'],
              'Original asset retained: '+hex(a['guid']))
        if a['type']=='matl':
            check(before.material(a)==after.material(assets[a['guid']]),
                  'Original material/shader bindings/uber buffer identical: '+hex(a['guid']))
    scene = json.loads((out/'scene.json').read_text())
    plan = json.loads((out/'structure-recovery/plan.json').read_text())
    check(len({p['index'] for p in scene['placements']})==len(scene['placements']),
          'Unique source placement ownership')
    check(sum(scene['materials'].values())==scene['triangles'], 'Canonical material counts cover full scene')
    check(plan['categories']=={'facade':168,'roof-vent':42,'roof-solar':128,'edge-rock':42},
          'All approved facade/roof/boundary groups recovered')
    oldowners={p['index'] for p in json.loads((backup/'physics.json').read_text())['owners'] if 'index' in p}
    for p in plan['placements']:
        check(p['origin']==p['original_apex_origin'], 'Exact source origin: '+str(p['index']))
        if p['solid'] not in (2,6,7):
            check(p['collision_triangles']==0, 'Source non-solid preserved: '+str(p['index']))
        check(p['index'] not in oldowners, 'No duplicate source collider: '+str(p['index']))
    old_sky=np.frombuffer(old[0x62],'u1').reshape(4,2,2048,2048,4)
    new_sky=np.frombuffer(new[0x62],'u1').reshape(4,2,2048,2048,4)
    count=json.loads((backup/'scene.json').read_text())['triangles']
    for page in range(4):
        tiles=max(0,min(262144,count-page*262144));rows,cols=divmod(tiles,512)
        check(np.array_equal(old_sky[page,:,:rows*4],new_sky[page,:,:rows*4]),
              'Old lightmap rows identical: '+str(page))
        if cols:
            check(np.array_equal(old_sky[page,:,rows*4:(rows+1)*4,:cols*4],
                                 new_sky[page,:,rows*4:(rows+1)*4,:cols*4]),
                  'Old partial lightmap row identical: '+str(page))
    result=dict(checks=len(checks),passed=checks,budget=budget,visibility=visibility,
                bsp_sha256=digest(out/'mp_party_crasher.bsp'),added_placements=plan['added_props'],
                native_runtime_verified=False)
    (out/'structure-recovery/binary-validation.json').write_text(json.dumps(result,indent=2))
    print('Passed',len(checks),'checks; world occupancy',round(budget['native_padded_indices']/budget['world_index_capacity']*100,3),'%')
    return result


if __name__=='__main__':
    verify()
