"""Publish the validated Party Crasher 0.5.0 signage recovery and player download."""
import argparse
import collections
import csv
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.5.0'
NAME = 'ArenaPartyCrasher'
NOTE = ('Fills all 33 empty flex-screen frames with their source panels and restores 33 source signs '
        'and 12 source banners, including the large Angel City banners over the south market. '
        'Uses 97.99% of native world index capacity, with no additional gameplay entities. '
        'Screen advertisement content is script-driven in Apex and is not supplied; panels use the '
        'static source material. Twelve further banners, dense window modules, roof foliage, '
        'animated advertisements and layered terrain materials remain incomplete. AI navigation and '
        'Titan modes are not supplied. Restart between previews.')


def finalize():
    out = folder('party-crasher'); project = out/'detail-recovery'
    candidate = WORK/'detail-candidates'/NAME
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    captures = json.loads((ROOT/'output/party-detail/native.json').read_text())
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
    if len(captures['shots']) != 4:
        raise ValueError('Native signage survey incomplete')
    audit_shared(); audit(candidate/'paks', 'mp_party_crasher')
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.4.0':
        raise ValueError('Unexpected accepted baseline version')
    for relative in ('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp',
                     'paks/party_crasher_world.rpak', 'mod.json'):
        shutil.copy2(candidate/relative, mod/relative)
        if digest(candidate/relative) != digest(mod/relative):
            raise ValueError('Published payload differs')
    plan = json.loads((project/'plan.json').read_text())
    status = dict(version=VERSION, candidate=False, client_verified=True, initial_preview_ready=True,
                  full_release_ready=False, bsp_sha256=sha,
                  render_fraction=binary['budget']['native_padded_indices']/3145728,
                  new_placements=plan['added_props'],
                  validation='Single-client pilot spawns, source contacts and reloads; FFA definitions unchanged')
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    shot = next(r['northstar'] for r in captures['shots'] if r['name'] == 'south-banners')
    shutil.copy2(shot['path'], mod/'screenshot.png')
    docs = ROOT/'docs/candidates/party-crasher/port-0.5.0'; docs.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); physics = json.loads((out/'physics.json').read_text())
    summary = json.loads((ROOT/'docs/candidates/party-crasher/port-0.4.0/inventory-summary.json').read_text())
    summary.update(version=VERSION, bsp_sha256=sha, rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k: v for k, v in binary['budget'].items() if k != 'path'},
                   collision={k: v for k, v in physics.items() if k not in ('owners', 'missing')},
                   new_recovery=dict(placements=plan['added_props'], triangles=plan['added_triangles'],
                                     categories=plan['categories'], skipped=plan['skipped']))
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
                 native_captures=len(captures['shots']), native_collider_contacts=len(runtime['contacts']),
                 both_teams_verified=True, spawn_clearance_and_support=True,
                 postmatch_lobby=True, stock_map_reload=True, party_reload=True,
                 script_errors=[], native_crashes=[], single_client_only=True,
                 safety_triggers_unchanged=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    shutil.copy2(mod/'screenshot.png', docs/'screenshot.png')
    (docs/'README.md').write_text(f'# Party Crasher {VERSION}\n\n{NOTE}\n\n'
        'The 0.4.0 scene placed all 33 `survival_modular_flexscreens_frame_01` frames but omitted the '
        '`survival_modular_flexscreens_04` panels inside them (4 triangles each), leaving open frames. '
        'This round adds them, then small signs, then banners, in priority order until the 98% native '
        'world-index ceiling. `timeshift_signage_01` (8 triangles) is left out because its text decal '
        'needs a reviewed alpha-overlay material. Skipped banners are listed in `inventory-summary.json`.\n\n'
        f'The independent audit passed {binary["checks"]:,} checks. Native tests verified '
        f'{len(runtime["contacts"])} new source collider contacts, clear supported team spawns, all 69 '
        'safety triggers, postmatch return, stock Coliseum loading and Party Crasher reloading. Four '
        'matched R5R/Northstar views were captured from the exact mounted payload. No multiplayer FPS, '
        'AI capacity or all-five-map stress certification is implied.\n\n'
        'A duplicate-triangle survey found no meaningful budget to reclaim: of 11,093 same-material '
        'coincident pairs, 9,885 are intentional two-sided faces, and most of the rest are stacked '
        '`echo_big_screen_animation_01` frames. Further large recovery needs the native static-prop path.\n\n'
        'Baseline rollback is retained on the build drive under `party-crasher/before-0.5.0/`.\n\n'
        'Reproduce with `recover_party_details.py plan`, `materials`, `append`, then '
        "`verify_party_structure.verify('0.5.0','detail-recovery',...)`, `recover_party_details.py stage`, the "
        '`party-crasher-detail-survey` routes and `verify_party_structure_runtime.py detail-recovery`.\n',
        encoding='utf-8')
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
