"""Verify, snapshot, install and archive the 0.1.42 candidate."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from build_glass_console import ROOT,SOURCE,TARGET,BASE,PACKAGE
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.41-before-glass-console'

def finalize():
    for f,count in (('glass-console-unit.log',6),('glass-console-native-capacity-unit.log',3)):
        t=(ROOT/'logs'/f).read_text(encoding='utf-8-sig')
        if f'Ran {count} tests' not in t or '\nOK' not in t or 'FAILED' in t:raise ValueError('Checks failed '+f)
    log=(ROOT/'logs/glass-console-0.1.42-validation.log').read_text(encoding='utf-8-sig')
    for marker in ('floor checks: 102/102 passed','rail checks: 204/204 passed','route checks: 1449/1449 passed','route_floor checks: 1449/1449 passed','center truck checks: 3/3 passed','collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Native validation missing '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Load missing')
    for destination in (BASE,INSTALLED):
        if json.loads((destination/'mod.json').read_text())['Version']!='0.1.41' or digest(destination/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Unexpected current baseline')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.41.zip').is_file():raise ValueError('Prior archive missing')
    prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    for rel,sha in prior.items():
        dest=BACKUP/rel;dest.parent.mkdir(parents=True,exist_ok=True);source=BASE/rel
        if not dest.exists():
            if source.stat().st_size>10*1024*1024 and digest(source)==sha:os.link(source,dest)
            else:shutil.copy2(INSTALLED/rel,dest)
        if digest(dest)!=sha:raise ValueError('Backup mismatch '+rel)
    print(f'Full prior snapshot verified: {len(prior)} files.',flush=True)
    for filename in ('GLASS_CONSOLES.md','REMAINING_OBJECTS.md'):shutil.copy2(ROOT/filename,PACKAGE/filename)
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-center-detail-validation.json')
    inventory=json.loads((ROOT/'logs/remaining-props-material-audit.json').read_text())
    counts={k:inventory[k] for k in ('arena_static_placements','rendered_in_arena','unrendered_arena_placements','unrendered_arena_distinct_models','remaining_arena_categories')}
    budget=enforce_camera_bypass_budget(TARGET)
    evidence=dict(version='0.1.42',bsp_sha256=digest(TARGET),native_server_loaded=True,load_seconds=float(loading[1]),native_checks_passed=4134,
        regression_tests=9,draw_budget=budget,remaining_objects=counts,prior_full_backup=str(BACKUP),prior_files_verified=len(prior),
        client_appearance_verified=False,limitation='Dedicated validation cannot verify GPU glass appearance. Console dark glass uses its recovered primary blend layer. Baked lighting is retained.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    (PACKAGE/'README.md').write_text((ROOT/'GLASS_CONSOLES.md').read_text(),encoding='utf-8')
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe target')
            if dest.exists() and os.path.samefile(source,dest):continue
            if dest.exists() and digest(dest)==digest(source):continue
            # Always replace shared immutable files; never modify a snapshot's inode.
            if destination==BASE and source.stat().st_size>10*1024*1024:
                if dest.exists():dest.unlink()
                os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Install mismatch '+rel)
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Prior backup changed '+rel)
    print(f'Installed 0.1.42; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.42.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    result=dict(version='0.1.42',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        prior_full_backup=str(BACKUP),prior_files_verified=len(prior),archive_hashes_verified=True,regression_tests=9,
        native_checks_passed=4134,draw_batches=budget['static_batch_runs'],remaining_objects=counts,client_appearance_verified=False)
    (ROOT/'logs/glass-console-0.1.42-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
