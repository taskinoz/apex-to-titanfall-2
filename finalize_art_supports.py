"""Verify, preserve the full 0.1.42 snapshot, install and archive 0.1.43."""
import collections,hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from build_art_supports import ROOT,SOURCE,TARGET,BASE,PACKAGE,SUPPORTS
from finalize_lighting_release import digest
from audit_world_draw_budget import enforce_camera_bypass_budget
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.42-before-art-supports'

def inventory():
    old=json.loads((ROOT/'logs/remaining-props-material-audit.json').read_text())
    restored=set(SUPPORTS);missing=[p for p in old['remaining_placements'] if p['index'] not in restored]
    removed=len(old['remaining_placements'])-len(missing)
    if removed!=22:raise ValueError('Unexpected restored placement inventory')
    cats=collections.Counter(p['model'].split('/')[1] for p in missing)
    counts=dict(arena_static_placements=old['arena_static_placements'],rendered_in_arena=old['rendered_in_arena']+removed,
        unrendered_arena_placements=len(missing),unrendered_arena_distinct_models=len({p['model'] for p in missing}),remaining_arena_categories=dict(cats))
    proof=dict(version='0.1.43',**counts,remaining_placements=missing,restored_this_release=sorted(restored))
    (ROOT/'logs/art-supports-remaining-objects.json').write_text(json.dumps(proof,indent=2))
    (PACKAGE/'REMAINING_OBJECTS.md').write_text(f"# Remaining source objects after 0.1.43\n\nThe map renders {counts['rendered_in_arena']:,} of {counts['arena_static_placements']:,} arena static prop placements.\n{len(missing):,} placements across {counts['unrendered_arena_distinct_models']} model types remain omitted.\nOf these, {cats['foliage']:,} are vegetation and {len(missing)-cats['foliage']:,} are other categories,\nincluding decals, water and test objects. The 486 placements outside the imported\narena are excluded. Dynamic entities are inventoried separately.\n\nThis release restores 22 omitted freight/fence placements. The two rebuilt pipes\nwere already rendered, so they do not increase this count.\n\nAudit: `logs/art-supports-remaining-objects.json`.\n",encoding='utf-8')
    return counts

def finalize():
    for f,count in (('art-supports-unit.log',7),('art-supports-native-capacity-unit.log',3)):
        t=(ROOT/'logs'/f).read_text(encoding='utf-8-sig')
        if f'Ran {count} tests' not in t or '\nOK' not in t or 'FAILED' in t:raise ValueError('Checks failed '+f)
    log=(ROOT/'logs/art-supports-0.1.43-validation.log').read_text(encoding='utf-8-sig')
    for marker in ('floor checks: 102/102 passed','rail checks: 204/204 passed','route checks: 1449/1449 passed','route_floor checks: 1449/1449 passed','center truck checks: 3/3 passed','art support checks: 22/22 passed','collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Native validation missing '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Load missing')
    sourcehash=digest(SOURCE)
    for destination in (BASE,INSTALLED):
        if json.loads((destination/'mod.json').read_text())['Version']!='0.1.42' or digest(destination/'mod/maps/mp_phase_runner.bsp')!=sourcehash:raise ValueError('Unexpected current baseline')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.42.zip').is_file():raise ValueError('Prior archive missing')
    prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    for rel,sha in prior.items():
        dest=BACKUP/rel;dest.parent.mkdir(parents=True,exist_ok=True);source=BASE/rel
        if not dest.exists():
            if source.stat().st_size>10*1024*1024 and digest(source)==sha:os.link(source,dest)
            else:shutil.copy2(INSTALLED/rel,dest)
        if digest(dest)!=sha:raise ValueError('Backup mismatch '+rel)
    print(f'Full prior snapshot verified: {len(prior)} files.',flush=True)
    shutil.copy2(ROOT/'ART_SUPPORTS.md',PACKAGE/'ART_SUPPORTS.md')
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-glass-console-validation.json')
    counts=inventory();budget=enforce_camera_bypass_budget(TARGET)
    evidence=dict(version='0.1.43',bsp_sha256=digest(TARGET),native_server_loaded=True,load_seconds=float(loading[1]),native_checks_passed=4156,
        regression_tests=10,draw_budget=budget,remaining_objects=counts,prior_full_backup=str(BACKUP),prior_files_verified=len(prior),
        restored_placements=22,rebuilt_pipe_placements=2,client_appearance_verified=False,limitation='Dedicated validation cannot verify GPU appearance. Sewer-wall specular uses a neutral fallback. Existing lightmaps and collision are retained.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    (PACKAGE/'README.md').write_text((ROOT/'ART_SUPPORTS.md').read_text(),encoding='utf-8')
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe target')
            if dest.exists() and os.path.samefile(source,dest):continue
            if dest.exists() and digest(dest)==digest(source):continue
            if destination==BASE and source.stat().st_size>10*1024*1024:
                if dest.exists():dest.unlink()
                os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Install mismatch '+rel)
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Prior backup changed '+rel)
    print(f'Installed 0.1.43; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.43.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    result=dict(version='0.1.43',installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,
        prior_full_backup=str(BACKUP),prior_files_verified=len(prior),archive_hashes_verified=True,regression_tests=10,
        native_checks_passed=4156,draw_batches=budget['static_batch_runs'],remaining_objects=counts,client_appearance_verified=False)
    (ROOT/'logs/art-supports-0.1.43-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
