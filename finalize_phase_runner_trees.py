"""Back up 0.1.44 and promote the tree pass only after regression and client checks."""
import collections,hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from build_phase_runner_trees import ROOT,BASE,PACKAGE,OUT,TARGET,VERSION
from finalize_lighting_release import digest
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.44-before-trees'
LOG=ROOT/'logs/client-loading-0.1.45-transition.log'

def finalize():
    tests=(ROOT/'logs/tree-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 9 tests' not in tests or '\nOK' not in tests or 'FAILED' in tests:raise ValueError('Tree regression checks failed')
    log=LOG.read_text(encoding='utf-8-sig')
    markers=('floor checks: 102/102 passed','rail checks: 204/204 passed','route checks: 1449/1449 passed','route_floor checks: 1449/1449 passed','center truck checks: 3/3 passed','art support checks: 22/22 passed','tree checks: 40/40 passed','collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear')
    for marker in markers:
        if log.count(marker)<2:raise ValueError('Two successful client validations missing '+marker)
    if log.count('UICodeCallback_LevelLoadingFinished: mp_phase_runner (false)')<2 or 'UICodeCallback_LevelLoadingFinished: mp_lobby (false)' not in log or 'PHASE RUNNER CLIENT TRANSITION PASSED: map -> lobby -> map' not in log:raise ValueError('Client loading/reload incomplete')
    if any(s in log for s in ('COMPILE ERROR','SCRIPT ERROR','PHASE RUNNER CLIENT TRANSITION FAILED')):raise ValueError('Client script error')
    report=json.loads((OUT/'trees.json').read_text());prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    for destination in (BASE,INSTALLED):
        if json.loads((destination/'mod.json').read_text())['Version']!='0.1.44':raise ValueError('Unexpected active version')
        if digest(destination/'mod/maps/mp_phase_runner.bsp')!=report['source_bsp_sha256']:raise ValueError('Baseline BSP changed')
        for rel,sha in prior.items():
            if digest(destination/rel)!=sha:raise ValueError('Baseline file mismatch '+rel)
    for rel,sha in prior.items():
        dest=BACKUP/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            src=BASE/rel
            if src.stat().st_size>10*1024*1024 and src.suffix in ('.bsp','.stbsp','.rpak'):os.link(src,dest)
            else:shutil.copy2(src,dest)
        if digest(dest)!=sha:raise ValueError('Backup mismatch '+rel)
    print(f'Complete 0.1.44 fallback verified: {len(prior)} files.',flush=True)
    old=json.loads((ROOT/'logs/art-supports-remaining-objects.json').read_text());restored={p['index'] for p in report['source_placements']};remaining=[p for p in old['remaining_placements'] if p['index'] not in restored]
    if len(old['remaining_placements'])-len(remaining)!=20:raise ValueError('Recovery count mismatch')
    categories=collections.Counter(p['model'].split('/')[1] for p in remaining)
    counts=dict(arena_static_placements=old['arena_static_placements'],rendered_in_arena=old['rendered_in_arena']+20,unrendered_arena_placements=len(remaining),unrendered_arena_distinct_models=len({p['model'] for p in remaining}),remaining_arena_categories=dict(categories))
    (ROOT/'logs/tree-remaining-objects.json').write_text(json.dumps(dict(version=VERSION,**counts,remaining_placements=remaining,restored_this_release=sorted(restored)),indent=2))
    remaining_doc=f"# Remaining source objects after {VERSION}\n\nThe map renders {counts['rendered_in_arena']:,} of {counts['arena_static_placements']:,} arena static prop placements.\n{len(remaining):,} placements across {counts['unrendered_arena_distinct_models']} model types remain omitted.\n{categories['foliage']:,} are vegetation and {len(remaining)-categories['foliage']:,} are other categories.\nThis release restores twenty original acacia placements. The 486 placements\noutside the imported arena and dynamic entities remain separate inventories.\n\nAudit: `logs/tree-remaining-objects.json`.\n"
    (PACKAGE/'REMAINING_OBJECTS.md').write_text(remaining_doc)
    shutil.copy2(ROOT/'TREE_DETAILS.md',PACKAGE/'TREE_DETAILS.md');shutil.copy2(ROOT/'TREE_DETAILS.md',PACKAGE/'README.md')
    evidence=dict(version=VERSION,bsp_sha256=digest(TARGET),native_server_loaded=True,native_checks_passed=4196,regression_tests=9,draw_budget=report['budget'],remaining_objects=counts,prior_full_backup=str(BACKUP),prior_files_verified=len(prior),restored_placements=20,client_map_loading_verified=True,client_reload_verified=True,client_validation_route=['mp_phase_runner','mp_lobby','mp_phase_runner'],client_map_collision_checks=4196,client_log=str(LOG.relative_to(ROOT)),client_load_seconds=[float(s) for s in re.findall(r'loading took ([0-9.]+)s',log)],client_appearance_verified=False,limitation='Actual client loading/reload and native trunk traces verified. Visual appearance needs in-game review; static opacity-aware canopy shadow baking is deferred.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2));status=json.loads((PACKAGE/'build-status.json').read_text());status['client_loading_validation']=evidence;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'};(PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for src in PACKAGE.rglob('*'):
            if not src.is_file():continue
            rel=src.relative_to(PACKAGE);dest=destination/rel
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Unsafe destination')
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and digest(dest)==digest(src):continue
            if dest.exists():dest.unlink()
            if destination==BASE and src.stat().st_size>10*1024*1024 and src.suffix in ('.bsp','.stbsp','.rpak'):os.link(src,dest)
            else:shutil.copy2(src,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed file mismatch '+rel)
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Fallback changed '+rel)
    shutil.copy2(PACKAGE/'REMAINING_OBJECTS.md',ROOT/'REMAINING_OBJECTS.md');print(f'Installed {VERSION}; verified {len(checks)} files.',flush=True)
    archive=ROOT/f'output/PhaseRunner.Preview-{VERSION}.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive mismatch '+rel)
    result=dict(version=VERSION,installed_files_verified=len(checks),archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,prior_full_backup=str(BACKUP),prior_files_verified=len(prior),regression_tests=9,native_checks_passed=4196,client_map_loading_verified=True,client_reload_verified=True,client_appearance_verified=False,tree_placements=20,tree_triangles=5780,world_index_percent=100*report['budget']['native_padded_indices']/report['budget']['world_index_capacity'])
    (ROOT/'logs/tree-0.1.45-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
