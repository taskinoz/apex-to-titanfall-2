"""Install only the hash-verified native visibility candidate and retain rollback."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from finalize_lighting_release import ROOT,digest
from rebuild_local_visibility import SOURCE,TARGET,validate
from repair_preview_index_padding import read_lumps
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
PACKAGE=ROOT/'northstar/PhaseRunner.VisibilityRelease'


def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp'
    if digest(bsp)!=digest(TARGET):raise ValueError('Packaged BSP differs from tested candidate')
    rollback=ROOT/'output/PhaseRunner.Preview-0.1.34.zip'
    if not rollback.is_file():raise ValueError('Confirmed lighting rollback missing')
    unit=(ROOT/'logs/local-visibility-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Visibility regressions failed')
    log=(ROOT/'logs/local-visibility-0.1.35-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text())
    point=len(status['collision_probes']);hull=len(status['pilot_hull_contact_probes']);clear=len(status['hull_clearance_probes'])
    for marker in (f'collision probes: {point}/{point} hit',f'prop hull probes: {hull}/{hull} hit',f'edge clearance probes: {clear}/{clear} clear'):
        if marker not in log:raise ValueError('Native validation missing '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Native map did not load')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.35':raise ValueError('Wrong candidate version')
    base=ROOT/'northstar/PhaseRunner.Preview'
    if json.loads((base/'mod.json').read_text())['Version']!='0.1.34':raise ValueError('Unexpected installed baseline')
    if digest(base/'mod/maps/mp_phase_runner_preview.bsp')!=digest(SOURCE):raise ValueError('Baseline map mismatch')
    current=read_lumps(bsp,(1,0x51,*range(0x6a,0x7a)))
    visibility=validate(current,current[0x51]);budget=audit(bsp)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Draw headroom insufficient')
    unchanged=[]
    for p in PACKAGE.rglob('*'):
        if p.is_file() and (p.relative_to(PACKAGE).parts[0]=='paks' or p.suffix in ('.mdl','.stbsp','.nut','.ent')):
            if digest(p)!=digest(base/p.relative_to(PACKAGE)):raise ValueError('Unexpected asset modification '+str(p))
            unchanged.append(p.relative_to(PACKAGE).as_posix())
    # Verify rollback's BSP and material bytes against the known installed base.
    with zipfile.ZipFile(rollback) as z:
        for rel in ('mod/maps/mp_phase_runner_preview.bsp','paks/phase_runner_world.rpak'):
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=digest(base/rel):raise ValueError('Rollback differs from baseline '+rel)
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md','INTERIOR_LIGHTING.md','VISIBILITY.md'):
        shutil.copy2(ROOT/doc,PACKAGE/doc)
    for name in ('pbr-audit.json','recovered-materials.json','ground-lighting-audit.json','texture-optimization.json','interior-lights.json'):
        shutil.copy2(base/name,PACKAGE/name)
    shutil.copy2(base/'runtime-validation.json',PACKAGE/'prior-lighting-validation.json')
    shutil.copy2(TARGET.with_name('local-visibility-audit.json'),PACKAGE/'local-visibility-audit.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner Northstar preview 0.1.35

Restart Northstar and load `map mp_phase_runner_preview`.

Sixteen native Titanfall visibility cells replace the single-cell prototype.
Forty-eight directed open connections provide conservative spatial portal
windows. Nearby geometry is protected from projected angle-based rejection
within each cell, covering both complete tunnel walkways and outdoor areas.
No opaque door/pipe blocker or Apex visibility data is used. All 4,561 meshes
remain reachable, with valid native index padding and 16.54% draw headroom.

The user-confirmed 0.1.34 lighting, optimized textures, full geometry, collision,
shadow geometry and both walkways are unchanged. Texture mips remain resident;
visibility portals do not implement spatial asset streaming.

Seven focused regressions and all 927 fresh native collision checks pass.
Client rendering and frame-rate improvement still need an in-game check.
Walk both pipes, turn through all view angles and inspect outside walls/fences
and small rocks. See VISIBILITY.md, local-visibility-audit.json and the runtime
validation reports for implementation evidence and limitations.
The complete confirmed-lighting 0.1.34 release is retained for rollback.
''')
    evidence=dict(version='0.1.35',bsp_sha256=digest(bsp),native_server_loaded=True,load_seconds=float(loading[1]),
        regression_tests=7,collision_checks=point+hull+clear,point_checks=point,player_hull_checks=hull,clearance_checks=clear,
        visibility=visibility,local_camera_domain=[[-12288,-12288,-4096],[12288,12288,4096]],
        all_tunnel_route_eye_positions_and_reported_outdoor_angles_cpu_checked=True,
        draw_budget=budget,draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100,
        native_index_pair_padding_preserved=True,original_collision_plane_prefix_preserved=True,
        draw_geometry_material_bindings_lightmaps_lights_shadow_geometry_collision_walkways_byte_preserved=True,
        unchanged_asset_hashes_verified=unchanged,prior_client_lighting_confirmed='0.1.34',
        prior_lighting_evidence='prior-lighting-validation.json',rollback_archive=rollback.name,
        client_rendering_verified=False,client_performance_verified=False,reported_failure_cause_confirmed=False,
        limitation='Open native spatial portals and conservative local camera coverage are a tested candidate. '
          'Dedicated loading does not exercise client PVS, view-angle rendering, GPU draw submission or frame rate. '
          'The exact original disappearance stage is not confirmed. Texture mips remain resident; no spatial starpak streaming is added.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (base,Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')):
        for p in PACKAGE.rglob('*'):
            if p.is_file():
                target=destination/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed hash mismatch '+rel)
    print(f'Installed 0.1.35; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.35.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive hash mismatch '+rel)
    print(json.dumps(dict(version='0.1.35',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,collision_checks=point+hull+clear,visibility=visibility),indent=2),flush=True)

if __name__=='__main__':finalize()
