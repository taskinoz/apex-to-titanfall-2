"""Install only the tested native lighting candidate and archive verified copies."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from finalize_lighting_release import ROOT,digest
from repair_environment_lighting import TARGET
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
PACKAGE=ROOT/'northstar/PhaseRunner.EnvironmentRelease'

def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(TARGET)!=digest(bsp):raise ValueError('Tested and packaged BSP differ')
    for version in ('0.1.30','0.1.32'):
        if not (ROOT/f'output/PhaseRunner.Preview-{version}.zip').is_file():raise ValueError('Rollback missing '+version)
    unit=(ROOT/'logs/environment-lighting-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Lighting regression failed')
    log=(ROOT/'logs/environment-0.1.33-validation.log').read_text(encoding='utf-8-sig')
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing native validation '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script failure')
    loaded=re.search(r'loading took ([0-9.]+)s',log)
    if not loaded:raise ValueError('Native map load unverified')
    status=json.loads((PACKAGE/'build-status.json').read_text());repair=status['lighting_environment_repair']
    if not repair['geometry_materials_and_lightmap_uvs_unchanged'] or not repair['collision_and_walkways_byte_unchanged']:
        raise ValueError('Preservation evidence missing')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.33':raise ValueError('Wrong version')
    base=ROOT/'northstar/PhaseRunner.Preview'
    for p in PACKAGE.rglob('*'):
        if p.is_file() and (p.relative_to(PACKAGE).parts[0]=='paks' or p.suffix in ('.mdl','.stbsp')):
            if digest(p)!=digest(base/p.relative_to(PACKAGE)):raise ValueError('Unexpected material/model/catalog change '+str(p))
    budget=audit(bsp)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.85:raise ValueError('Unsafe draw budget')
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    for name in ('pbr-audit.json','recovered-materials.json'):shutil.copy2(base/name,PACKAGE/name)
    shutil.copy2(ROOT/'logs/environment-ground-lighting.json',PACKAGE/'ground-lighting-audit.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner Northstar preview 0.1.33

Restart Northstar and load `map mp_phase_runner_preview`.

The sky dome is excluded from sun/sky occlusion and receives independent
background illumination. The map has native indexed gameplay/menu lighting
environments and remote menu-camera anchors, following Coliseum. Exact compiled
world shadow meshes let nearby dynamic sun shadows use the geometry of the bake.

All geometry, PBR materials, lightmap UVs, visibility and collision are unchanged
from 0.1.32. Both tunnel walkways remain unchanged. Nessie and future catwalk
work remain in ART_TODO.md. Materials and the resident-texture STBSP are identical.

Seven lighting/shadow/preservation tests and all 927 fresh native server collision
checks pass. GPU lighting and menu shadows still require client verification.
Please inspect the dark areas/bright rectangle, open and close the pause/loadout
menu, and check that pilot/Titan menu shadows no longer appear in gameplay.

This remains direct sun plus sampled sky lighting, without indirect bounce,
emissive baking, alpha-tested shadowing or new reflection probes. World shadow
meshes add about 12.5 MB and shadow-pass work; check client performance too.
Rollback archives 0.1.30 and 0.1.32 are preserved in the workspace output folder.
See LIGHTING.md and runtime-validation.json for evidence and limitations.
''')
    evidence=dict(version='0.1.33',bsp_sha256=digest(bsp),native_server_loaded=True,load_seconds=float(loaded[1]),
        lighting_environment_tests=7,collision_checks=927,geometry_materials_visibility_and_collision_byte_preserved=True,
        walkways_unchanged=True,material_rpak_and_stbsp_byte_unchanged=True,menu_stage_origin=repair['menu_stage_origin'],
        sky_caster_triangles_excluded=3968,real_surface_samples_regaining_sun=687100,
        native_world_shadow_meshes=repair['dynamic_static_world_csm_meshes'],draw_budget=budget,
        client_rendering_verified=False,client_performance_verified=False,
        limitation='Dedicated checks do not establish GPU lighting, menu-shadow removal or performance. '
            'No indirect bounce, alpha-tested shadowing or new reflection probes. Baseline arc-cannon KeyValues warning remains in the test profile.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for root in (base,Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in PACKAGE.rglob('*'):
            if p.is_file():target=root/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(root/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.33; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.33.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    print(json.dumps(dict(version='0.1.33',installed_files=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100),indent=2),flush=True)
if __name__=='__main__':finalize()
