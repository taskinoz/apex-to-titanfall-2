"""Verify fresh evidence, install the budget-safe diagnostic and archive it."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
ROOT=Path(__file__).resolve().parent

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def finalize():
    package=ROOT/'northstar/PhaseRunner.DrawBudgetTest'
    installed=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
    version=json.loads((package/'mod.json').read_text())['Version']
    if version!='0.1.29':raise ValueError('Unexpected release version')
    s=json.loads((package/'build-status.json').read_text())
    log=(ROOT/'logs/preview-0.1.29-final.log').read_text(encoding='utf-8-sig')
    unit=(ROOT/'logs/draw-budget-unit-0.1.29.log').read_text(encoding='utf-8-sig')
    native=(ROOT/'logs/native-draw-capacity-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 12 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Draw regression tests failed')
    if 'Ran 3 tests' not in native or '\nOK' not in native:raise ValueError('Native capacity tests failed')
    point=len(s['collision_probes']);hull=len(s['pilot_hull_contact_probes']);clear=len(s['hull_clearance_probes'])
    for message in (f'Phase Runner collision probes: {point}/{point} hit',f'Phase Runner prop hull probes: {hull}/{hull} hit',f'Phase Runner edge clearance probes: {clear}/{clear} clear'):
        if message not in log:raise ValueError('Incomplete fresh engine evidence: '+message)
    contacts=re.findall(r'prop hull probe (\d+): fraction=([0-9.]+) startSolid=(\w+)',log)
    if len(contacts)!=hull or any(float(f)>=1 or solid!='false' for _,f,solid in contacts):raise ValueError('Player contacts did not start clear')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Server did not finish loading')
    bsp=package/'mod/maps/mp_phase_runner_preview.bsp';budget=audit(bsp)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Insufficient draw headroom')
    build=s['world_draw_budget_repair']
    if not build['original_collision_position_buffer_prefix_byte_identical'] or not build['compaction']['unchanged_lumps_byte_verified']:raise ValueError('Collision preservation failed')
    # Confirm every existing GPU asset and streaming catalog matches the exact
    # working rollback package; only the draw BSP and release evidence differ.
    base=ROOT/'output/phase-runner/rollback-0.1.27/PhaseRunner.Preview'
    asset_files=[]
    for p in package.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(package)
        if rel.parts[0]=='paks' or p.suffix in ('.mdl','.stbsp','.ent','.nut'):
            if digest(p)!=digest(base/rel):raise ValueError('Existing asset changed: '+str(rel))
            asset_files.append(str(rel))
    evidence=dict(version=version,bsp_sha256=digest(bsp),dedicated_server_loaded=True,
        load_seconds=float(loading.group(1)),point_contact_checks=point,
        clear_start_player_hull_contact_checks=hull,clearance_checks=clear,
        draw_regression_checks=12,native_capacity_regression_checks=3,draw_budget=budget,
        recovered_placements=build['all_restored_placements'],collision_byte_preserved_from='0.1.27',
        existing_assets_byte_verified=asset_files,render_detail='fixed source lower LOD plus component-anchored reduction',
        client_rendering_verified=False,client_movement_verified=False,tunnel_barriers_resolved=False,
        limitation='The all-visible draw budget now fits, with 28.9 percent headroom. '
            'This does not prove that the budget caused the reported camera-angle pop-in. '
            'Actual client rendering remains unverified. Full-detail collision is preserved; '
            'reduced render detail can differ from it. Material approximations and invisible '
            'tunnel barriers remain unfinished.')
    (package/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={str(p.relative_to(package)).replace('\\','/'):digest(p) for p in package.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (package/'checksums.json').write_text(json.dumps(checks,indent=2))
    for p in package.rglob('*'):
        if p.is_file():
            target=installed/p.relative_to(package);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    for rel,sha in checks.items():
        if digest(installed/rel)!=sha:raise ValueError('Installed mismatch: '+rel)
    canonical=ROOT/'northstar/PhaseRunner.Preview'
    for p in package.rglob('*'):
        if p.is_file():
            target=canonical/p.relative_to(package);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    print(f'Installed {version}; {len(checks)} files verified; {point+hull+clear} native collision checks passed.',flush=True)
    archive=ROOT/f'output/PhaseRunner.Preview-{version}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in package.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(package))
    with zipfile.ZipFile(archive) as z:
        for rel,expected in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=expected:raise ValueError('Archive mismatch: '+rel)
    print(json.dumps(dict(version=version,installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,draw_budget=budget,client_rendering_verified=False),indent=2))

if __name__=='__main__':finalize()
