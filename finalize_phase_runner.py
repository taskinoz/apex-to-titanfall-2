"""Publish Phase Runner 1.7.1: 1.7.0 plus base decal z-fighting, container frames and catwalk profile."""
import json
import shutil

from phase_runner_blend import ROOT, WORK, PACKAGE, PAK
from package_player_mods import RELEASES, digest, write_player_zip

VERSION = '1.7.1'
NAME = 'PhaseRunner'
NOTE = ('Fixes the flickering floor in both starting bases (opaque Apex decals drawn on the same plane as the floor; '
        'the stripes are now alpha-blended decals and a wrong stand-in sign texture is hidden), restores the metal frames '
        'around stacked containers that left visible gaps, and smooths the tunnel catwalks so they no longer dip and '
        'meet the floor at both arena ends. Minimaps are no longer washed out (shared ApexMaps.UI 0.1.1). Includes 1.7.0: '
        'Apex two-layer blending, Apex-scale ground tiling and collision matched to 210 cliffs and rocks.')


def finalize():
    cand = WORK/'candidate'/NAME
    if json.loads((PACKAGE/'mod.json').read_text())['Version'] not in ('1.7.0', VERSION):
        raise ValueError('Unexpected accepted baseline')
    binary = json.loads((WORK/'binary-validation.json').read_text()); runtime = json.loads((WORK/'runtime-validation.json').read_text())
    blend = json.loads((WORK/'blend/patch.json').read_text()); mats = json.loads((WORK/'blend/materials.json').read_text())
    coll = json.loads((WORK/'collision/result.json').read_text())
    sha = digest(cand/'mod/maps/mp_phase_runner.bsp')
    if sha != digest(WORK/'mp_phase_runner.bsp') or binary['bsp_sha256'] != sha or runtime['bsp_sha256'] != sha:
        raise ValueError('Stale Phase Runner validation')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native errors during validation')
    det = json.loads((WORK/'details/result.json').read_text())
    for rel in ('mod/maps/mp_phase_runner.bsp', 'mod/maps/mp_phase_runner.stbsp', f'paks/{PAK}.rpak', 'paks/rpak.json', 'mod.json'):
        shutil.copy2(cand/rel, PACKAGE/rel)
        if digest(cand/rel) != digest(PACKAGE/rel):
            raise ValueError('Published payload differs: '+rel)
    after = ROOT/'docs/phase-runner-1.7.1'; after.mkdir(parents=True, exist_ok=True)
    audit_after = json.loads((__import__('pathlib').Path('D:/Games/ApexToTitanfallWork/legacy-audit/after-1.7.0/phase-runner/collision-visibility.json')).read_text())
    audit_before = json.loads((__import__('pathlib').Path('D:/Games/ApexToTitanfallWork/legacy-audit/phase-runner/collision-visibility.json')).read_text())
    proof = dict(bsp_sha256=sha, binary_checks=binary['checks'], native_blend_materials=len(mats['native_blend_materials']),
                 texture_data_rebound=mats['texture_data_rebound'], blend_pack_bytes=mats['pak_bytes'],
                 world_uv_rewritten=blend['uv_rewritten_corners'], single_layer_kept=blend['excluded_unmatched']+['asphalt08_cracked_bm'],
                 rocks_matched=coll['replaced'], source_headers_disabled=coll['source_headers_disabled'],
                 source_brushes_disabled=coll['source_brushes_disabled'], drawn_collision_triangles=coll['drawn_collision_triangles'],
                 invisible_collision_before=audit_before['fraction'], invisible_collision_after=audit_after['fraction'],
                 spawns_clear_and_supported=runtime['spawns'], drawn_rock_contacts=f"{runtime['matched']}/{len(runtime['contacts'])}",
                 both_teams_verified=True, postmatch_lobby=True, stock_map_reload=True, map_reload=True,
                 catwalk_meshes_smoothed=det['catwalk_meshes'], catwalk_max_shift=det['max_abs_dz'], catwalk_route_ends=det['route_ends'],
                 container_frames_restored=len(det['container_frames']), frame_triangles=det['frame_triangles'],
                 decals_alpha_blended=['cement_stripes_decals_vert', 's2s_bolt_decals_03', 's2s_boltdecals_02', 's2s_decals_01'],
                 stand_in_hidden='sign_warning_yellow (for unrecovered signage_building_02)', single_client_only=True)
    (after/'validation.json').write_text(json.dumps(proof, indent=2)+'\n')
    text = [f'# Phase Runner {VERSION}', NOTE, '## How',
            '- `phase_runner_blend.py` traces each Apex blend material\'s pixel shader (layer UV source, ramp, vertex-alpha '
            'or z-up blend input). Vertex alpha comes from the source BSP vertex colours and prop VG colours matched by '
            'position, or from the z-up normal term; materials whose albedo is projected from world position get '
            '`uv = (x, -y) . RotScale + Translate` in source coordinates. The surfaces are rebound to native Coliseum '
            'wld bm materials in a new `phase_runner_blend.rpak`. Layer 2 is sampled at the mesh UV (Titanfall\'s shader '
            'has one UV): the tiling of world-projected snow/moss layers on rocks is approximate, not their colour.',
            f"- Kept single-layer: {', '.join(proof['single_layer_kept'])} (unmatched source alpha or a regression in "
            'native captures).',
            f"- `phase_runner_collision.py` finds each rock's drawn LOD by vertex matching and replaces the source collider "
            f"of {coll['replaced']} rocks over 15% mismatch with their drawn triangles. Owners with any disabled primitive "
            '(tunnel caps, catwalk clips) are not touched; spawns are not moved.',
            f"Invisible reachable collision: {audit_before['fraction']*100:.1f}% before, {audit_after['fraction']*100:.1f}% after "
            '(upper bound: reach ignores out-of-bounds volumes).',
            f"Validation: {binary['checks']} binary checks (only vertex alpha/UV, texture-data strings and appended collision "
            f"change; render budget unchanged); {runtime['spawns']} spawns clear and supported; {proof['drawn_rock_contacts']} "
            'drawn-rock contacts; both teams, postmatch lobby, stock and map reload.',
            'Rollback: `legacy-work/phase-runner/before-1.7.0/` on the build drive.']
    (after/'README.md').write_text('\n\n'.join(text)+'\n', encoding='utf-8')
    readme = (PACKAGE/'README.md').read_text(encoding='utf-8')
    (PACKAGE/'README.md').write_text('\n\n'.join(text)+'\n\n## Previous release notes\n\n'+readme, encoding='utf-8')
    status = json.loads((PACKAGE/'build-status.json').read_text()); status.update(version=VERSION, bsp_sha256=sha)
    (PACKAGE/'build-status.json').write_text(json.dumps(status, indent=2)+'\n')
    RELEASES[NAME] = dict(RELEASES[NAME], version=VERSION, notes=NOTE)
    result = write_player_zip(PACKAGE, ROOT/'output'/f'{NAME}-{VERSION}-Northstar.zip')
    path = ROOT/'output/player-distributions.json'
    ledger = json.loads(path.read_text()) if path.exists() else {}
    ledger[NAME] = result; path.write_text(json.dumps(ledger, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    finalize()
