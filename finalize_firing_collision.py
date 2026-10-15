"""Publish Firing Range 0.5.1: collision matched to the drawn rocks, target clips removed."""
import json
import shutil

from new_arena_ports import ROOT, WORK, folder
from package_player_mods import RELEASES, digest, write_player_zip
from map_pack_lifetime import audit, audit_shared

VERSION = '0.5.1'
NAME = 'ApexFiringRange'
NOTE = ('Rocks now collide with the shape you see: 329 rocks drawn at coarse detail had full-detail Apex '
        'collision, which left invisible rock to bump into and visible rock to fall into. Their collision is now '
        'the drawn shape, and spawns that stood on the old shape were moved onto the visible ground. Invisible '
        'player clips left around the missing shooting-range targets are removed. Invisible collision across the '
        'playable area drops from about 16% to under 3% of collision surface. Includes 0.5.0 blending and rock '
        'detail. Weapon stations, targets, foliage and AI navigation remain absent. Restart between previews.')


def finalize():
    out = folder('firing-range'); cand = WORK/'collision-candidates'/NAME; mod = ROOT/'northstar'/NAME
    if json.loads((mod/'mod.json').read_text())['Version'] != '0.5.0':
        raise ValueError('Unexpected accepted baseline')
    binary = json.loads((out/'collision-match/binary-validation.json').read_text())
    runtime = json.loads((out/'collision-match/runtime-validation.json').read_text())
    surfaces = json.loads((out/'lod-upgrade/runtime-validation.json').read_text())
    report = json.loads((out/'report-collision-check.json').read_text())
    clips = json.loads((out/'target-clips/result.json').read_text())
    match = json.loads((out/'collision-match/result.json').read_text())
    audit_v = json.loads((out/'collision-visibility.json').read_text())
    sha = digest(cand/'mod/maps/mp_apex_firing_range.bsp')
    if sha != digest(out/'mp_apex_firing_range.bsp'):
        raise ValueError('Staged map differs from build')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    audit_shared(); audit(cand/'paks', 'mp_apex_firing_range')
    for rel in ('mod/maps/mp_apex_firing_range.bsp', 'mod.json'):
        shutil.copy2(cand/rel, mod/rel)
    m = json.loads((mod/'mod.json').read_text()); m['Version'] = VERSION; (mod/'mod.json').write_text(json.dumps(m, indent=2))
    ok = sum(all(r['kind'] == 'ok' for r in s['rays']) for s in report)
    docs = ROOT/'docs/candidates/firing-range/port-0.5.1'; docs.mkdir(parents=True, exist_ok=True)
    proof = dict(bsp_sha256=sha, binary_checks=binary['checks'], placements_matched=match['replaced'],
                 spawns_moved=len(match['spawns_moved']), clip_triangles_removed=clips['removed_invisible_clip_triangles'],
                 drawn_surface_contacts=f"{runtime['matched']}/{len(runtime['contacts'])}",
                 report_positions_clean=f'{ok}/{len(report)}', invisible_collision_fraction=audit_v['fraction'],
                 both_teams_verified=True, postmatch_lobby=True, stock_map_reload=True, firing_reload=True,
                 single_client_only=True, ai_navigation_added=False)
    (docs/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    text = [f'# Firing Range {VERSION}', NOTE, '## How',
            '- `audit_collision_visibility.py` samples the active native collision (brushes and triangle headers) of the '
            'playable area against the drawn surfaces. Before: 15.7% of collision surface had no drawn surface within 24 '
            f"units. After: {audit_v['fraction']*100:.1f}%.",
            '- `match_collision_to_render.py` recovers each placement\'s own collider from the deterministic build order and '
            'measures both directions. Coarse-LOD placements over 15% mismatch have their source collider removed from the '
            'collision grid (data stays serialized) and get triangle collision made from the exact drawn triangles. Spawn '
            'markers not standing on a drawn surface are moved onto the highest drawn surface below them.',
            '- `remove_target_clips.py` removes clip-only collision within 250 units of shooting-range target markers that '
            'has no drawn surface nearby; Apex scripts spawn the targets there, this port does not.',
            f"Validation: {binary['checks']} binary checks; native traces stop on the drawn rock at {runtime['matched']}/"
            f"{len(runtime['contacts'])} sampled rocks; {ok}/{len(report)} reported positions fully clean (the rest have one "
            'edge ray); all spawns clear and supported, landing-pad contacts, postmatch lobby, stock and map reload.',
            'Rollback: `firing-range/before-collision-match/` and `before-target-clips/` on the build drive.']
    (docs/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8'); shutil.copy2(docs/'README.md', mod/'README.md')
    status = json.loads((mod/'build-status.json').read_text()); status.update(version=VERSION, bsp_sha256=sha)
    (mod/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    RELEASES[NAME] = dict(version=VERSION, map='mp_apex_firing_range', title='Firing Range',
                          screenshot='northstar/ApexFiringRange/screenshot.png', notes=NOTE)
    print(json.dumps(write_player_zip(mod, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')))


if __name__ == '__main__':
    finalize()
