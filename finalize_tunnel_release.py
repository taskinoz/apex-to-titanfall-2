"""Verify final tunnel evidence, install the mod and hash-check its archive."""
import hashlib,json,re,shutil,zipfile
from pathlib import Path
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'northstar/PhaseRunner.TunnelRelease'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner_preview.bsp';source=ROOT/'output/phase-runner/preview-tunnel-walkways/mp_phase_runner_preview.bsp'
    if digest(bsp)!=digest(source):raise ValueError('Release differs from validated BSP')
    status=json.loads((PACKAGE/'build-status.json').read_text());mod=json.loads((PACKAGE/'mod.json').read_text())
    if mod['Version']!='0.1.30':raise ValueError('Incorrect version')
    log=(ROOT/'logs/tunnel-0.1.30-validation.log').read_text(encoding='utf-8-sig')
    for name in ('tunnel-detail-unit.log','tunnel-collision-unit.log','tunnel-walkway-unit.log'):
        unit=(ROOT/'logs'/name).read_text(encoding='utf-8-sig')
        if 'Ran 6 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Failed regression '+name)
    point=len(status['collision_probes']);hull=len(status['pilot_hull_contact_probes']);clear=len(status['hull_clearance_probes'])
    for m in (f'Phase Runner collision probes: {point}/{point} hit',f'Phase Runner prop hull probes: {hull}/{hull} hit',f'Phase Runner edge clearance probes: {clear}/{clear} clear'):
        if m not in log:raise ValueError('Missing engine evidence '+m)
    result=re.search(r'walkway traversal: (\d+)/(\d+) clear; floors=(\d+)',log)
    if not result or not result[1]==result[2]==result[3]:raise ValueError('Incomplete walkway traversal/floors')
    count=int(result[1]);expected=len(json.loads((ROOT/'logs/tunnel-walkway-route-probes.json').read_text()))
    if count!=expected or count<1000 or 'route obstruction' in log or 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Route validation failed')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Map failed to load')
    contacts=re.findall(r'prop hull probe (\d+): fraction=([0-9.]+) startSolid=(\w+)',log)
    if len(contacts)!=hull or any(float(f)>=1 or solid!='false' for _,f,solid in contacts):raise ValueError('Player contacts failed')
    budget=audit(bsp)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Draw budget exceeded')
    base=ROOT/'northstar/PhaseRunner.Preview';assets=[]
    for p in PACKAGE.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(PACKAGE)
        if rel.parts[0]=='paks' or p.suffix in ('.mdl','.stbsp','.ent','.nut'):
            if digest(p)!=digest(base/rel):raise ValueError('Unintended asset change '+str(rel))
            assets.append(str(rel))
    evidence=dict(version='0.1.30',bsp_sha256=digest(bsp),dedicated_server_loaded=True,load_seconds=float(loading[1]),
        point_contact_checks=point,clear_start_player_hull_contact_checks=hull,existing_clearance_checks=clear,
        walkway_segments=count,bidirectional_walkway_sweeps=count*2,walkway_floor_contacts=count,
        player_hull=[[-16,-16,0],[16,16,72]],step_height=18,walkway_routes=2,regression_tests=18,
        draw_budget=budget,draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100,
        existing_assets_byte_verified=assets,prior_client_rendering_confirmed_version='0.1.29',
        client_rendering_verified=False,client_movement_verified=False,
        limitation='Dedicated hull sweeps and floor contacts sample both complete new walkway centerlines. '
            'This does not prove every off-center movement, grapple, or client view. New metal walkways are '
            'Titanfall traversal adaptations. Original source physics remains outside deliberately opened '
            'tool-material apertures and replaced portal-frame hulls. Original shaders, final lighting and '
            'full spatial texture streaming remain unfinished.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={str(p.relative_to(PACKAGE)).replace('\\','/'):digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    installed=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
    for targetroot in (installed,base):
        for p in PACKAGE.rglob('*'):
            if p.is_file():target=targetroot/p.relative_to(PACKAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for rel,sha in checks.items():
            if digest(targetroot/rel)!=sha:raise ValueError('Installed mismatch '+str(targetroot/rel))
    print(f'Installed 0.1.30; {len(checks)} file hashes verified; {count} walkway segments clear in both directions.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.30.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    print(json.dumps(dict(version='0.1.30',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,
        walkway_segments=count,existing_collision_checks=point+hull+clear,draw_headroom_percent=evidence['draw_headroom_percent']),indent=2),flush=True)

if __name__=='__main__':finalize()
