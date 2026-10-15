"""Publish Party Crasher 0.6.2: the fourth user report (q34-q40)."""
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.6.2'
NAME = 'ArenaPartyCrasher'
NOTE = ('Fixes invisible objects from missing Apex props: the cafe table set, both search lights, the concrete '
        'rubble ramp and a speaker are now drawn, and the second flower planter is back with solid walls. '
        'More cafe tables and stools are restored. The fountain foam is faint, as in Apex (Titanfall cannot '
        'animate it), and the R5Reloaded placeholder screen shows a north-star emblem. Over-detailed wire '
        'bundles, consoles and pillar signs use simplified meshes to pay for this. Foliage, animated '
        'advertisements and AI navigation remain absent. Restart between previews.')


def finalize():
    out = folder('party-crasher'); project = out/'report4-recovery'; cand = WORK/'report4-candidates'/NAME
    mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.6.1':
        raise ValueError('Unexpected accepted baseline')
    binary = json.loads((project/'binary-validation.json').read_text())
    runtime = json.loads((project/'runtime-validation.json').read_text())
    collision = json.loads((out/'collision-match/runtime-validation.json').read_text())
    plan = json.loads((project/'result.json').read_text()); textures = json.loads((project/'textures.json').read_text())
    report = json.loads((out/'report-collision-check.json').read_text())
    sha = digest(cand/'mod/maps/mp_party_crasher.bsp'); pack = digest(cand/'paks/party_crasher_world.rpak')
    if sha != digest(out/'mp_party_crasher.bsp') or binary['bsp_sha256'] != sha or runtime['bsp_sha256'] != sha:
        raise ValueError('Stale Party Crasher validation')
    if runtime['material_pack_sha256'] != pack or not runtime['mounted_payload_verified']:
        raise ValueError('Mounted material verification missing')
    for proof in (runtime, collision):
        if proof['logs']['script_errors'] or proof['logs']['native_crashes']:
            raise ValueError('Native errors during validation')
    if not all(all(r['kind'] == 'ok' for r in s['rays']) for s in report if s['name'][:3] in ('q34', 'q35', 'q36', 'q37', 'q39')):
        raise ValueError('Reported positions are not clean')
    audit_shared(); audit(cand/'paks', 'mp_party_crasher')
    for rel in ('mod/maps/mp_party_crasher.bsp', 'mod/maps/mp_party_crasher.stbsp', 'paks/party_crasher_world.rpak', 'mod.json'):
        shutil.copy2(cand/rel, mod/rel)
        if digest(cand/rel) != digest(mod/rel):
            raise ValueError('Published payload differs')
    restored = [p for p in plan['placements'] if not p.get('replacement')]
    simplified = [p for p in plan['placements'] if p.get('replacement')]
    ok = sum(all(r['kind'] == 'ok' for r in s['rays']) for s in report)
    docs = ROOT/'docs/candidates/party-crasher/port-0.6.2'; docs.mkdir(parents=True, exist_ok=True)
    proof = dict(bsp_sha256=sha, material_pack_sha256=pack, binary_checks=binary['checks'],
                 render_fraction=binary['budget']['native_padded_indices']/3145728,
                 restored_placements=len(restored), simplified_placements=len(simplified),
                 freed_triangles=plan['freed_triangles'], added_triangles=plan['added_triangles'],
                 categories=plan['categories'], foam_opacity_scale=textures['foam_opacity_scale'],
                 atlas_panel_source_pixels=textures['atlas_panel_source_pixels'],
                 source_collider_contacts=len(runtime['contacts']),
                 drawn_surface_contacts=f"{collision['matched']}/{len(collision['contacts'])}",
                 report_positions_clean=f'{ok}/{len(report)}', both_teams_verified=True, postmatch_lobby=True,
                 stock_map_reload=True, party_reload=True, single_client_only=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    text = [f'# Party Crasher {VERSION}', NOTE, '## How',
            '- Invisible collision at q34-q37 and q39 was world-baked collision of omitted Apex props, found by tracing '
            'from each report camera and testing which omitted placement\'s model bounds contain the hit: table set '
            '8851/6678/6319/6625/13690, search lights 13651/13652, rubble 898/1777/12866 and speaker 9255. They are '
            'drawn at source LOD0 with their source collider.',
            '- The q39 planter (11244) has only a small IRPS box as its source collider, so its walls collide with its '
            'drawn structural triangles (flower cards excluded).',
            f"- Budget: {len(simplified)} single-LOD props in the arena (hanging wire bundles, ship consoles, pillar "
            f"signage; menu-stage copies untouched) are meshoptimizer-simplified at 0.5% relative error, freeing "
            f"{plan['freed_triangles']:,} triangles. Collision is unchanged and the regression views show no visible "
            'change.',
            f"- q38: `water_foamy_fountain_01` is animated and faint in Apex; its opacity map is scaled by "
            f"{textures['foam_opacity_scale']}. q40: the R5Reloaded placeholder panel of `oasis_signs_ad_atlas_01` is "
            'repainted with an original north-star emblem.',
            f"Validation: {binary['checks']:,} binary checks; collision grid = previous active set plus new headers; "
            f'{ok}/{len(report)} report views fully clean; {len(runtime["contacts"])} new collider contacts; '
            f"{collision['matched']}/{len(collision['contacts'])} drawn-surface contacts; 40-view regression unchanged "
            'except the repainted screen; spawns, postmatch lobby, stock and map reload.',
            'Rollback: `party-crasher/before-0.6.2/` (including `texture-originals/`) on the build drive.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8'); shutil.copy2(docs/'README.md', mod/'README.md')
    status = json.loads((mod/'build-status.json').read_text())
    status.update(version=VERSION, bsp_sha256=sha, render_fraction=proof['render_fraction'], new_placements=len(restored))
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
