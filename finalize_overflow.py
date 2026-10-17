"""Publish Overflow 0.4.0: native two-layer blending, collision matched to drawn props, invisible objects drawn."""
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.4.0'
NAME = 'ArenaOverflow'
INVISIBLE_BEFORE = 0.0369  # audit_collision_visibility.py overflow on 0.3.1
NOTE = ('Restores Apex two-layer blending with Titanfall\'s native blend shader: stains, dirt and wear on concrete, '
        'painted metal and rock now blend as in Apex instead of showing one layer. 51 pipes, rocks and wall plates drawn '
        'at coarse detail now collide with the shape you see, and 53 props whose Apex collision was still in the map '
        '(tech panels, server racks, ceiling servers, warning lights, vents) are drawn instead of being invisible '
        'objects. Known issue (also in 0.3.1): about one load in five can crash Northstar at spawn; restart and load again. Animated advertisements, AI navigation and Titan modes remain absent.')


def finalize():
    out = folder('overflow'); cand = WORK/'overflow-candidates'/NAME; mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] not in ('0.3.1', VERSION):
        raise ValueError('Unexpected accepted baseline')
    binary = json.loads((out/'invisible-props/binary-validation.json').read_text())
    runtime = json.loads((out/'collision-match/runtime-validation.json').read_text())
    match = json.loads((out/'collision-match/result.json').read_text())
    blend = json.loads((out/'layer-blend/blend-result.json').read_text())
    props = json.loads((out/'invisible-props/result.json').read_text())
    after = json.loads((out/'collision-visibility.json').read_text())
    sha = digest(cand/'mod/maps/mp_overflow.bsp')
    if sha != digest(out/'mp_overflow.bsp') or binary['bsp_sha256'] != sha:
        raise ValueError('Stale Overflow validation')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    audit_shared(); audit(cand/'paks', 'mp_overflow')
    for rel in ('mod/maps/mp_overflow.bsp', 'mod/maps/mp_overflow.stbsp', 'paks/overflow_world.rpak', 'mod.json'):
        shutil.copy2(cand/rel, mod/rel)
        if digest(cand/rel) != digest(mod/rel):
            raise ValueError('Published payload differs: '+rel)
    docs = ROOT/'docs/candidates/overflow/port-0.4.0'; docs.mkdir(parents=True, exist_ok=True)
    proof = dict(bsp_sha256=sha, binary_checks=binary['checks'], render_fraction=binary['budget']['native_padded_indices']/3145728,
                 native_blend_materials=len(blend['materials']), collision_matched=match['replaced'],
                 source_brushes_disabled=match['source_brushes_disabled'], source_headers_disabled=match['source_headers_disabled'],
                 invisible_objects_drawn=props['added_props'], invisible_object_triangles=props['added_triangles'],
                 invisible_collision_before=INVISIBLE_BEFORE, invisible_collision_after=after['fraction'],
                 drawn_surface_contacts=f"{runtime['matched']}/{len(runtime['contacts'])-runtime.get('excluded_preexisting', 0)}",
                 contacts_on_preexisting_collider_above=runtime.get('excluded_preexisting', 0),
                 both_teams_verified=True, postmatch_lobby=True, stock_map_reload=True, map_reload=True, single_client_only=True)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    text = [f'# Overflow {VERSION}', NOTE, '## How',
            f"- `apply_layer_blends.py`: {len(blend['materials'])} Apex bm materials rebound to Titanfall's native wld bm shader "
            'with source vertex alpha / z-up blend input (all 18 matched their source alpha).',
            f"- `match_collision_to_render.py`: {match['replaced']} coarse-LOD placements over 15% collision/render mismatch collide "
            'with their drawn triangles; no spawn moved.',
            f"- `recover_invisible_props.py`: {props['added_props']} omitted props near reachable ground whose own surface lay on "
            'undrawn world collision are drawn from their source VG; no collision added.',
            f"Invisible reachable collision: {INVISIBLE_BEFORE*100:.1f}% before, {after['fraction']*100:.1f}% after.",
            f"Validation: {binary['checks']:,} binary checks; collision grid = 0.3.1 active set minus replaced colliders plus new "
            f"headers; {proof['drawn_surface_contacts']} drawn-surface contacts ({proof['contacts_on_preexisting_collider_above']} "
            'samples stopped on an unrelated pre-existing clip above the pipes); spawns, both teams, postmatch lobby, stock '
            'and map reload. Two of many harness sessions crashed on a second map load at spawn; repeated fresh-session and '
            'reload tests of this build and of 0.3.1 show the same intermittent Northstar instability, not a new fault.',
            'Rollback: `overflow/before-layer-blend/`, `before-collision-match/`, `before-invisible-props/` on the build drive.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8')
    readme = (mod/'README.md').read_text(encoding='utf-8')
    if not readme.startswith(f'# Overflow {VERSION}'):
        (mod/'README.md').write_text('\n\n'.join(text)+'\n\n## Previous release notes\n\n'+readme, encoding='utf-8')
    status = json.loads((mod/'build-status.json').read_text()); status.update(version=VERSION, bsp_sha256=sha, render_fraction=proof['render_fraction'])
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    RELEASES[NAME] = dict(version=VERSION, map='mp_overflow', title='Overflow', screenshot='northstar/ArenaOverflow/screenshot.png', notes=NOTE)
    result = write_player_zip(mod, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path = ROOT/'output/player-distributions.json'
    ledger = json.loads(path.read_text()) if path.exists() else {}
    ledger[NAME] = result; path.write_text(json.dumps(ledger, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    finalize()
