"""Visibility-only recovery over the client-confirmed character lighting build."""
import json, os, shutil, struct
from pathlib import Path
from repair_camera_visibility import build_camera_visibility
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'output/phase-runner/character-lighting/mp_phase_runner.bsp'
OUT = ROOT/'output/phase-runner/playable-visibility'
TARGET = OUT/'mp_phase_runner.bsp'
BASE = ROOT/'northstar/PhaseRunner.Preview'
PACKAGE = ROOT/'northstar/PhaseRunner.PlayableVisibilityRelease'
CAMERA_MIN = (-12288., -12288., -4096.)
CAMERA_MAX = (12288., 12288., 4096.)

def build():
    if json.loads((BASE/'mod.json').read_text())['Version'] != '0.1.38':
        raise ValueError('Expected the confirmed character-lighting baseline')
    budget = audit(SOURCE)
    if budget['native_padded_indices'] > WORLD_INDEX_CAPACITY*.85:
        raise ValueError('Conservative visibility requires native index headroom')
    l = read_lumps(SOURCE, (0x51, 0x78))
    nodes, refs, objects = build_camera_visibility(l[0x51], l[0x78], CAMERA_MIN, CAMERA_MAX)
    proof = validate_visibility(nodes, refs, objects, l[0x51])
    compaction = compact(SOURCE, TARGET, {0x77: nodes, 0x79: objects})
    report = dict(version='0.1.39', source_version='0.1.38', **proof,
        camera_domain=[CAMERA_MIN, CAMERA_MAX], flat_leaf_limit=255,
        maximum_pending_nodes=len(nodes)//32-1, reference_order_preserved=True,
        geometric_mesh_bounds_preserved=True, all_draw_geometry_preserved=True,
        character_probes_collision_lights_lightmaps_and_portals_byte_preserved=True,
        new_portal_connections=0, budget=budget, compaction=compaction,
        native_reader='client.dll+0x2e9983 camera-inside acceptance; +0x2e9dcf emits references',
        client_lighting_and_presentation_confirmed_by_user=True,
        client_geometry_verified=False,
        limitation='Removes access-path selectivity inside the supported camera domain. '
                   'Actual client geometry visibility and performance require an in-game check. '
                   'Native renderer still uses exact geometric mesh bounds.')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'playable-visibility.json').write_text(json.dumps(report, indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'), TARGET.with_suffix('.stbsp'))
    for source in BASE.rglob('*'):
        if not source.is_file(): continue
        rel = source.relative_to(BASE); dest = PACKAGE/rel
        actual = TARGET if rel.as_posix() == 'mod/maps/mp_phase_runner.bsp' else source
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if os.path.samefile(actual, dest): continue
            dest.unlink()
        if actual.stat().st_size > 10*1024*1024: os.link(actual, dest)
        else: shutil.copy2(actual, dest)
    mod = json.loads((PACKAGE/'mod.json').read_text()); mod['Version']='0.1.39'
    mod['Description']='Phase Runner with playable-area visibility recovery and native player lighting.'
    (PACKAGE/'mod.json').write_text(json.dumps(mod, indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text())
    status['playable_visibility_repair']=report
    status['visibility_rebuild']=proof
    (PACKAGE/'build-status.json').write_text(json.dumps(status, indent=2))
    shutil.copy2(OUT/'playable-visibility.json', PACKAGE/'playable-visibility.json')
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__': build()
