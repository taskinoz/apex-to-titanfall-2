"""Promote only validated gameplay content; retain the 1.0.0 install and release."""
import json,os,shutil,sys
from pathlib import Path
from finalize_phase_runner_release import safe_copy,digest
ROOT=Path(__file__).resolve().parent
STAGE=ROOT/'northstar/PhaseRunner.GameModes'
PACKAGE=ROOT/'northstar/PhaseRunner'
BACKUP=ROOT/'output/installed-backups/PhaseRunner-1.0.0-before-gameplay'
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
MODES={'tdm','ps','ctf','cp','aitdm','fastball','lts','ttdm','mfd','ffa'}

def finalize():
    native=json.loads((ROOT/'logs/gameplay-runtime.json').read_text())
    if set(native)!=MODES:raise ValueError('Missing mode validation')
    for mode,r in native.items():
        if r['check']['mode']!=mode or not r['check']['ok']:raise ValueError('Failed mode '+mode)
        s=r['check']['spawns']
        if s['info_spawnpoint_human_start']['imc']!=12 or s['info_spawnpoint_human_start']['militia']!=12:raise ValueError('Missing team starts')
        if s['info_spawnpoint_human']['total']!=42 or s['info_spawnpoint_titan']['total']!=12 or s['info_spawnpoint_titan_start']['total']!=6:raise ValueError('Missing respawns')
    if len(native['ctf']['check']['objectives'])!=2 or not all(x['valid'] for x in native['ctf']['check']['objectives']):raise ValueError('Missing flag')
    if set(native['cp'].get('capture_tests',{}))!={'A','B','C'}:raise ValueError('Capture tests incomplete')
    if native['fastball']['after_intro']['panels']!=3:raise ValueError('Fastball failed')
    for file,n in [('gameplay-unit.log',5),('gameplay-harness-tests.log',6)]:
        text=(ROOT/'logs'/file).read_text(encoding='utf-8-sig')
        if f'Ran {n} tests' not in text or '\nOK' not in text or 'FAILED' in text:raise ValueError('Regression failed: '+file)
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='1.0.0':raise ValueError('Unexpected canonical baseline')
    if json.loads((INSTALLED/'mod.json').read_text())['Version']!='1.0.0':raise ValueError('Unexpected installed baseline')
    old={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file()}
    for rel,sha in old.items():
        dst=BACKUP/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():os.link(PACKAGE/rel,dst)
        if digest(dst)!=sha or digest(INSTALLED/rel)!=sha:raise ValueError('Baseline mismatch: '+rel)
    print('1.0.0 baseline preserved and verified.',flush=True)
    doc=(ROOT/'docs/conversion/GAMEPLAY_MODES.md').read_text()
    (STAGE/'docs/conversion/GAMEPLAY_MODES.md').write_text(doc)
    guide=STAGE/'docs/conversion/APEX_TO_TITANFALL2.md'
    guide.write_text(guide.read_text()+'\n\n## Gameplay authoring update — 1.1.0\n\nSee [gameplay layout and mode hooks](GAMEPLAY_MODES.md) for native team spawns, CTF, hardpoints, Fastball and verification. Earlier inventories describe the 1.0.0 source conversion; gameplay-layout.json records the additional authored target entities.\n')
    (ROOT/'docs/conversion/APEX_TO_TITANFALL2.md').write_text(guide.read_text())
    (STAGE/'README.md').write_text('''# Phase Runner 1.1.0 for Northstar

Phase Runner now has opposing building bases: IMC west and Militia east. There are 12 pilot starts per team, 42 distributed pilot respawns, 12 outdoor Titan respawns and three Titan starts per side. CTF has flags in both buildings; Amped Hardpoint has A/B/C capture areas; Fastball has native Buddy throw positions and three hacking panels. Shared spawns also serve Pilot Skirmish, Last Titan Standing, Titan Brawl, Marked for Death and FFA.

## Install and play

Close Titanfall 2. Extract the `PhaseRunner` folder into your active Northstar profile's `mods` directory. Replace or disable the earlier PhaseRunner/PhaseRunner.Preview copy so only one version loads. All players joining the match need this map version. Common Northstar/Coliseum assets are required.

Select the mode in a private match, or set `mp_gamemode <mode>` before `map mp_phase_runner`. Identifiers: `aitdm` Attrition, `tdm` TDM, `ps` Pilot Skirmish, `ctf` CTF, `cp` Amped Hardpoint, `fastball`, `lts`, `ttdm` Titan Brawl, `mfd`, `ffa`.

Attrition pilot/Titan spawns are configured, but AI waves still require a valid authored AIN/navigation graph. Frontier Defense waves and Bounty Hunt banks/camps are not included. Multiplayer balance and full Fastball team respawn/CTF matches still need human playtests.

## Validation

Ten modes were checked in the native game. All 86 spawn/flag markers pass standing-hull clearance and floor support checks. Native team start selection was checked in the pilot modes, both CTF flags were created, all three hardpoints captured and began amping for the chosen teams, and all three Fastball panels were present after the throw intro. Five gameplay regression tests and six harness tests passed.

The entire existing BSP body and all non-entity headers are unchanged from 1.0.0. Existing lighting, textures, visibility, collision, recovered props, twenty firs and tunnel catwalks are retained. Only native gameplay entities and map scripts were added. The earlier release ZIP remains available for rollback.

See [gameplay documentation](docs/conversion/GAMEPLAY_MODES.md), gameplay-layout.json, gameplay-runtime.json and gameplay-validation.json. The conversion guide and source omission ledgers retain their versioned provenance; this authored gameplay layer is separate from source asset recovery. The optional harness is not part of the shipping mod, and local-test settings default off.
''',encoding='utf-8')
    evidence=STAGE/'evidence'
    for src in ('gameplay-runtime.json','gameplay-spawn-probes.json','gameplay-unit.log','gameplay-harness-tests.log','gameplay-native-suite.log','gameplay-extra-native-suite.log'):
        safe_copy(ROOT/'logs'/src,evidence/src,STAGE)
    safe_copy(ROOT/'logs/gameplay-runtime.json',STAGE/'gameplay-runtime.json',STAGE)
    screenshots=[]
    for r in native.values():
        if 'screenshot' not in r:continue
        p=Path(r['screenshot']['path']);safe_copy(p,evidence/p.name,STAGE);safe_copy(p.with_suffix('.json'),evidence/p.with_suffix('.json').name,STAGE)
        screenshots.append('evidence/'+p.name)
    # Final harness logs have auth fields redacted before export.
    sys.path.insert(0,str(ROOT/'test-harness'))
    from harness import Controller
    c=Controller();export=c.export_logs()
    if export and export['script_errors']:raise ValueError('Final native run has script errors')
    safe_copy(c.run/'game.log',evidence/'gameplay-final-native.log',STAGE)
    for p in c.run.glob('game-before-titan-switch-*.log'):safe_copy(p,evidence/p.name,STAGE)
    validation=dict(version='1.1.0',modes=sorted(MODES),spawn_markers_checked_per_mode=86,
                    pilot_start_selection_tested=['tdm','ps','ctf','cp','aitdm','mfd'],hardpoint_capture_tests=['A','B','C'],
                    ctf_flags_created=2,fastball_panels_created=3,regression_tests=11,geometry_and_collision_preserved=True,
                    screenshots=screenshots,native_bsp_sha256=digest(STAGE/'mod/maps/mp_phase_runner.bsp'),
                    known_harness_failure='An earlier LTS hot switch hit the stock Titan-menu BUTTON_BACK deregistration assertion. Titan-only switches now use a fresh owned process. The failed run is retained in test-harness/output/20261006-145515.',
                    limitations=['Single-client functional testing; multiplayer balance and full team matches remain unverified.','Attrition AI navigation is absent.','Native Titan spawn hulls/markers are checked; not every live Titan drop trajectory is tested.'])
    (STAGE/'gameplay-validation.json').write_text(json.dumps(validation,indent=2))
    status=json.loads((STAGE/'build-status.json').read_text());status['gameplay_release']=validation
    (STAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    hashes={p.relative_to(STAGE).as_posix():digest(p) for p in STAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (STAGE/'checksums.json').write_text(json.dumps(hashes,indent=2))
    for src in STAGE.rglob('*'):
        if src.is_file():safe_copy(src,PACKAGE/src.relative_to(STAGE),PACKAGE)
    from package_player_mods import write_player_zip
    archive=write_player_zip(PACKAGE,ROOT/'output/PhaseRunner-1.1.0-Northstar.zip')
    print('1.1.0 Northstar ZIP verified.',flush=True)
    for src in PACKAGE.rglob('*'):
        if src.is_file():safe_copy(src,INSTALLED/src.relative_to(PACKAGE),INSTALLED)
    for rel,sha in hashes.items():
        if digest(INSTALLED/rel)!=sha:raise ValueError('Installed checksum mismatch')
    for rel,sha in old.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Backup changed')
    enabled=INSTALLED.parent.parent/'enabledmods.json';config=json.loads(enabled.read_text(encoding='utf-8-sig'))
    config.setdefault('PhaseRunner',{}).update({'1.0.0':False,'1.1.0':True});enabled.write_text(json.dumps(config,indent=2))
    result=dict(version='1.1.0',release=archive,installed=str(INSTALLED),backup=str(BACKUP),installed_files_verified=len(hashes),validation=validation)
    (ROOT/'output/PhaseRunner-1.1.0-release-manifest.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':finalize()
