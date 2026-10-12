"""Verify native evidence, preserve the prior install, package and install the release."""
import hashlib,json,os,re,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT/'northstar/PhaseRunner'
DOC=ROOT/'docs/conversion'
RUN=ROOT/'test-harness/output/20261006-125249'
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.46-before-release'
MARKERS=('floor checks: 102/102 passed','rail checks: 204/204 passed','route checks: 1449/1449 passed','route_floor checks: 1449/1449 passed','center truck checks: 3/3 passed','art support checks: 22/22 passed','tree checks: 40/40 passed','collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear')

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def safe_copy(src,dest,root):
    if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Destination escaped package')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and digest(src)==digest(dest):return
    # Unlink before replacing: historical packages may use hard links.
    if dest.exists():dest.unlink()
    shutil.copy2(src,dest)

def zip_checked(path,files):
    expected={}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for src,name in files:
            z.write(src,name);expected[name]=digest(src)
    with zipfile.ZipFile(path) as z:
        if set(z.namelist())!=set(expected):raise ValueError('ZIP membership mismatch')
        for name,sha in expected.items():
            h=hashlib.sha256()
            with z.open(name) as f:
                for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
            if h.hexdigest()!=sha:raise ValueError('ZIP hash mismatch: '+name)
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=digest(path),verified_files=len(expected))

