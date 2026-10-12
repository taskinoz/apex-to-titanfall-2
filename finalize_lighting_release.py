"""Install the tested lighting-only candidate and retain the playable rollback."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'northstar/PhaseRunner.LightingRelease'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def finalize():
    source=ROOT/'output/phase-runner/preview-baked/mp_phase_runner_preview.bsp';bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(source)!=digest(bsp):raise ValueError('Packaged candidate differs from tested map')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.30.zip').is_file():raise ValueError('Playable rollback missing')
    unit=(ROOT/'logs/lighting-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Lighting regression failed')
    log=(ROOT/'logs/lighting-0.1.31-validation.log').read_text(encoding='utf-8-sig')
    for marker in ['collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear']:
        if marker not in log:raise ValueError('Missing engine check '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Script failure')
    loaded=re.search(r'loading took ([0-9.]+)s',log)
    if not loaded:raise ValueError('Map not loaded')
    budget=audit(bsp)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.85:raise ValueError('Draw capacity exceeded')
    status=json.loads((PACKAGE/'build-status.json').read_text());bake=status['static_light_bake']
    if not bake['geometry_and_albedo_uv_preserved'] or not bake['collision_lumps_byte_verified']:raise ValueError('Missing preservation evidence')
    base=ROOT/'northstar/PhaseRunner.Preview'
    # Material assets, resident streaming catalog and entities are identical.
    for p in PACKAGE.rglob('*'):
        if p.is_file() and (p.relative_to(PACKAGE).parts[0]=='paks' or p.suffix in ('.mdl','.stbsp','.ent')):
            if digest(p)!=digest(base/p.relative_to(PACKAGE)):raise ValueError('Unexpected asset change '+str(p))
    shutil.copy2(ROOT/'ART_TODO.md',PACKAGE/'ART_TODO.md')
    shutil.copy2(ROOT/'LIGHTING.md',PACKAGE/'LIGHTING.md')
    shutil.copy2(ROOT/'output/phase-runner/light-bake/pbr-audit.json',PACKAGE/'pbr-audit.json')
    readme='''# Phase Runner Northstar preview 0.1.31

Restart Northstar and load `map mp_phase_runner_preview`.

This is the first complete static lighting bake for the playable 0.1.30 geometry.
All 873,018 triangles, materials, diffuse UVs and collider records are preserved.
Both tunnel walkways remain unchanged. The Nessie location and future catwalk
idea are noted in ART_TODO.md.

Two native 4096-pixel lightmap pages store sampled directional sky occlusion and
static sun visibility, covering 9,616,777 surface luxels. Corrected tangent frames
allow the existing recovered normal/gloss/specular materials to respond in the
native PBR shader. The RPak and resident-texture STBSP catalog are unchanged.

Seven lighting/preservation tests and all 927 isolated-server collision checks
pass. The map loads in the native engine. Dedicated checks cannot verify GPU
lighting: please inspect outdoor rock shadows, metal highlights and tunnel
lighting, as well as any renewed visibility issues, after restarting the client.

This bake does not yet include indirect bounce, area/emissive lighting, new
reflection probes or alpha-tested foliage shadowing. Some PBR texture channels
still use native fallbacks. Lightmaps add about 570 MB of uncompressed payload.
The confirmed playable 0.1.30 archive remains available for rollback.

See LIGHTING.md, build-status.json, pbr-audit.json and runtime-validation.json.
'''
    (PACKAGE/'README.md').write_text(readme)
    evidence=dict(version='0.1.31',bsp_sha256=digest(bsp),native_server_loaded=True,load_seconds=float(loaded[1]),
        lighting_tests=7,collision_checks=927,geometry_preservation_verified=True,collision_byte_preservation_verified=True,
        walkways_unchanged=True,material_rpak_and_streaming_catalog_unchanged=True,draw_budget=budget,
        prior_client_verified_version='0.1.30',client_rendering_verified=False,
        limitation='First static sun/sky bake. GPU light binding, PBR appearance, reflections and memory use require client inspection. '
            'No indirect bounce or custom reflection probes. Baseline arc-cannon KeyValues warning is present in the isolated profile.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={str(p.relative_to(PACKAGE)).replace('\\','/'):digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for root in [Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview'),base]:
        for p in PACKAGE.rglob('*'):
            if p.is_file():target=root/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(root/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.31; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.31.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    print(json.dumps(dict(version='0.1.31',installed_files=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100),indent=2),flush=True)

if __name__=='__main__':finalize()
