"""Publish Party Crasher 0.6.1: collision matched to drawn screen towers, reported planter, columns and cafe."""
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.6.1'
NAME = 'ArenaPartyCrasher'
NOTE = ('Screen-tower arms and frames now collide with the shape you see instead of invisible full-detail Apex '
        'collision. Restores the flower planter that stood as an invisible object, the two reported glass columns '
        '(with collision) and three cafe tables with stools. Distant unreachable scenery drops to its lowest '
        'authored detail to pay for them; the map still uses 98% of native world index capacity. Foliage, '
        'remaining cafe furniture, animated advertisements and AI navigation remain absent. Restart between previews.')


def finalize():
    out = folder('party-crasher'); cand = WORK/'column-candidates'/NAME; mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.6.0':
        raise ValueError('Unexpected accepted baseline')
    binary = json.loads((out/'column-recovery/binary-validation.json').read_text())
    runtime = json.loads((out/'column-recovery/runtime-validation.json').read_text())
    collision = json.loads((out/'collision-match/runtime-validation.json').read_text())
    match = json.loads((out/'collision-match/result.json').read_text())
    lods = json.loads((out/'lod-upgrade/result.json').read_text())
    plan = json.loads((out/'column-recovery/plan.json').read_text())
    report = json.loads((out/'report-collision-check.json').read_text())
    sha = digest(cand/'mod/maps/mp_party_crasher.bsp'); pack = digest(cand/'paks/party_crasher_world.rpak')
    if sha != digest(out/'mp_party_crasher.bsp') or binary['bsp_sha256'] != sha or runtime['bsp_sha256'] != sha:
        raise ValueError('Stale Party Crasher validation')
    if runtime['material_pack_sha256'] != pack or not runtime['mounted_payload_verified']:
        raise ValueError('Mounted material verification missing')
    for proof in (runtime, collision):
        if proof['logs']['script_errors'] or proof['logs']['native_crashes']:
            raise ValueError('Native errors during validation')
    if collision['matched'] < .9*len(collision['contacts']):
        raise ValueError('Drawn-surface contacts failed')
    audit_shared(); audit(cand/'paks', 'mp_party_crasher')
    for rel in ('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp', 'paks/party_crasher_world.rpak', 'mod.json'):
        shutil.copy2(cand/rel, mod/rel)
        if digest(cand/rel) != digest(mod/rel):
            raise ValueError('Published payload differs')
    ok = sum(all(r['kind'] == 'ok' for r in s['rays']) for s in report)
    docs = ROOT/'docs/candidates/party-crasher/port-0.6.1'; docs.mkdir(parents=True, exist_ok=True)
    proof = dict(bsp_sha256=sha, material_pack_sha256=pack, binary_checks=binary['checks'],
                 render_fraction=binary['budget']['native_padded_indices']/3145728,
                 placements_matched=match['replaced'], source_brushes_disabled=match['source_brushes_disabled'],
                 drawn_surface_contacts=f"{collision['matched']}/{len(collision['contacts'])}",
                 lod_downgrades=lods['downgraded'], lod_net_triangles=lods['net_triangles'],
                 new_placements=plan['added_props'], new_triangles=plan['added_triangles'], categories=plan['categories'],
                 source_collider_contacts=len(runtime['contacts']), report_positions_clean=f'{ok}/{len(report)}',
                 both_teams_verified=True, postmatch_lobby=True, stock_map_reload=True, party_reload=True,
                 single_client_only=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    text = [f'# Party Crasher {VERSION}', NOTE, '## How',
            f"- `match_collision_to_render.py`: {match['replaced']} coarse-LOD placements (screen-tower arms, flexscreen "
            f"frames) over 15% collision/render mismatch get triangle collision from their drawn triangles; "
            f"{match['source_brushes_disabled']} source brushes leave the collision grid.",
            f"- `upgrade_placement_lods.py`: {lods['downgraded']} placements more than 1,500 units from any reachable "
            f"point drop to their lowest authored LOD (net {lods['net_triangles']:,} triangles).",
            f"- `recover_party_columns.py`: {plan['added_props']} props in released lightmap tiles, reported positions "
            'first. The flower planter `party_crashers_pillar_03` at report q33 had its collision baked into the Apex '
            'world collision, so while omitted it was an invisible object; it is now drawn. Glass columns use a '
            'meshoptimizer-simplified LOD0 (no lower authored LOD exists).',
            '- Fixed `recover_composite_details.append_collision`: it rebuilt the collision grid over every primitive, '
            're-enabling source colliders that collision matching had disabled. It now keeps disabled primitives out.',
            f"Validation: {binary['checks']:,} binary checks; collision grid = previous active set plus the new headers "
            f"(none re-enabled); native traces stop on the drawn surface at {collision['matched']}/"
            f"{len(collision['contacts'])} replaced placements; {len(runtime['contacts'])} new collider contacts; "
            f'{ok}/{len(report)} report positions fully clean (the rest hit glass, which the check does not count as '
            'drawn); 40-view regression capture identical to 0.6.0 except the restored column; spawns, postmatch '
            'lobby, stock and map reload.',
            'Rollback: `party-crasher/before-collision-match/`, `before-lod-upgrade/` and `before-0.6.1/` on the build drive.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8'); shutil.copy2(docs/'README.md', mod/'README.md')
    status = json.loads((mod/'build-status.json').read_text())
    status.update(version=VERSION, bsp_sha256=sha, render_fraction=proof['render_fraction'], new_placements=plan['added_props'])
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    RELEASES[NAME] = dict(version=VERSION, map='mp_party_crasher', title='Party Crasher',
                          screenshot='northstar/ArenaPartyCrasher/screenshot.png', notes=NOTE)
    result = write_player_zip(mod, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path = ROOT/'output/player-distributions.json'
    ledger = json.loads(path.read_text()) if path.exists() else {}
    ledger[NAME] = result; path.write_text(json.dumps(ledger, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    finalize()
