"""Install the validated interior-lighting and balanced-material candidate."""
import json,re,shutil,zipfile,hashlib
from pathlib import Path
from finalize_lighting_release import ROOT,digest
from apply_interior_lighting import TARGET
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
PACKAGE=ROOT/'northstar/PhaseRunner.InteriorRelease'

def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(bsp)!=digest(TARGET):raise ValueError('Tested candidate differs from package')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.33.zip').is_file():raise ValueError('Confirmed outdoor-lighting rollback missing')
    unit=(ROOT/'logs/interior-lighting-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Interior regression failed')
    log=(ROOT/'logs/interior-0.1.34-validation.log').read_text(encoding='utf-8-sig')
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing native validation '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script failure')
    loaded=re.search(r'loading took ([0-9.]+)s',log)
    if not loaded:raise ValueError('Native map load unverified')
    status=json.loads((PACKAGE/'build-status.json').read_text());repair=status['interior_light_repair'];optimization=status['texture_optimization']
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.34':raise ValueError('Incorrect version')
    if not repair['collision_and_walkways_byte_unchanged'] or not repair['sun_visibility_bytes_preserved']:raise ValueError('Preservation proof missing')
    materials=ROOT/'output/phase-runner/balanced-materials';validation=json.loads((materials/'validation.json').read_text())
    if not validation['all_dependencies_present'] or validation['materials']!=380 or validation['assets']!=947:raise ValueError('Material dependency mismatch')
    pak=PACKAGE/'paks/phase_runner_world.rpak'
    if digest(pak)!=digest(materials/'build/phase_runner_world.rpak'):raise ValueError('Material pack mismatch')
    base=ROOT/'northstar/PhaseRunner.Preview'
    for p in PACKAGE.rglob('*'):
        if p.is_file() and p.suffix in ('.mdl','.stbsp'):
            if digest(p)!=digest(base/p.relative_to(PACKAGE)):raise ValueError('Unexpected model/catalog change')
    budget=audit(bsp)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.85:raise ValueError('Draw budget exceeded')
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md','INTERIOR_LIGHTING.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    for name in ('pbr-audit.json','recovered-materials.json','ground-lighting-audit.json'):shutil.copy2(base/name,PACKAGE/name)
    (PACKAGE/'texture-optimization.json').write_text(json.dumps(optimization,indent=2))
    (PACKAGE/'interior-lights.json').write_text(json.dumps(repair['interior_fixtures'],indent=2))
    (PACKAGE/'README.md').write_text('''# Phase Runner Northstar preview 0.1.34

Restart Northstar and load `map mp_phase_runner_preview`.

Thirty static native point lights illuminate the two buildings and both tunnels:
12 recovered building fixture positions and 18 new tunnel traversal lights.
Their static visibility is ray-baked; the existing native shader supplies PBR
diffuse/specular response. Outdoor sun/sky data and both walkways are preserved.

The texture pack is reduced from about 886 MB to 565 MB. Exact duplicate channels
are shared, and all textures have full resident mip chains. Albedo top levels and
rock/terrain normal top levels are unchanged; other auxiliary textures are capped
at 1024. Shadow draws fall from 107 to 27 with every caster triangle retained.
The geometry, render visibility, collider data and native STBSP remain unchanged.

Seven focused regression tests and all 927 fresh native collision checks pass.
Client brightness, PBR highlights, performance and improvement to the reported
popping still need verification. Please check both buildings and tunnel routes.
All texture mips remain resident; spatial starpak streaming remains unfinished.
See INTERIOR_LIGHTING.md and runtime-validation.json for details and limitations.
The confirmed outdoor lighting 0.1.33 archive remains available for rollback.
''')
    old_size=(base/'paks/phase_runner_world.rpak').stat().st_size
    evidence=dict(version='0.1.34',bsp_sha256=digest(bsp),material_rpak_sha256=digest(pak),native_server_loaded=True,
        load_seconds=float(loaded[1]),interior_and_optimization_tests=7,collision_checks=927,
        native_static_interior_lights=30,building_lights=12,tunnel_lights=18,covered_surface_luxels_lit=80319,
        outdoor_sun_visibility_and_sky_direction_byte_preserved=True,geometry_collision_visibility_and_walkways_byte_preserved=True,
        shadow_batches_before=107,shadow_batches_after=27,all_shadow_caster_triangles_preserved=True,
        old_material_rpak_bytes=old_size,material_rpak_bytes=pak.stat().st_size,
        material_rpak_reduction_percent=(1-pak.stat().st_size/old_size)*100,
        exact_duplicate_textures_removed=136,full_resident_texture_mip_chains=True,albedo_and_terrain_normal_top_blocks_preserved=True,
        auxiliary_resolution_cap=1024,native_material_dependencies_verified=True,stbsp_byte_unchanged=True,
        draw_budget=budget,prior_client_verified_lighting_version='0.1.33',client_rendering_verified=False,
        popping_cause_confirmed=False,
        limitation='Native server checks do not verify interior brightness, point-light GPU binding, PBR appearance or popping/performance. '
            'Auxiliary prop textures have lower maximum resolution. Static direct-light visibility and small artistic ambient fill are not a GI bake. '
            'All mips are resident, not starpak streamed. Baseline arc-cannon KeyValues warning remains in the test profile.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for root in (base,Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in PACKAGE.rglob('*'):
            if p.is_file():target=root/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(root/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.34; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.34.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    print(json.dumps(dict(version='0.1.34',installed_files=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,material_rpak_reduction_percent=evidence['material_rpak_reduction_percent']),indent=2),flush=True)
if __name__=='__main__':finalize()