def finalize():
    tests=(ROOT/'logs/release-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in tests or '\nOK' not in tests or 'FAILED' in tests:raise ValueError('Regression tests incomplete')
    native=(RUN/'game.log').read_text(encoding='utf-8-sig')
    if 'SCRIPT ERROR' in native or 'COMPILE ERROR' in native or 'Northstar has crashed!' in native:raise ValueError('Native validation errors')
    for m in MARKERS:
        if native.count(m)<3:raise ValueError('Expected launch, reload, return checks: '+m)
    for f,mapname in [('release-stock-switch.log','mp_coliseum'),('release-return-switch.log','mp_phase_runner')]:
        result=json.loads((ROOT/'logs'/f).read_text(encoding='utf-8-sig'))
        if not all(result['contexts'][c]['level']==mapname and result['contexts'][c]['ready'] for c in ('ui','server','client')):raise ValueError('Switch incomplete')
    route=json.loads((RUN/'route-result.json').read_text())
    if len(route['captures'])!=6 or route['logs']['script_errors']:raise ValueError('Screenshot route incomplete')
    current_version=json.loads((INSTALLED/'mod.json').read_text())['Version']
    if current_version not in ('0.1.46','1.0.0'):raise ValueError('Unexpected installed baseline')
    baseline=INSTALLED if current_version=='0.1.46' else BACKUP
    if not (baseline/'mod.json').exists() or json.loads((baseline/'mod.json').read_text())['Version']!='0.1.46':raise ValueError('Previous baseline unavailable')
    old={p.relative_to(baseline).as_posix():digest(p) for p in baseline.rglob('*') if p.is_file()}
    for rel,sha in old.items():
        dest=BACKUP/rel
        if not dest.exists():safe_copy(baseline/rel,dest,BACKUP)
        if digest(dest)!=sha:raise ValueError('Backup integrity failure')
    print('Complete previous install backed up and verified.',flush=True)
    evidence=PACKAGE/'evidence';evidence.mkdir(exist_ok=True)
    for src,name in [(ROOT/'test-harness/output/20261006-124755/screenshots/floating-tree-before-526fd8aa.png','tree-before.png'),
                     (RUN/'screenshots/grounded-tree-after-808a1e99.png','tree-after.png'),
                     (RUN/'screenshots/tree-root-release-2da8de08.png','tree-root-release.png')]:
        safe_copy(src,evidence/name,PACKAGE)
        safe_copy(src.with_suffix('.json'),evidence/Path(name).with_suffix('.json'),PACKAGE)
    for shot in route['captures']:
        src=Path(shot['path']);safe_copy(src,evidence/src.name,PACKAGE);safe_copy(src.with_suffix('.json'),evidence/src.with_suffix('.json').name,PACKAGE)
    safe_copy(RUN/'game.log',evidence/'native-validation.log',PACKAGE)
    safe_copy(ROOT/'logs/release-unit.log',evidence/'regression-tests.log',PACKAGE)
    safe_copy(ROOT/'logs/tree-grounding-before.json',DOC/'tree-grounding-before.json',DOC)
    stale_manifest=PACKAGE/'docs/conversion/developer-source-manifest.json'
    if stale_manifest.exists():stale_manifest.unlink()
    for src in DOC.rglob('*'):
        if src.is_file() and src.name!='developer-source-manifest.json':safe_copy(src,PACKAGE/'docs/conversion'/src.relative_to(DOC),PACKAGE)
    validation=dict(version='1.0.0',bsp_sha256=digest(PACKAGE/'mod/maps/mp_phase_runner.bsp'),regression_tests=7,
                    native_checks_per_load=4196,validated_map_loads=3,native_markers={m:native.count(m) for m in MARKERS},
                    runtime_route=['cold_launch','same_map_reload','mp_coliseum','mp_phase_runner'],screenshots=9,
                    reported_tree_visual_verified=True,all_twenty_tree_roots_structurally_verified=True,
                    initial_reload_failure='An earlier run with an active custom camera produced a stock loadout/server exception. The harness now clears its camera before disconnect. The subsequent three loads and stock-map return passed; the precise native failure cause is not established.',
                    limitations=['Sampled native traces do not prove every trajectory.','No exhaustive multiplayer/game-mode certification.','Source animation, selective portals and full streaming are incomplete.'])
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(validation,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text())
    # Preserve historical stage flags as provenance; expose current facts separately.
    if 'historical_initial_stage' not in status:
        status['historical_initial_stage']={k:status.get(k) for k in ('map','in_game_verified','collision_sample_brushes','collision_sample_limit','collision_counts')}
    status['map']='mp_phase_runner'
    status['in_game_verified']=True
    status['report_scope']='Historical pipeline stages retained for provenance; release and current measurements are authoritative for 1.0.0.'
    status['current_measurements']=json.loads((DOC/'engine-limits.json').read_text())['current_release']
    status['release']=dict(version='1.0.0',raw_map_name='mp_phase_runner',native_client_validated=True,tree_roots_corrected=9,tree_placements=20,complete_source_fidelity=False,validation=validation)
    (PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    (PACKAGE/'REMAINING_OBJECTS.md').write_text('# Remaining source objects — 1.0.0\n\n5,425 of 16,376 arena placements are rendered. 10,951 remain omitted: 9,537 vegetation and 1,414 other items across 68 model types. Another 486 placements lie outside the imported arena.\n\nSee [full omission ledger](docs/conversion/MISSING_CONTENT.md) for every model and placement, plus dynamic/behavioral omissions.\n',encoding='utf-8')
    for note in PACKAGE.glob('*.md'):
        if note.name in ('README.md','REMAINING_OBJECTS.md'):continue
        content=note.read_text(encoding='utf-8')
        banner='> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.\n\n'
        if not content.startswith(banner):note.write_text(banner+content,encoding='utf-8')
    (PACKAGE/'README.md').write_text('''# Phase Runner 1.0.0 for Northstar

Playable Apex Phase Runner adaptation for Titanfall 2. This release fixes nine floating fir trunks, preserving the tested lighting, collision and portal-free visibility. Twenty full-sized firs are present.

## Install

Close Titanfall 2. Extract the `PhaseRunner` folder from the release ZIP into your active Northstar profile's `mods` folder (normally `Titanfall2/R2Northstar/mods`). Remove or disable the previous `PhaseRunner.Preview` mod so only one version loads. Keep the old ZIP or backup for rollback. Start Northstar and use `map mp_phase_runner` or select Phase Runner in a private match. The installed Titanfall 2 common and Coliseum assets are required.

The release contains BSP, STBSP, RPaks, scripts, loading artwork and localization. Testing controls are a separate optional harness mod; the shipping local-test setting is off. The existing tunnel catwalks and railings remain in place.

## Validation and limits

Seven release regression tests passed. Three native loads passed 4,196 sampled collision/clearance checks each. The client screenshot route covers both buildings, both tunnels, the center and overview; same-map reload and Coliseum-to-Phase Runner return completed without script errors in the final run. See `runtime-validation.json` for evidence and the earlier failed test run.

This is a playable adaptation, not a complete reproduction of Apex. It renders 5,425 arena static placements; 10,951 placements remain omitted, mainly vegetation. Original animated/gameplay entities, full spatial texture streaming, selective portals and universal game-mode support remain incomplete. World indices use 92.96% of the measured capacity; further additions require budget planning.

## Technical handoff

Read [conversion guide](docs/conversion/APEX_TO_TITANFALL2.md), [missing content](docs/conversion/MISSING_CONTENT.md), [engine limits](docs/conversion/engine-limits.json), and the complete placement/entity/binary ledgers in `docs/conversion`. The separate developer ZIP contains the retained prototype source and proposed converter schema; it requires matching inputs, tools and intermediate baselines.

The original tunnel path backup and previous preview releases remain in the development workspace. The scaffold/catwalk theme requested for the tunnels is retained. A future change may remove or redesign it once traversability is revalidated.
''',encoding='utf-8')
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    archive=zip_checked(ROOT/'output/PhaseRunner-1.0.0-Northstar.zip',[(p,'PhaseRunner/'+p.relative_to(PACKAGE).as_posix()) for p in PACKAGE.rglob('*') if p.is_file()])
    print('Northstar release ZIP verified.',flush=True)
    for src in PACKAGE.rglob('*'):
        if src.is_file():safe_copy(src,INSTALLED/src.relative_to(PACKAGE),INSTALLED)
    wanted={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file()}
    for rel in (set(old)-wanted)|{'docs/conversion/developer-source-manifest.json'}:
        p=INSTALLED/rel
        if not p.resolve().is_relative_to(INSTALLED.resolve()):raise ValueError('Unsafe obsolete file')
        if p.exists():p.unlink()
    for rel,sha in checks.items():
        if digest(INSTALLED/rel)!=sha:raise ValueError('Installed hash failure')
    for rel,sha in old.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Backup changed during install')
    enabled=INSTALLED.parent.parent/'enabledmods.json'
    if enabled.exists():
        config=json.loads(enabled.read_text(encoding='utf-8-sig'))
        config.setdefault('PhaseRunner',{})['1.0.0']=True
        enabled.write_text(json.dumps(config,indent=2))
    source_files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in ('.py','.cpp','.ps1','.md')]
    source_files += [p for base in (DOC,ROOT/'test-harness',ROOT/'northstar/MapTest.Harness') for p in base.rglob('*')
                     if p.is_file() and p.name!='developer-source-manifest.json' and 'output' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts and p.suffix.lower() in ('.py','.ps1','.md','.json','.nut','.h','.csv','.patch')]
    # Include exact format parser used by the prototype, together with its license.
    for p in (ROOT/'tools/bsp_tool').rglob('*'):
        if p.is_file() and not any(x in p.parts for x in ('.git','__pycache__','tests','test_maps')) and (p.suffix=='.py' or p.name.upper().startswith(('LICENSE','COPYING'))):source_files.append(p)
    source_files=sorted(set(source_files))
    manifest={p.relative_to(ROOT).as_posix():digest(p) for p in source_files}
    (DOC/'developer-source-manifest.json').write_text(json.dumps(manifest,indent=2))
    source_files.append(DOC/'developer-source-manifest.json')
    kit=zip_checked(ROOT/'output/PhaseRunner-1.0.0-ConversionDeveloperKit.zip',[(p,'PhaseRunner-Conversion/'+p.relative_to(ROOT).as_posix()) for p in source_files])
    result=dict(version='1.0.0',release=archive,developer_kit=kit,installed=str(INSTALLED),backup=str(BACKUP),backup_files_verified=len(old),installed_files_verified=len(checks),trees_checked=20,trees_lowered=9,regression_tests=7,native_checks_per_load=4196,validated_map_loads=3)
    (ROOT/'output/PhaseRunner-1.0.0-release-manifest.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
