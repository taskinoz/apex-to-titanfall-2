"""Promote the shader repair only after actual client loading and reload pass."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from repair_art_supports_loading import ROOT,PACKAGE
from finalize_lighting_release import digest
BASE=ROOT/'northstar/PhaseRunner.Preview'
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.42-before-art-supports'

def finalize():
    tests=0
    for f,count in (('art-supports-unit.log',7),('art-supports-native-capacity-unit.log',3),('art-supports-loading-unit.log',4)):
        t=(ROOT/'logs'/f).read_text(encoding='utf-8-sig')
        if f'Ran {count} tests' not in t or '\nOK' not in t or 'FAILED' in t:raise ValueError('Checks failed '+f)
        tests+=count
    log=(ROOT/'logs/client-loading-0.1.44-transition.log').read_text(encoding='utf-8-sig')
    markers=('floor checks: 102/102 passed','rail checks: 204/204 passed','route checks: 1449/1449 passed','route_floor checks: 1449/1449 passed','center truck checks: 3/3 passed','art support checks: 22/22 passed','collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear')
    for marker in markers:
        if log.count(marker)<2:raise ValueError('Two client map validations missing '+marker)
    if log.count('UICodeCallback_LevelLoadingFinished: mp_phase_runner (false)')<2 or 'UICodeCallback_LevelLoadingFinished: mp_lobby (false)' not in log:raise ValueError('Client level completion missing')
    if 'PHASE RUNNER CLIENT TRANSITION PASSED: map -> lobby -> map' not in log:raise ValueError('Transition completion missing')
    if any(x in log for x in ('COMPILE ERROR','SCRIPT ERROR','PHASE RUNNER CLIENT TRANSITION FAILED')):raise ValueError('Client script failure')
    expected={p.relative_to(BACKUP).as_posix():digest(p) for p in BACKUP.rglob('*') if p.is_file()}
    for destination in (BASE,INSTALLED):
        if json.loads((destination/'mod.json').read_text())['Version']!='0.1.42':raise ValueError('Unexpected baseline')
        for rel,sha in expected.items():
            if digest(destination/rel)!=sha:raise ValueError('Working baseline changed '+rel)
    print(f'Working baseline and full fallback verified: {len(expected)} files.',flush=True)
    prior=json.loads((ROOT/'logs/art-supports-0.1.43-release.json').read_text())
    evidence=json.loads((PACKAGE/'runtime-validation.json').read_text())
    evidence.update(version='0.1.44',regression_tests=tests,client_map_loading_verified=True,client_reload_verified=True,
        client_validation_route=['mp_phase_runner','mp_lobby','mp_phase_runner'],client_map_collision_checks=4156,
        client_appearance_verified=False,client_log='logs/client-loading-0.1.44-transition.log',
        client_load_seconds=[float(x) for x in re.findall(r'loading took ([0-9.]+)s',log)],
        limitation='Loading and map/lobby reload tested in a live isolated client. Appearance at the reported coordinates remains unverified.',
        loading_repair=json.loads((PACKAGE/'loading-repair.json').read_text()))
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());status['loading_repair_release']=evidence['loading_repair'];status['client_loading_validation']=dict(version='0.1.44',client_map_loading_verified=True,client_reload_verified=True);(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(ROOT/'LOADING_REPAIR.md',PACKAGE/'LOADING_REPAIR.md');shutil.copy2(ROOT/'LOADING_REPAIR.md',PACKAGE/'README.md')
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe target')
            if dest.exists() and os.path.samefile(source,dest):continue
            if dest.exists() and digest(dest)==digest(source):continue
            if dest.exists():dest.unlink()
            if destination==BASE and source.stat().st_size>10*1024*1024:os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed file mismatch '+rel)
    for rel,sha in expected.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Fallback snapshot changed '+rel)
    shutil.copy2(PACKAGE/'REMAINING_OBJECTS.md',ROOT/'REMAINING_OBJECTS.md')
    print(f'Installed 0.1.44; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.44.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    result=dict(version='0.1.44',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        fallback_full_backup=str(BACKUP),fallback_files_verified=len(expected),failed_candidate_preserved=prior['archive'],
        archive_hashes_verified=True,regression_tests=tests,native_checks_passed=4156,client_map_loading_verified=True,client_reload_verified=True,
        client_appearance_verified=False)
    (ROOT/'logs/art-supports-loading-0.1.44-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
