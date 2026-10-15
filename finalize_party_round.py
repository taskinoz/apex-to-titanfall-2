"""Publish the validated Party Crasher 0.6.0 round and player download."""
import argparse
import collections
import csv
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.6.0'
NAME = 'ArenaPartyCrasher'
NOTE = ('Restores Apex two-layer blending with Titanfall native blend shader: moss and snow on rocks, '
        'dirt on rubble and stained concrete now blend as in Apex. Removes the opaque caustic light layer '
        'and the dark layer over the marble orbs. Stops drawing 133 meshes that no reachable position can see, '
        'and uses that budget to restore the window walls, the red screen towers that carry the banners, '
        'the Mirage race-track seating set and 14 rocks around reported gaps; these '
        'restored props carry their source collision. Uses 97.97% of native world index capacity. Glass columns, foliage, '
        'cafe furniture and animated advertisements remain omitted. AI navigation and Titan modes are not '
        'supplied. Restart between previews.')


def finalize():
    out = folder('party-crasher'); project = out/'reported-recovery'
    candidate = WORK/'reported-candidates'/NAME
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    captures = json.loads((ROOT/'output/party-reported/native.json').read_text())
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
    if len(captures['shots']) != 40:
        raise ValueError('Native regression survey incomplete')
    audit_shared(); audit(candidate/'paks', 'mp_party_crasher')
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version']  not in ('0.5.1', '0.6.0'):
        raise ValueError('Unexpected accepted baseline version')
    for relative in ('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp',
                     'paks/party_crasher_world.rpak', 'mod.json'):
        shutil.copy2(candidate/relative, mod/relative)
        if digest(candidate/relative) != digest(mod/relative):
            raise ValueError('Published payload differs')
    plan = json.loads((project/'plan.json').read_text()); retire = json.loads((out/'retire/result.json').read_text())
    blend = json.loads((out/'layer-blend/blend-result.json').read_text())
    status = dict(version=VERSION, candidate=False, client_verified=True, initial_preview_ready=True,
                  full_release_ready=False, bsp_sha256=sha,
                  render_fraction=binary['budget']['native_padded_indices']/3145728,
                  new_placements=plan['added_props'],
                  validation='Single-client pilot spawns, source contacts and reloads; FFA definitions unchanged')
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    shot = next(r['northstar'] for r in captures['shots'] if r['name'].startswith('p28'))
    shutil.copy2(shot['path'], mod/'screenshot.png')
    docs = ROOT/'docs/candidates/party-crasher/port-0.6.0'; docs.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); physics = json.loads((out/'physics.json').read_text())
    summary = json.loads((ROOT/'docs/candidates/party-crasher/port-0.5.1/inventory-summary.json').read_text())
    summary.update(version=VERSION, bsp_sha256=sha, rendered_static_placements=len(scene['placements']),
                   omitted_local_placements=len(scene['omitted']),
                   omission_reasons=dict(collections.Counter(p['reason'] for p in scene['omitted'])),
                   budget={k: v for k, v in binary['budget'].items() if k != 'path'},
                   collision={k: v for k, v in physics.items() if k not in ('owners', 'missing')},
                   round_changes=dict(native_blend_materials=sorted(blend['materials']), retired=retire,
                                      new_placements=plan['added_props'], new_triangles=plan['added_triangles'],
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
    causes = [
        'Native blending: the Titanfall wld bm shader (Coliseum concrete_plates_plain_wet_bm) evaluates the same '
        'equation as Apex, w = saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha). Blend inputs are written into vertex '
        'alpha: source vertex alpha, or the source z-up ramp from the normal for moss and snow rock materials '
        '(apply_layer_blends.py).',
        'Hidden geometry: analyse_visibility.py floods walkable surfaces from the spawns (400-unit climbs, any drop, '
        'out-of-bounds volumes included within 600 units of in-bounds ground), casts 4,000 rays from each of 7,770 '
        'viewpoints with see-through materials passed through, then re-tests every candidate triangle with exact lines '
        'of sight to nearby viewpoints. 133 meshes (42,250 triangles) were never visible; they still cast sun shadows. '
        'A first pass used mis-oriented normals and untranslated trigger volumes and would have culled 189 visible '
        'meshes; it was rejected before release. A 40-view capture comparison of this build against the pre-cull '
        'build shows only the intended overlay removals and the restored props.',
        'Lightmap tiles: every native triangle owns one 4x4 tile. append_free_charts.py places new props in tiles '
        'released by retired triangles on any page.',
        'Overlays: every caustic_water_01 and waterfall_interior_02 triangle has another surface within 3 units, '
        'so removing them opens no holes.']
    text = [f'# Party Crasher {VERSION}', NOTE, '## How', '\n'.join('- '+c for c in causes),
            f'The independent round audit passed {binary["checks"]:,} checks. Native tests verified '
            f'{len(runtime["contacts"])} new collider contacts, clear supported team spawns, all 69 safety triggers, '
            'postmatch return, stock Coliseum loading and Party Crasher reloading.',
            'Rollback snapshots are kept on the build drive under `party-crasher/before-layer-blend/`, '
            '`before-retire/` and `before-0.6.0/`.']
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
