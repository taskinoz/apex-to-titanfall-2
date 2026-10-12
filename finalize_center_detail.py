"""Install the verified prop pass with an immutable verified prior snapshot."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from build_center_detail import ROOT,SOURCE,TARGET,BASE,PACKAGE,MATERIALS
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.40-before-center-detail'

def finalize():
    for filename,count in (('center-detail-unit.log',8),('center-detail-native-capacity-unit.log',3)):
        text=(ROOT/'logs'/filename).read_text(encoding='utf-8-sig')
        if f'Ran {count} tests' not in text or '\nOK' not in text or 'FAILED' in text:raise ValueError('Failed checks '+filename)
    log=(ROOT/'logs/center-detail-0.1.41-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text());report=status['center_detail_release']
    for name,count in status['catwalk_native_probes']['counts'].items():
        if f'Phase Runner catwalk {name} checks: {count}/{count} passed' not in log:raise ValueError('Missing catwalk check '+name)
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear','center truck checks: 3/3 passed'):
        if marker not in log:raise ValueError('Missing native check '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script failure')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Map load not proven')
    budget=enforce_camera_bypass_budget(TARGET)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.9 or budget['static_batch_runs']>=512:raise ValueError('Draw safety margin exceeded')
    if digest(PACKAGE/'mod/maps/mp_phase_runner.bsp')!=digest(TARGET):raise ValueError('Candidate mismatch')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.41':raise ValueError('Wrong package')
    for mod in (BASE,INSTALLED):
        if json.loads((mod/'mod.json').read_text())['Version']!='0.1.40' or digest(mod/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Wrong confirmed baseline')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.40.zip').is_file():raise ValueError('Prior archive missing')
    prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    # Large immutable workspace copies are already identical to the installed
    # files. Link those into the snapshot, copy the editable metadata, and verify
    # every byte. Installation below replaces large files rather than editing
    # their shared storage, so the previous source and snapshot remain intact.
    for rel,sha in prior.items():
        target=BACKUP/rel;canonical=BASE/rel;installed=INSTALLED/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            if installed.stat().st_size>10*1024*1024 and canonical.is_file() and digest(canonical)==sha:os.link(canonical,target)
            else:shutil.copy2(installed,target)
        if digest(target)!=sha:raise ValueError('Old snapshot mismatch '+rel)
    (ROOT/'logs/old-0.1.40-backup-verification.json').write_text(json.dumps(dict(backup=str(BACKUP),files=prior,verified=True),indent=2))
    print(f'Full 0.1.40 snapshot verified: {len(prior)} files.',flush=True)
    for doc in ('CENTER_DETAIL.md','ART_TODO.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    shutil.copy2(TARGET.parent/'nessie-support-proof.json',PACKAGE/'nessie-support-proof.json')
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-batch-order-validation.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner 0.1.41

Restart Northstar and load `map mp_phase_runner`.

Restores the original three closed police trucks and 206 small rock clusters
around the center and Nessie. Nessie uses its original unsimplified 1,442-triangle
LOD0, up from 59 triangles. The truck beneath it also uses LOD0 so its hood
supports the original doll placement; the two center trucks use authored LOD2.
All source positions, angles, scales and UVs are retained.

The original truck hulls collide. The small decorative rock clusters retain
their original non-solid setting. New source props have separate sun/sky/local
lightmaps, smooth source normals, correct tangents and recovered PBR materials.
Existing lightmaps, player lighting, catwalks, loading art and map names remain
intact. Original skybox/portal records and the confirmed camera guards remain.

The map submits all 4,817 meshes in 463 static draw batches. Native index use
stays below 90 percent capacity. Client appearance and performance need checking.
Eight preservation/source/budget tests and three native capacity tests pass.
The native server passes the existing 4,131 checks and three new truck checks.
One diagnostic start moved above the restored truck; its Nessie target is intact.

Full prior snapshot: output/installed-backups/PhaseRunner.Preview-0.1.40-before-center-detail
Prior archive: output/PhaseRunner.Preview-0.1.40.zip
The 0.1.36 original-path backup/archive remains available.
Backup paths are relative to the project root. See CENTER_DETAIL.md for details.
''',encoding='utf-8')
    # Record measured counts rather than relying on prose's approximate planning.
    readme=(PACKAGE/'README.md').read_text().replace('4,817 meshes in 463',f"{budget['meshes']:,} meshes in {budget['static_batch_runs']}")
    (PACKAGE/'README.md').write_text(readme,encoding='utf-8')
    evidence=dict(version='0.1.41',map_name='mp_phase_runner',bsp_sha256=digest(TARGET),native_server_loaded=True,
        load_seconds=float(loading[1]),regression_tests=11,existing_native_checks=4131,new_truck_checks=3,draw_budget=budget,
        restored_trucks=3,restored_small_rockclusters=206,nessie_triangles_before=59,nessie_triangles_after=1442,
        prior_client_confirmed_version='0.1.40',prior_client_report='Solid version; no pop-in or pop-out.',
        full_prior_backup=str(BACKUP),old_backup_files_verified=len(prior),native_probe_adjustment=report['native_probe_adjustment'],
        client_geometry_verified=False,client_performance_verified=False,
        limitation='Dedicated validation cannot verify GPU appearance. New props have separate lightmaps; existing surface/probe lightmaps remain intact. Truck windows use the native opaque world-shader approximation. Small rock clusters retain original non-solid flags.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Install escaped mod')
            if dest.exists() and prior.get(rel.as_posix())==checks.get(rel.as_posix()) and digest(dest)==checks[rel.as_posix()]:continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and os.path.samefile(source,dest):continue
            if destination==BASE and source.stat().st_size>10*1024*1024:
                if dest.exists():dest.unlink()
                os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed mismatch '+rel)
    # Verify the immutable snapshot again after replacing the canonical files.
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Prior snapshot was modified '+rel)
    print(f'Installed 0.1.41; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.41.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    result=dict(version='0.1.41',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_hashes_verified=True,prior_full_backup=str(BACKUP),prior_files_verified=len(prior),regression_tests=11,
        native_checks_passed=4134,draw_batches=budget['static_batch_runs'],index_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100,
        client_geometry_verified=False)
    (ROOT/'logs/center-detail-0.1.41-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
