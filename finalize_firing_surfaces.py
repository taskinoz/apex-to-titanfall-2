"""Publish the validated Firing Range 0.4.0 surface repair and player download."""
import argparse
import collections
import csv
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.4.0'
NAME = 'ApexFiringRange'
NOTE = ('Restores the hidden central VTOL landing pad: 74 source pieces including the deck, tarmac, '
        'arm towers, pipes, supports, air units, runway lights and stairs, which now have their '
        'source collision. The transparent sand overlay no longer covers the metal floors, the giant '
        'bones and a reported large rock use smoother authored LOD1, and four zipline arms are restored. '
        'Uses 97.93% of native world index capacity with no added gameplay entities. Sand blending is '
        'a lower-resolution static approximation; eight further zipline arms, foliage, weapon stations, '
        'targets, animated advertisements and AI navigation remain absent. Restart between previews.')


def finalize():
    out = folder('firing-range'); project = out/'surface-repair'
    candidate = WORK/'surface-candidates'/NAME
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    captures = json.loads((ROOT/'output/firing-surface/native.json').read_text())
    sha = digest(candidate/'mod/maps/mp_apex_firing_range.bsp')
    pack = digest(candidate/'paks/firing_range_world.rpak')
    for proof in (binary, runtime, captures):
        if proof['bsp_sha256'] != sha:
            raise ValueError('Stale Firing Range validation')
    for proof in (runtime, captures):
        if proof['material_pack_sha256'] != pack or not proof['mounted_payload_verified']:
            raise ValueError('Mounted material verification missing')
    if not all(runtime.get(k) for k in ('postmatch_lobby', 'stock_map_reload', 'firing_reload')):
        raise ValueError('Reload gates missing')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    if len(captures['shots']) != 7:
        raise ValueError('Native comparison survey incomplete')
    audit_shared(); audit(candidate/'paks', 'mp_apex_firing_range')
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.3.1':
        raise ValueError('Unexpected accepted baseline version')
    for relative in ('mod/maps/mp_apex_firing_range.bsp', 'mod/maps/mp_apex_firing_range.stbsp',
                     'paks/firing_range_world.rpak', 'mod.json'):
        shutil.copy2(candidate/relative, mod/relative)
        if digest(candidate/relative) != digest(mod/relative):
            raise ValueError('Published payload differs')
    plan = json.loads((project/'plan.json').read_text())
    status = dict(version=VERSION, candidate=False, client_verified=True, initial_preview_ready=True,
                  full_release_ready=False, bsp_sha256=sha,
                  render_fraction=binary['budget']['native_padded_indices']/3145728,
                  new_placements=plan['added_props'],
                  validated_modes=['ps'],
                  validation='Single-client pilot spawns, landing-pad surface contacts and reloads; FFA definitions unchanged')
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    shot = next(r['northstar'] for r in captures['shots'] if r['name'] == 'pad-overview')
    shutil.copy2(shot['path'], mod/'screenshot.png')
    docs = ROOT/'docs/candidates/firing-range/port-0.4.0'; docs.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); physics = json.loads((out/'physics.json').read_text())
    summary = json.loads((ROOT/'docs/candidates/firing-range/port-0.3.0/inventory-summary.json').read_text())
    summary.update(version=VERSION, bsp_sha256=sha, rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k: v for k, v in binary['budget'].items() if k != 'path'},
                   collision={k: v for k, v in physics.items() if k not in ('owners', 'missing')},
                   new_recovery=dict(placements=plan['added_props'], triangles=plan['added_triangles'],
                                     retired_triangles=plan['retired_triangles'],
                                     groups=dict(collections.Counter(p['recovery'] for p in plan['placements'])),
                                     skipped=plan['skipped']))
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
                 native_captures=len(captures['shots']), native_surface_contacts=len(runtime['contacts']),
                 both_teams_verified=True, spawn_clearance_and_support=True,
                 postmatch_lobby=True, stock_map_reload=True, firing_reload=True,
                 script_errors=[], native_crashes=[], single_client_only=True,
                 safety_triggers_unchanged=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    shutil.copy2(mod/'screenshot.png', docs/'screenshot.png')
    (docs/'README.md').write_text(f'# Firing Range {VERSION}\n\n{NOTE}\n\n'
        '## What changed\n\n'
        '- **Landing pad.** 74 source placements around (1523, 2008, -700) were omitted in 0.3.0 as '
        '"invalid static triangle strips". They use direct triangle lists without a strip table, which '
        'the decoder now reads. Their deck, tarmac, pipes and supports already had source world collision. '
        'Native traces showed the eight sewer staircases had none, so their source IRPS colliders are appended.\n'
        '- **Sand overlay.** `sand_desert_02_bm_transparent` rendered as an opaque sheet over metal floors. '
        'It now uses the native world-alpha shader with coverage baked from the source shader equation '
        '`1 - saturate(5*mask - 5 + 6*vertexAlpha)` into a 2048 atlas. The atlas gives about 0.7 texels '
        'per unit, so blending is softer than the source.\n'
        '- **Bones and rock 1292.** Authored LOD1 replaces LOD2/LOD3. A proposed 8x base-UV scale for '
        '`rib_giant_*` was rejected: the source pixel shader applies `c_uv1RotScale` only to the detail '
        'normal, and the albedo is an unwrapped atlas.\n'
        '- **Zipline arms.** Four of twelve source arms fit under the 98% index ceiling; the rest are listed '
        'in `inventory-summary.json`.\n\n'
        f'The independent audit passed {binary["checks"]:,} checks. Native tests verified '
        f'{len(runtime["contacts"])} landing-pad surface contacts against the visible geometry, clear supported '
        'team spawns, unchanged safety triggers and ropes, postmatch return, stock Coliseum loading and '
        'Firing Range reloading. Seven matched R5R/Northstar views were captured from the exact mounted payload. '
        'Pilots vs Pilots was exercised; FFA registration and entities are unchanged from 0.3.1. '
        'No multiplayer FPS, AI or all-five-map stress certification is implied.\n\n'
        'Baseline rollback is retained on the build drive under `firing-range/before-0.4.0/`.\n\n'
        'Reproduce with `repair_firing_range_surfaces.py plan`, `patch`, `materials`, `append`, then '
        '`verify_firing_surfaces.py`, `stage_firing_surfaces.py`, the `firing-range-surface-repair` routes and '
        '`verify_firing_surfaces_runtime.py`. Set APEX_PORT_WORK to the owned build workspace.\n', encoding='utf-8')
    shutil.copy2(docs/'README.md', mod/'README.md')
    build = json.loads((out/'source-build.json').read_text())
    build.update(version=VERSION, render_triangles=scene['triangles'], draw_budget=binary['budget'])
    (out/'source-build.json').write_text(json.dumps(build, indent=2))
    print('Published Firing Range', VERSION, sha, flush=True)


def package():
    RELEASES[NAME] = dict(version=VERSION, map='mp_apex_firing_range', title='Firing Range',
                          screenshot='northstar/ApexFiringRange/screenshot.png', notes=NOTE)
    result = write_player_zip(ROOT/'northstar'/NAME, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path = ROOT/'output/player-distributions.json'
    ledger = json.loads(path.read_text()) if path.exists() else {}
    ledger[NAME] = result
    path.write_text(json.dumps(ledger, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['finalize', 'package'])
    dict(finalize=finalize, package=package)[p.parse_args().action]()
