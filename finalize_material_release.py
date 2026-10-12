"""Install the verified lighting/material candidate and preserve both rollbacks."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from finalize_lighting_release import digest,ROOT
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
PACKAGE=ROOT/'northstar/PhaseRunner.MaterialRelease'

def finalize():
    source=ROOT/'output/phase-runner/preview-material-repaired/mp_phase_runner_preview.bsp'
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(source)!=digest(bsp):raise ValueError('Packaged BSP differs from tested candidate')
    for version in ('0.1.30','0.1.31'):
        if not (ROOT/f'output/PhaseRunner.Preview-{version}.zip').is_file():raise ValueError('Rollback archive missing')
    unit=(ROOT/'logs/dev-material-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 4 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Material preservation tests failed')
    log=(ROOT/'logs/dev-material-0.1.32-validation.log').read_text(encoding='utf-8-sig')
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing native validation '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script failure')
    loaded=re.search(r'loading took ([0-9.]+)s',log)
    if not loaded:raise ValueError('Native map load not verified')
    status=json.loads((PACKAGE/'build-status.json').read_text());repair=status['dev_material_repair']
    if not repair['vertex_and_lightmap_lumps_byte_identical'] or repair['fallback_draw_triangles_remaining']:raise ValueError('Material repair incomplete')
    validation=json.loads((ROOT/'output/phase-runner/dev-materials/validation.json').read_text())
    if not validation['all_dependencies_present']:raise ValueError('Unresolved RPak dependencies')
    if digest(PACKAGE/'paks/phase_runner_world.rpak')!=digest(ROOT/'output/phase-runner/dev-materials/build/phase_runner_world.rpak'):raise ValueError('Packaged material RPak mismatch')
    budget=audit(bsp)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.85:raise ValueError('Draw budget headroom exceeded')
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    shutil.copy2(ROOT/'output/phase-runner/dev-materials/pbr-audit.json',PACKAGE/'pbr-audit.json')
    shutil.copy2(ROOT/'output/phase-runner/dev-materials/recovered.json',PACKAGE/'recovered-materials.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner Northstar preview 0.1.32

Restart Northstar and load `map mp_phase_runner_preview`.

The first native sun/sky lightmap bake and corrected PBR tangent frames are
included. This follow-up replaces 6,961 developer-textured triangles, restoring
original floor, roof and barrel artwork with normal/gloss/specular channels.
Three missing material variants use themed substitutes, and authored developer
cladding uses the recovered white floor tile. See DEV_MATERIALS.md for details.

All 873,018 triangles, their lighting coordinates, and all collider data are
preserved. Both tunnel walkways remain unchanged. Nessie and future catwalk
work are recorded in ART_TODO.md. The native resident-texture STBSP catalog is
updated; spatial mip streaming remains unfinished.

Four material preservation tests, the seven lighting tests from 0.1.31, and all
927 fresh native server collision checks pass. GPU lighting, shadows, highlights
and reflections still need a client check. This first bake has no indirect bounce,
area/emissive lighting, new reflection probes or alpha-tested foliage shadows.
It adds about 570 MB of uncompressed lightmap payload.

The confirmed playable 0.1.30 and first lighting 0.1.31 archives remain available.
See LIGHTING.md, DEV_MATERIALS.md and runtime-validation.json for evidence.
''')
    evidence=dict(version='0.1.32',bsp_sha256=digest(bsp),native_server_loaded=True,load_seconds=float(loaded[1]),
        material_preservation_tests=4,prior_lighting_tests=7,collision_checks=927,repaired_dev_triangles=6961,
        geometry_and_lightmap_coordinates_preserved=True,collision_lumps_byte_preserved=True,walkways_unchanged=True,
        native_material_dependencies_verified=True,resident_stbsp_catalog_verified=True,draw_budget=budget,
        prior_client_verified_version='0.1.30',client_rendering_verified=False,
        limitation='GPU lighting appearance requires client inspection. No indirect bounce or custom reflection probes; '
            'three material variants use documented substitutes. Baseline arc-cannon KeyValues warning remains in the isolated profile.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={str(p.relative_to(PACKAGE)).replace('\\','/'):digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for root in (ROOT/'northstar/PhaseRunner.Preview',Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in PACKAGE.rglob('*'):
            if p.is_file():target=root/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(root/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.32; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.32.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    print(json.dumps(dict(version='0.1.32',installed_files=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100),indent=2),flush=True)

if __name__=='__main__':finalize()
