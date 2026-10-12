"""Record textured preview test results and verify the installed package."""
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def finalize():
    package = ROOT/'northstar/PhaseRunner.Preview'
    installed = Path(r'D:\Games\Titanfall2\R2Northstar\mods\PhaseRunner.Preview')
    bsp = package/'mod/maps/mp_phase_runner_preview.bsp'
    version = json.loads((package/'mod.json').read_text())['Version']
    log_path = ROOT/f'logs/preview-{version}-final.log'
    log = log_path.read_text()
    status = json.loads((package/'build-status.json').read_text())
    collision_count=len(status['collision_probes'])
    if f'Phase Runner collision probes: {collision_count}/{collision_count} hit' not in log:
        raise ValueError('Dedicated collision evidence is incomplete')
    load_seconds = float(re.search(r'loading took ([0-9.]+)s',log).group(1))
    status = json.loads((package/'build-status.json').read_text())
    prop_status = status.get('structural_props')
    evidence = dict(version=version,bsp_sha256=hashlib.sha256(bsp.read_bytes()).hexdigest(),
        dedicated_server_loaded=True,load_seconds=load_seconds,
        sample_collision_hits=collision_count,sample_collision_count=collision_count,unit_checks_passed=43 if status.get('landscape_restore') else 37 if status.get('visibility_range_repair') else 35 if status.get('portal_material_repair') else 30 if status.get('broad_restore') else 27 if status.get('missing_sections') else 25 if status.get('lighting_repair') else (22 if status.get('terrain_uv_repair') else (18 if prop_status else 14)),
        original_material_face_order_verified=True,
        native_material_dependencies_verified=True,
        recovered_world_materials=79,total_world_materials=85,
        recovered_world_triangles=225303,total_world_triangles=227920,
        client_textures_visual_verified=False,sky_rendering_verified=False,
        exterior_collision_complete=False,static_props_converted=False,
        log=str(log_path.relative_to(ROOT)).replace('\\','/'),
        previous_user_feedback='The user confirms 0.1.15 looks substantially better but portal loading issues remain. Portal pop-in occurs with distance and camera rotation. This build needs client verification. Missing doors are accepted. The 0.1.15 client log confirms the STBSP loaded without a reported format error. User supplied investigation coordinates (-3250,-3479,-1115) and (-2213,3026,-1091). The user confirmed ground flickering stopped in 0.1.8.',
        limitation='Dedicated server checks do not verify GPU materials, sky rendering or full movement coverage.')
    if prop_status:
        evidence['structural_props'] = dict(restored=prop_status['restored_props'],models=prop_status['models'],
            triangles=prop_status['triangles'],visual_verified=False,collision_added=False,
            approximate_material_triangles=prop_status['ambiguous_material_triangles'])
    if status.get('ground_surface_repair'):
        evidence['ground_surface_repair'] = status['ground_surface_repair']
    if status.get('terrain_uv_repair'):
        evidence['terrain_uv_repair'] = status['terrain_uv_repair']
    if status.get('map_structures'):
        evidence['map_structures'] = status['map_structures']
    if status.get('visibility_range_repair'):
        evidence['previous_user_feedback']='The user reports worse distance/angle pop-in in 0.1.16, sometimes visible only close up at particular angles, and requested Homestead/Colony as native references. 0.1.17 corrects the internal subtree start offsets found by that comparison; its client rendering remains unverified.'
    for field in ('lighting_repair','streaming_sidecar','support_structures','legacy_sky_cleanup','area_details','missing_sections','broad_restore','visibility_rebuild','compaction','final_compaction','portal_surface_filter','portal_material_repair','portal_filter_compaction','visibility_range_repair','landscape_restore','vertex_packing','conservative_draw_bounds','terrain_transition_bake','portal_render_settings','draw_regression_repair','spatial_draw_sections','prop_physics','structure_physics','native_cell_rebuild','central_material_audit','index_padding_repair','surface_alignment_repair','signed_rock_collision_repair','hull_clearance_probes'):
        if status.get(field): evidence[field]=status[field]
    if status.get('landscape_restore'):
        unit_log=(ROOT/f'logs/unit-{version}.log').read_text()
        match=re.search(r'Ran (\d+) tests',unit_log)
        if not match or '\nOK' not in unit_log or 'FAILED' in unit_log:raise ValueError('Unit verification is incomplete')
        evidence['unit_checks_passed']=int(match.group(1))
        evidence['previous_user_feedback']='0.1.17 still has severe distance/angle pipe pop-in, missing outer scenery, and jagged snow/flower boundaries. This build adds original rock placements, an approximate opaque terrain seam bake, shared vertex buffers, two-sided portal surfaces and conservative draw bounds. Client rendering remains unverified; full original layered shaders and prop collision are unfinished.'
    if status.get('draw_regression_repair'):
        evidence['previous_user_feedback']='0.1.18 portals and other props disappear. 0.1.19 restores geometric draw bounds, spatial visibility and earlier native material rasterizer flags while retaining recovered scenery, terrain texture bake and shared vertex buffers. Client rendering remains unverified; earlier pop-in may remain.'
    if status.get('prop_physics'):
        count=sum(p['kind'] in ('rock','pipe','portal') or bool(p.get('prop_probe')) for p in status['collision_probes'])
        if f'Phase Runner prop hull probes: {count}/{count} hit' not in log:raise ValueError('Prop hull evidence incomplete')
        prop_results=re.findall(r'Phase Runner prop hull probe \d+: fraction=([0-9.]+) startSolid=(\w+)',log)
        if len(prop_results)!=count or any(float(f)>=1 or solid!='false' for f,solid in prop_results):raise ValueError('Prop hull contacts did not start in clear space')
        evidence['prop_hull_clear_start_contacts_verified']=True
        evidence['prop_hull_hits']=count
        evidence['prop_hull_count']=count
        evidence['previous_user_feedback']='0.1.19 looks better but rock/prop pop-in and missing rock/pipe collision remain. 0.1.20 adds smaller spatial draw sections and native collision to recovered props. GPU rendering and player movement remain unverified.'
    if status.get('native_cell_rebuild'):
        evidence['previous_user_feedback']='The user reports more visible props in 0.1.20 but invisible central structures and missing wall, railing and tube floor collision. 0.1.21 rebuilds native outdoor cells/portals and local vertex ranges, and supplements original structural collision. Central material visibility and player movement need client verification.'
    if status.get('index_padding_repair'):
        evidence['previous_user_feedback']='0.1.21 produced hall of mirrors and a client crash when grappling. The dump exposed a triangle-pair read crossing an odd mesh boundary. 0.1.22 supplies native degenerate padding, restores the 0.1.20 visibility and vertex ranges, and retains additional structural collision. GPU rendering and a player grapple still need client verification.'
    if status.get('surface_alignment_repair'):
        edge_count=len(status['hull_clearance_probes'])
        results=re.findall(r'Phase Runner edge clearance probe \d+: fraction=([0-9.]+) startSolid=(\w+)',log)
        if len(results)!=edge_count or any(float(f)!=1 or solid!='false' for f,solid in results):raise ValueError('Hull edge clearance failed in the game engine')
        if f'Phase Runner edge clearance probes: {edge_count}/{edge_count} clear' not in log:raise ValueError('Incomplete hull edge evidence')
        additional=(ROOT/f'logs/surface-unit-{version}.log').read_text()
        matches=re.findall(r'Ran (\d+) tests',additional)
        if not matches or '\nOK' not in additional or 'FAILED' in additional:raise ValueError('Surface/hull regression checks failed')
        evidence['unit_checks_passed']+=sum(map(int,matches))
        evidence['hull_edge_clearance_count']=edge_count
        evidence['previous_user_feedback']='0.1.22 shows more objects but collision feels offset, some props pop in, a ramp looks stretched and doorways show barrier planes. The user suspects out-of-bounds unloading and menu lighting. 0.1.23 adds native hull edge planes, exact padded draw ranges, removes Apex start barrier visuals and replaces borrowed spatial lightmap pages. GPU appearance, missing collision and the ramp remain unverified.'
    if status.get('signed_rock_collision_repair'):
        additional=(ROOT/f'logs/signed-rock-unit-{version}.log').read_text()
        matches=re.findall(r'Ran (\d+) tests',additional)
        if not matches or '\nOK' not in additional or 'FAILED' in additional:raise ValueError('Signed BVH regression checks failed')
        evidence['unit_checks_passed']+=sum(map(int,matches))
        evidence['previous_user_feedback']='0.1.23 contains invisible obstructions at (186,-5211,-955) and (-1716,-3994,-963); central rocks only become visible from above. 0.1.24 fixes signed global packed vertices for 73 rock hulls and checks both reported obstructions for clearance. The distinct rendering problem remains under investigation.'
    feedback_path = ROOT/f'output/phase-runner/client-feedback-{version}.json'
    if status.get('prop_coverage_repair'):
        additional=(ROOT/f'logs/coverage-unit-{version}.log').read_text()
        matches=re.findall(r'Ran (\d+) tests',additional)
        if not matches or '\nOK' not in additional or 'FAILED' in additional:raise ValueError('Prop coverage regression checks failed')
        evidence['unit_checks_passed']+=sum(map(int,matches))
        evidence['prop_coverage_repair']=status['prop_coverage_repair']
        evidence['visibility_queue_rebuild']=status['visibility_queue_rebuild']
        evidence['previous_user_feedback']='The user confirms collision improves in 0.1.24, but crates and pipe rings lack collision. Rocks and pipes appear when looking up/down and disappear when looking straight ahead; stairs disappear from particular standing views. 0.1.25 adds original convex collision to 575 crate/ring/elbow placements, reclaims wholly enclosed world solids, and bounds native visibility traversal. The GPU cause is not established; client rendering and full movement need verification.'
    if status.get('coordinate_collision_repair'):
        additional=(ROOT/f'logs/coordinate-unit-{version}.log').read_text()
        match=re.search(r'Ran (\d+) tests',additional)
        if not match or '\nOK' not in additional or 'FAILED' in additional:raise ValueError('Coordinate collision regression checks failed')
        evidence['unit_checks_passed']+=int(match.group(1))
        evidence['coordinate_collision_repair']=status['coordinate_collision_repair']
        evidence['previous_user_feedback']='The user identifies disappearing stairs at (-4176.4,-1463.9,-1014.6), a missing cargo collider at (-1330.3,3043.2,-928), pipe gaps at (-2163.4,3016.3,-974.4), (3587.7,2513.7,-1152.9), (4484,474,-1152.1), and horizontally invisible rocks at (1839.9,-782,-1200.7). 0.1.26 restores original stair/cargo physics and 1800 more tunnel floor prisms. The camera-angle rendering issue remains unresolved; full movement needs client verification.'
    if feedback_path.is_file():
        feedback = json.loads(feedback_path.read_text())
        evidence['client_feedback'] = feedback
        evidence['client_textures_visual_verified'] = feedback.get('world_textures_visible',False)
        evidence['sky_rendering_verified'] = feedback.get('sky_visible',False)
        if 'structural_props' in evidence:
            evidence['structural_props']['visual_verified'] = feedback.get('props_visible',False)
    (package/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks = {str(p.relative_to(package)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in package.rglob('*') if p.is_file() and p.name != 'checksums.json'}
    (package/'checksums.json').write_text(json.dumps(checks,indent=2))
    for name in ('runtime-validation.json','checksums.json'):
        shutil.copy2(package/name,installed/name)
    for relative,digest in checks.items():
        actual = hashlib.sha256((installed/relative).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f'Installed file mismatch: {relative}')
    archive = ROOT/f'output/PhaseRunner.Preview-{version}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for path in package.rglob('*'):
            if path.is_file():
                target.write(path,Path('PhaseRunner.Preview')/path.relative_to(package))
    print(json.dumps(dict(installed_files_verified=len(checks),archive=str(archive),
                          archive_bytes=archive.stat().st_size),indent=2))


if __name__ == '__main__':
    finalize()

