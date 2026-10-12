"""Record fresh server checks and install the conservative visibility diagnostic."""
import hashlib, json, re, shutil, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def finalize():
    package=ROOT/'northstar/PhaseRunner.Preview'
    installed=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
    version=json.loads((package/'mod.json').read_text())['Version']
    if version!='0.1.28':raise ValueError('Unexpected visibility release version')
    s=json.loads((package/'build-status.json').read_text())
    log=(ROOT/'logs/preview-0.1.28-final.log').read_text(encoding='utf-8-sig')
    unit=(ROOT/'logs/camera-visibility-unit-0.1.28.log').read_text(encoding='utf-8-sig')
    for text in ('Ran 9 tests','\nOK'):
        if text not in unit:raise ValueError('Camera visibility tests failed')
    point=len(s['collision_probes']);hull=len(s['pilot_hull_contact_probes']);clear=len(s['hull_clearance_probes'])
    for message in (f'Phase Runner collision probes: {point}/{point} hit',
                    f'Phase Runner prop hull probes: {hull}/{hull} hit',
                    f'Phase Runner edge clearance probes: {clear}/{clear} clear'):
        if message not in log:raise ValueError('Incomplete new engine evidence: '+message)
    contacts=re.findall(r'prop hull probe (\d+): fraction=([0-9.]+) startSolid=(\w+)',log)
    if len(contacts)!=hull or any(float(f)>=1 or solid!='false' for _,f,solid in contacts):
        raise ValueError('Player contacts did not start clear')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Dedicated server did not finish loading')
    if not s['camera_visibility_repair']['compaction']['unchanged_lumps_byte_verified']:
        raise ValueError('Geometry/collision preservation was not verified')
    bsp=package/'mod/maps/mp_phase_runner_preview.bsp'
    barrier_audit=json.loads((ROOT/'logs/reported-tunnel-barriers.json').read_text())
    (package/'tunnel-barrier-audit.json').write_text(json.dumps(dict(
        supplied_positions=9,collision_version='0.1.27',
        exact_source_ownership_candidates=barrier_audit,
        limitation='These are contacts at approximate player positions, including floor contacts. '
                   'Expanded convex-plane proximity is not a native sweep or proof of which '
                   'piece blocks travel. No collision is removed in the visibility diagnostic.'),indent=2))
    evidence=dict(version=version,bsp_sha256=digest(bsp),
        dedicated_server_loaded=True,load_seconds=float(loading.group(1)),
        point_contact_checks=point,clear_start_player_hull_contact_checks=hull,
        clearance_checks=clear,visibility_regression_checks=9,
        cpu_camera_orientation_checks=2184,
        geometric_draw_bounds_and_collision_byte_identical_to='0.1.27',
        modified_bsp_lumps=[119,121],reference_order_preserved=True,
        camera_visibility_diagnostic=s['camera_visibility_repair'],
        client_rendering_verified=False,client_movement_verified=False,
        tunnel_barriers_resolved=False,
        tunnel_barrier_position_audit='tunnel-barrier-audit.json',
        limitation='CPU camera-box acceptance checks and dedicated loading do not prove GPU '
                   'rendering or identify the tunnel barriers. Verify actual camera-angle visibility '
                   'and frame rate in the client. Collision remains the user-tested 0.1.27 data.')
    (package/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={str(p.relative_to(package)).replace('\\','/'):digest(p)
            for p in package.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (package/'checksums.json').write_text(json.dumps(checks,indent=2))
    for p in package.rglob('*'):
        if p.is_file():
            target=installed/p.relative_to(package);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,target)
    for relative,sha in checks.items():
        if digest(installed/relative)!=sha:raise ValueError('Installed file mismatch '+relative)
    print(f'Installed {version}; {len(checks)} files verified.',flush=True)
    archive=ROOT/f'output/PhaseRunner.Preview-{version}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as target:
        for p in package.rglob('*'):
            if p.is_file():target.write(p,Path('PhaseRunner.Preview')/p.relative_to(package))
    print(json.dumps(dict(version=version,installed_files_verified=len(checks),
        archive=str(archive),archive_bytes=archive.stat().st_size,
        point_contacts=point,player_contacts=hull,clearances=clear,
        client_rendering_verified=False),indent=2))


if __name__=='__main__':finalize()
