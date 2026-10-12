"""Install the tested character-lighting-only release with a full rollback."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from build_character_lighting import ROOT,SOURCE,TARGET,OUT
from package_character_lighting import BASE,PACKAGE
from finalize_lighting_release import digest
from audit_world_draw_budget import audit
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.37-before-character-lighting'

def finalize():
    unit=(ROOT/'logs/character-lighting-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 7 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:raise ValueError('Character lighting regressions failed')
    log=(ROOT/'logs/character-lighting-0.1.38-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text());report=status['character_light_repair']
    for name,count in status['catwalk_native_probes']['counts'].items():
        marker=f'Phase Runner catwalk {name} checks: {count}/{count} passed'
        if marker not in log:raise ValueError('Missing native check '+marker)
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing native check '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Map did not load')
    if digest(PACKAGE/'mod/maps/mp_phase_runner.bsp')!=digest(TARGET):raise ValueError('Packaged BSP mismatch')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.38':raise ValueError('Wrong candidate version')
    for mod in (BASE,INSTALLED):
        if json.loads((mod/'mod.json').read_text())['Version']!='0.1.37':raise ValueError('Unexpected baseline')
        if digest(mod/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Baseline BSP mismatch')
    if not (ROOT/'output/PhaseRunner.Preview-0.1.37.zip').is_file():raise ValueError('Prior archive missing')
    prior={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    if not BACKUP.exists():shutil.copytree(INSTALLED,BACKUP)
    for rel,sha in prior.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Prior full backup mismatch '+rel)
    (ROOT/'logs/old-0.1.37-backup-verification.json').write_text(json.dumps(dict(backup=str(BACKUP),files=prior),indent=2))
    print(f'Full 0.1.37 backup verified: {len(prior)} files.',flush=True)
    for doc in ('CHARACTER_LIGHTING.md','LIGHTING.md'):shutil.copy2(ROOT/doc,PACKAGE/doc)
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-catwalk-validation.json')
    (PACKAGE/'README.md').write_text('''# Phase Runner 0.1.38

Restart Northstar and load `map mp_phase_runner`.

Adds native spatial lighting samples for moving pilots/Titans, hands and
weapons. The prior map had no character probes. This release adds 39,819
gameplay samples for directional ambient, sun/sky visibility and up to four
local-light links, with closer coverage in buildings and both pipe tunnels.
Two native menu-stage samples preserve the isolated menu lighting.

Geometry, collision, industrial catwalks/railings, visibility, surface
lightmaps, world lights, PBR materials, loading artwork, 13-language map-name
resources and STBSP content retain the exact 0.1.37 data. No portals are added.
Seven focused regressions pass, along with the existing native collision and
catwalk traversal checks. The map loads without script errors.

Character/weapon lighting, reflection appearance and lighting transitions
still need a client check outdoors, in buildings and inside both tunnels.
See CHARACTER_LIGHTING.md and runtime-validation.json for evidence and limits.

Full prior mod: output/installed-backups/PhaseRunner.Preview-0.1.37-before-character-lighting
Prior archive: output/PhaseRunner.Preview-0.1.37.zip
The earlier 0.1.36 full backup/archive with the original paths is also retained.
Backup paths are relative to the project root, not the game mod directory.
''',encoding='utf-8')
    evidence=dict(version='0.1.38',map_name='mp_phase_runner',bsp_sha256=digest(TARGET),native_server_loaded=True,
        load_seconds=float(loading[1]),regression_tests=7,existing_collision_checks=927,
        catwalk_checks=status['catwalk_native_probes']['counts'],character_lighting=report,
        independent_probe_query_validation=json.loads((ROOT/'logs/character-probe-query-validation.json').read_text()),
        native_local_light_index_audit=json.loads((ROOT/'logs/character-light-index-audit.json').read_text()),
        draw_budget=audit(TARGET),old_full_backup=str(BACKUP),old_backup_files_verified=len(prior),
        prior_evidence='prior-catwalk-validation.json',client_lighting_verified=False,client_performance_verified=False,
        limitation='Dedicated loading and CPU probes do not verify GPU character/weapon illumination, reflection appearance or frame rate.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for source in PACKAGE.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(PACKAGE);dest=destination/rel
            if not dest.resolve().is_relative_to(destination.resolve()):raise ValueError('Install target escaped mod')
            # Preserve already verified assets instead of rewriting resident RPaks.
            if dest.exists() and rel.as_posix() in checks and prior.get(rel.as_posix())==checks[rel.as_posix()] and digest(dest)==checks[rel.as_posix()]:continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and os.path.samefile(source,dest):continue
            if destination==BASE and source.stat().st_size>10*1024*1024:
                if dest.exists():dest.unlink()
                os.link(source,dest)
            else:shutil.copy2(source,dest)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed checksum mismatch '+rel)
    print(f'Installed 0.1.38; {len(checks)} file hashes verified.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.38.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive checksum mismatch '+rel)
    result=dict(version='0.1.38',map_name='mp_phase_runner',installed_files_verified=len(checks),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,
        prior_full_backup=str(BACKUP),prior_files_verified=len(prior),regression_tests=7,
        gameplay_light_probes=report['gameplay_probes'],menu_light_probes=report['menu_probes'],
        load_seconds=float(loading[1]),client_lighting_verified=False)
    (ROOT/'logs/character-lighting-0.1.38-release.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
