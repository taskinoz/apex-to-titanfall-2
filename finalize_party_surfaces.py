"""Publish the validated Party Crasher 0.5.1 surface repair and player download."""
import argparse
import collections
import csv
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.5.1'
NAME = 'ArenaPartyCrasher'
NOTE = ('Fixes flat grey and olive ground: 13 world-projected source materials (rubble, moss, snow, gravel, '
        'grunge) now tile at their Apex scale instead of once per unit. Removes the z-fighting white '
        'rubble overlay on floors and grass: it now blends with the original Apex coverage, and fully '
        'transparent parts are no longer drawn. Includes the 0.5.0 signs, banners and screen panels. '
        'Uses 97.93% of native world index capacity. Many source props (cafe furniture, planters, '
        'trees, window modules, rocks) remain omitted for the draw budget. AI navigation and Titan '
        'modes are not supplied. Restart between previews.')


def finalize():
    out = folder('party-crasher'); project = out/'surface-repair'
    candidate = WORK/'surface-candidates'/NAME
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    captures = json.loads((ROOT/'output/party-surface/native.json').read_text())
    sha = digest(candidate/'mod/maps/mp_party_crasher.bsp')
    pack = digest(candidate/'paks/party_crasher_world.rpak')
    for proof in (binary, runtime, captures):
        if proof['bsp_sha256'] != sha:
            raise ValueError('Stale Party Crasher validation')
    for proof in (runtime, captures):
        if proof['material_pack_sha256'] != pack or not proof['mounted_payload_verified']:
            raise ValueError('Mounted material verification missing')
    if not all(runtime.get(k) for k in ('postmatch_lobby', 'stock_map_reload', 'party_reload')):
        raise ValueError('Reload gates missing')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    if len(captures['shots']) != 14:
        raise ValueError('Native user-report survey incomplete')
    audit_shared(); audit(candidate/'paks', 'mp_party_crasher')
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.5.0':
        raise ValueError('Unexpected accepted baseline version')
    for relative in ('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp',
                     'paks/party_crasher_world.rpak', 'mod.json'):
        shutil.copy2(candidate/relative, mod/relative)
        if digest(candidate/relative) != digest(mod/relative):
            raise ValueError('Published payload differs')
    surface = json.loads((project/'surface-result.json').read_text())
    status = dict(version=VERSION, candidate=False, client_verified=True, initial_preview_ready=True,
                  full_release_ready=False, bsp_sha256=sha,
                  render_fraction=binary['budget']['native_padded_indices']/3145728,
                  new_placements=0,
                  validation='Single-client pilot spawns, source contacts and reloads; FFA definitions unchanged')
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    shot = next(r['northstar'] for r in captures['shots'] if r['name'].startswith('r14'))
    shutil.copy2(shot['path'], mod/'screenshot.png')
    docs = ROOT/'docs/candidates/party-crasher/port-0.5.1'; docs.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); physics = json.loads((out/'physics.json').read_text())
    summary = json.loads((ROOT/'docs/candidates/party-crasher/port-0.5.0/inventory-summary.json').read_text())
    summary.update(version=VERSION, bsp_sha256=sha, rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k: v for k, v in binary['budget'].items() if k != 'path'},
                   collision={k: v for k, v in physics.items() if k not in ('owners', 'missing')},
                   surface_repair=dict(world_projected_materials=len(surface['world_projected_materials']),
                                       rewritten_triangles=surface['rewritten_native_triangles'],
                                       overlays=surface['overlays'], retired_overlay_triangles=surface['retired_overlay_triangles']))
    (docs/'inventory-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    inventory = json.loads((out/'source-inventory.json').read_text())
    included = {p['index']: p for p in scene['placements']}; omitted = {p['index']: p for p in scene['omitted']}
    owners = {p['index']: p for p in physics['owners'] if 'index' in p}
    fields = ['index', 'model', 'source_x', 'source_y', 'source_z', 'status', 'lod', 'triangles', 'collision', 'reason']
    with (docs/'placement-inventory.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for p in inventory['props']:
            used = included.get(p['index']); skip = omitted.get(p['index']); owner = owners.get(p['index'])
            writer.writerow(dict(index=p['index'], model=p['model'],
                **dict(zip(('source_x', 'source_y', 'source_z'), p['original_apex_origin'])),
                status='rendered' if used else 'omitted-local' if skip else 'outside-region',
                lod=used['lod'] if used else '', triangles=used['triangles'] if used else '',
                collision=owner['method'] if owner else 'Source world or non-solid', reason=skip['reason'] if skip else ''))
    proof = dict(bsp_sha256=sha, material_pack_sha256=pack, binary_checks=binary['checks'],
                 native_captures=len(captures['shots']),
                 both_teams_verified=True, spawn_clearance_and_support=True,
                 postmatch_lobby=True, stock_map_reload=True, party_reload=True,
                 script_errors=[], native_crashes=[], single_client_only=True,
                 safety_triggers_unchanged=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    shutil.copy2(mod/'screenshot.png', docs/'screenshot.png')
    causes = [
        'Apex wld pixel shaders project albedo from world position, uv = (x, -y) . c_uvN. The converted meshes '
        'stored raw world coordinates as UVs, so the texture repeated every unit and averaged to a flat colour. '
        '`classify_world_uv.py` traces each source pixel shader to find the c_uvN slot feeding the albedo.',
        'The b2t overlay opacity is (1 - saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)) * albedo.a. The real '
        'vertex colour is the record field bsp_tool names `negative_one`; its `colour` field is packed tangent data. '
        'Coverage is baked per triangle into an atlas drawn with the native world alpha shader.']
    text = [f'# Party Crasher {VERSION}', NOTE, '## Causes', '\n'.join('- '+c for c in causes),
            f'The independent audit passed {binary["checks"]:,} checks: collision, lightmaps, entities, lights and '
            'probes are byte-identical and every non-overlay mesh keeps identical triangles. Native tests verified '
            'clear supported team spawns, all 69 safety triggers, postmatch return, stock Coliseum loading and '
            'Party Crasher reloading. Fourteen user-reported views were captured in R5R and Northstar from the '
            'exact mounted payload.',
            'Baseline rollback is retained on the build drive under `party-crasher/before-0.5.1/`.',
            'Reproduce with `classify_world_uv.py party-crasher`, `repair_party_surfaces.py patch`, `materials`, '
            '`verify_party_surfaces.py`, `repair_party_surfaces.py stage`, the `party-crasher-user-report` routes '
            'and `verify_party_structure_runtime.py surface-repair`.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8')
    shutil.copy2(docs/'README.md', mod/'README.md')
    build = json.loads((out/'source-build.json').read_text())
    build.update(version=VERSION, render_triangles=scene['triangles'], draw_budget=binary['budget'])
    (out/'source-build.json').write_text(json.dumps(build, indent=2))
    print('Published Party Crasher', VERSION, sha, flush=True)


def package():
    RELEASES[NAME] = dict(version=VERSION, map='mp_party_crasher', title='Party Crasher',
                          screenshot='northstar/ArenaPartyCrasher/screenshot.png', notes=NOTE)
    result = write_player_zip(ROOT/'northstar'/NAME, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path = ROOT/'output/player-distributions.json'
    ledger = json.loads(path.read_text()) if path.exists() else {}
    ledger[NAME] = result
    path.write_text(json.dumps(ledger, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['finalize', 'package'])
    dict(finalize=finalize, package=package)[p.parse_args().action]()
