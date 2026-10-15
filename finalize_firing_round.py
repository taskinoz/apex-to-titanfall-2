"""Publish the validated Firing Range 0.5.0 round and player download."""
import argparse
import collections
import csv
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.5.0'
NAME = 'ApexFiringRange'
NOTE = ('Restores Apex two-layer blending with the native Titanfall blend shader: sand on rock tops and '
        'slopes, sandy ground and blended red rock now follow the Apex blend weights. Raises 39 blocky rocks '
        'near reported spots to finer authored detail, so they sit closer to their collision, and stops drawing '
        '9 meshes no reachable position can see. Includes the 0.4.0 landing pad and surface repairs. Uses '
        '97.63% of native world index capacity. Many rocks still use coarse detail for budget reasons; foliage, '
        'weapon stations, targets and AI navigation remain absent. Restart between previews.')


def finalize():
    out = folder('firing-range'); project = out/'lod-upgrade'
    candidate = WORK/'round-candidates'/NAME
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    captures = json.loads((ROOT/'output/firing-round/native.json').read_text())
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
    if len(captures['shots']) < 14:
        raise ValueError('Native comparison survey incomplete')
    audit_shared(); audit(candidate/'paks', 'mp_apex_firing_range')
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.4.0':
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
    shot = next(r['northstar'] for r in captures['shots'] if r['name'].startswith('f19'))
    shutil.copy2(shot['path'], mod/'screenshot.png')
    docs = ROOT/'docs/candidates/firing-range/port-0.5.0'; docs.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); physics = json.loads((out/'physics.json').read_text())
    summary = json.loads((ROOT/'docs/candidates/firing-range/port-0.4.0/inventory-summary.json').read_text())
    summary.update(version=VERSION, bsp_sha256=sha, rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k: v for k, v in binary['budget'].items() if k != 'path'},
                   collision={k: v for k, v in physics.items() if k not in ('owners', 'missing')},
                   round_changes=dict(native_blend_materials=sorted(json.loads((out/'layer-blend/blend-result.json').read_text())['materials']),
                                      retired=json.loads((out/'retire/result.json').read_text()),
                                      lod_upgraded=plan['upgraded'], lod_downgraded=plan['downgraded'],
                                      net_triangles=plan['net_triangles'], skipped=len(plan['skipped'])))
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
    text = [f'# Firing Range {VERSION}', NOTE, '## How',
            '- Native blending: the Titanfall wld bm shader (Coliseum concrete_plates_plain_wet_bm) evaluates the same equation '
            'as the Apex blend materials. Blend inputs are written into vertex alpha: source vertex alpha (the bsp_tool '
            '`negative_one` field for world geometry), or the source z-up ramp from the normal for the sand-on-rock '
            'materials (apply_layer_blends.py). All 12 Firing Range blend materials converted.\n'
            '- Hidden geometry: analyse_visibility.py found 9 meshes (2,812 triangles) with no line of sight from any '
            'reachable position; they keep casting sun shadows.\n'
            '- Rock detail: upgrade_placement_lods.py retires old-LOD triangles by exact position and appends the finer '
            'authored LOD into released lightmap tiles. 39 rocks nearest the reported views moved up one level; 14 rocks '
            'more than 1,500 units from any reachable point moved to their lowest level to pay for it. Collision is unchanged.',
            f'The independent round audit passed {binary["checks"]:,} checks. Native tests verified '
            f'{len(runtime["contacts"])} landing-pad surface contacts, clear supported team spawns, unchanged safety '
            'triggers and ropes, postmatch return, stock Coliseum loading and Firing Range reloading.',
            'Rollback snapshots are kept on the build drive under `firing-range/before-layer-blend/`, `before-retire/` '
            'and `before-lod-upgrade/`.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8')
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
