"""Verify and install exact draw ordering with full prior backup and archive."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from repair_world_batch_order import ROOT,SOURCE,TARGET,BASE,PACKAGE
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.39-before-batch-order'

def finalize():
    for filename,count in (('world-batch-order-unit.log',6),('world-batch-native-capacity-unit.log',3)):
        log=(ROOT/'logs'/filename).read_text(encoding='utf-8-sig')
        if f'Ran {count} tests' not in log or '\nOK' not in log or 'FAILED' in log:
            raise ValueError('Regressions failed: '+filename)
    log=(ROOT/'logs/world-batch-order-0.1.40-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text());report=status['world_batch_order_repair']
    for name,count in status['catwalk_native_probes']['counts'].items():
        if f'Phase Runner catwalk {name} checks: {count}/{count} passed' not in log:
            raise ValueError('Missing native catwalk check '+name)
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing native check '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Map did not load')
    budget=enforce_camera_bypass_budget(TARGET)
    if budget['static_batch_runs']!=454:raise ValueError('Unexpected draw ordering')
    if digest(PACKAGE/'mod/maps/mp_phase_runner.bsp')!=digest(TARGET):raise ValueError('Candidate BSP mismatch')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.40':raise ValueError('Wrong candidate')
    for mod in (BASE,INSTALLED):
        if json.loads((mod/'mod.json').read_text())['Version']!='0.1.39':raise ValueError('Unexpected baseline')
        if digest(mod/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Baseline BSP differs')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.39.zip').is_file():raise ValueError('Prior archive missing')
    prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    if not BACKUP.exists():shutil.copytree(INSTALLED,BACKUP)
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Backup mismatch '+rel)
    (ROOT/'logs/old-0.1.39-backup-verification.json').write_text(json.dumps(dict(backup=str(BACKUP),files=prior),indent=2))
    print(f'Full 0.1.39 backup verified: {len(prior)} files.',flush=True)
    for doc in ('WORLD_BATCH_ORDER.md','VISIBILITY.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-playable-visibility-validation.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner 0.1.40

Restart Northstar and load `map mp_phase_runner`.

Fixes a native world draw-list cutoff by grouping existing mesh records into
454 material/channel batches, down from 3,777. Titanfall's draw list holds
2,048 batches. The old all-visible order omitted every new catwalk mesh.
All triangles, detail, UVs and material bindings are preserved exactly.
Visibility references and mesh bounds still address their original geometry.

Collision, catwalks/railings, working player lighting, surface lighting, PBR
materials, loading artwork and 13-language map names are preserved. Nine
regressions and native collision/catwalk checks pass. Final GPU appearance
and dynamic-light batch behavior still need an in-game check.

Full prior mod: output/installed-backups/PhaseRunner.Preview-0.1.39-before-batch-order
Prior archive: output/PhaseRunner.Preview-0.1.39.zip
The 0.1.36 original-path backup/archive remains preserved.
Backup paths are relative to the project root.
''',encoding='utf-8')
    evidence=dict(version='0.1.40',map_name='mp_phase_runner',bsp_sha256=digest(TARGET),native_server_loaded=True,
        load_seconds=float(loading[1]),regression_tests=9,existing_collision_checks=927,
        catwalk_checks=status['catwalk_native_probes']['counts'],batch_order=report,draw_budget=budget,
        old_full_backup=str(BACKUP),old_backup_files_verified=len(prior),
        prior_evidence='prior-playable-visibility-validation.json',
        prior_character_lighting_and_presentation_client_confirmed=True,
        client_geometry_verified=False,client_performance_verified=False,
        limitation='Native bytecode and draw-order checks confirm safe static submission. '
                   'Dedicated loading does not verify final GPU visibility or dynamic-light masks.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Install target escaped mod')
            if dest.exists() and rel.as_posix() in checks and prior.get(rel.as_posix())==checks[rel.as_posix()] and digest(dest)==checks[rel.as_posix()]:continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and os.path.samefile(source,dest):continue
            if destination==BASE and source.stat().st_size>10*1024*1024:
                if dest.exists():dest.unlink()
                os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed checksum mismatch '+rel)
    print(f'Installed 0.1.40; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.40.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive checksum mismatch '+rel)
    result=dict(version='0.1.40',map_name='mp_phase_runner',installed_files_verified=len(checks),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,
        prior_full_backup=str(BACKUP),prior_files_verified=len(prior),regression_tests=9,
        old_static_batches=report['before']['static_batch_runs'],new_static_batches=budget['static_batch_runs'],
        native_batch_capacity=2048,load_seconds=float(loading[1]),client_geometry_verified=False)
    (ROOT/'logs/world-batch-order-0.1.40-release.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
