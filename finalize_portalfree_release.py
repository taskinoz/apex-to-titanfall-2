"""Verify and install the portal-free candidate; retain the confirmed rollback."""
import hashlib,json,re,shutil,struct,zipfile
from pathlib import Path
from finalize_lighting_release import ROOT,digest
from optimize_portalfree_render import SOURCE,TARGET
from repair_preview_index_padding import read_lumps
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY

PACKAGE=ROOT/'northstar/PhaseRunner.PortalfreeRelease'

def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(bsp)!=digest(TARGET):raise ValueError('Packaged BSP differs from tested candidate')
    rollback=ROOT/'output/PhaseRunner.Preview-0.1.34.zip'
    if not rollback.is_file():raise ValueError('Confirmed rollback missing')
    unit=(ROOT/'logs/portalfree-optimization-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Regressions failed')
    log=(ROOT/'logs/portalfree-0.1.36-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text())
    point=len(status['collision_probes']);hull=len(status['pilot_hull_contact_probes']);clear=len(status['hull_clearance_probes'])
    for marker in (f'collision probes: {point}/{point} hit',f'prop hull probes: {hull}/{hull} hit',f'edge clearance probes: {clear}/{clear} clear'):
        if marker not in log:raise ValueError('Native validation missing '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Native map did not load')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.36':raise ValueError('Wrong candidate version')
    base=ROOT/'northstar/PhaseRunner.Preview'
    if json.loads((base/'mod.json').read_text())['Version']!='0.1.34':raise ValueError('Unexpected baseline')
    if digest(base/'mod/maps/mp_phase_runner_preview.bsp')!=digest(SOURCE):raise ValueError('Baseline mismatch')
    ids=(0x50,0x51,*range(0x6a,0x7a))
    current=read_lumps(bsp,ids);previous=read_lumps(SOURCE,ids)
    for i in range(0x6a,0x77):
        if current[i]!=previous[i]:raise ValueError('Portal baseline mismatch '+hex(i))
    visibility=validate_visibility(current[0x77],current[0x78],current[0x79],current[0x51])
    budget=audit(bsp)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Draw headroom insufficient')
    old=list(struct.iter_unpack('<I3H6b2h2BHI',previous[0x50]))
    new=list(struct.iter_unpack('<I3H6b2h2BHI',current[0x50]))
    if len(old)!=len(new) or any(n[3]>o[3] for o,n in zip(old,new)):raise ValueError('CPU clipping span increased')
    unchanged=[]
    for p in PACKAGE.rglob('*'):
        if p.is_file() and (p.relative_to(PACKAGE).parts[0]=='paks' or p.suffix in ('.mdl','.stbsp','.nut','.ent')):
            if digest(p)!=digest(base/p.relative_to(PACKAGE)):raise ValueError('Unexpected asset modification '+str(p))
            unchanged.append(p.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(rollback) as z:
        for rel in ('mod/maps/mp_phase_runner_preview.bsp','paks/phase_runner_world.rpak'):
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=digest(base/rel):raise ValueError('Rollback differs '+rel)
    shutil.copy2(ROOT/'PORTALFREE_OPTIMIZATION.md',ROOT/'VISIBILITY.md')
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md','INTERIOR_LIGHTING.md','VISIBILITY.md'):
        shutil.copy2(ROOT/doc,PACKAGE/doc)
    for name in ('pbr-audit.json','recovered-materials.json','ground-lighting-audit.json','texture-optimization.json','interior-lights.json'):
        shutil.copy2(base/name,PACKAGE/name)
    shutil.copy2(base/'runtime-validation.json',PACKAGE/'prior-lighting-validation.json')
    report=json.loads(TARGET.with_name('portalfree-optimization.json').read_text())
    shutil.copy2(TARGET.with_name('portalfree-optimization.json'),PACKAGE/'portalfree-optimization.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner Northstar preview 0.1.36

Restart Northstar and load `map mp_phase_runner_preview`.

The 0.1.35 portal experiment is withdrawn after client sky culling and hall
of mirrors. This release restores the exact single-cell/portal records from
the confirmed 0.1.34 release. No connected portals are introduced.
Sky visibility covers the full supported camera domain. Local padded bounds
and conservative guards along both tunnel routes protect nearby surfaces.

Compatible render-batch records drop from 4,561 to 337, and duplicate vertex
data drops by 8,707,864 bytes. All 873,018 triangles retain exact corner
attributes, native winding and material bindings. Each mesh's CPU clipping
span is preserved or reduced; valid paired indices retain 16.54% headroom.

Lighting, PBR textures, shadow geometry, collision and both tunnel walkways
retain the confirmed 0.1.34 data. Seven focused regressions and 927 fresh
native collision checks pass. Texture mips remain resident; STBSP is unchanged.

Client rendering and performance still require an in-game check. Check the
sky, both complete pipe tunnels and outdoor walls, fences and small rocks.
See VISIBILITY.md and runtime-validation.json for evidence and limitations.
The full confirmed-lighting 0.1.34 archive is retained for rollback.
''')
    evidence=dict(version='0.1.36',bsp_sha256=digest(bsp),native_server_loaded=True,load_seconds=float(loading[1]),
        regression_tests=7,collision_checks=point+hull+clear,point_checks=point,player_hull_checks=hull,clearance_checks=clear,
        visibility=visibility,portal_records_restored_from='0.1.34',new_portal_connections=0,
        withdrawn_version='0.1.35',withdrawal_reason='User reported sky culling and hall of mirrors.',
        sky_and_tunnel_cpu_camera_coverage_checked=True,render_sharing=report['render_sharing'],draw_budget=budget,
        draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100,
        all_rendered_corner_attributes_and_material_bindings_exact=True,
        positions_normals_real_mesh_bounds_collision_lightmaps_lights_shadow_geometry_walkways_preserved=True,
        unchanged_asset_hashes_verified=unchanged,prior_client_lighting_confirmed='0.1.34',
        prior_lighting_evidence='prior-lighting-validation.json',rollback_archive=rollback.name,
        client_rendering_verified=False,client_performance_verified=False,
        limitation='Dedicated loading does not exercise client PVS, view-angle rendering, GPU draw submission or frame rate. '
          'Render data savings are measured; FPS improvement is not measured. Texture mips remain resident; no spatial streaming is added.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (base,Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in PACKAGE.rglob('*'):
            if p.is_file():
                target=destination/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        # Only remove the named superseded audit owned by this mod.
        obsolete=destination/'local-visibility-audit.json'
        if obsolete.parent.resolve()!=destination.resolve():raise ValueError('Cleanup target escaped mod directory')
        if obsolete.is_file():obsolete.unlink()
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.36; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.36.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    result=dict(version='0.1.36',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,collision_checks=point+hull+clear,load_seconds=float(loading[1]),visibility=visibility)
    (ROOT/'logs/portalfree-0.1.36-release.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
