"""Install the validated renamed release and preserve the complete prior mod."""
import hashlib,json,os,re,shutil,zipfile
from pathlib import Path
from finalize_lighting_release import ROOT,digest
from build_phase_runner_catwalks import SOURCE,TARGET
from package_phase_runner_release import PACKAGE
from repair_preview_index_padding import read_lumps
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY

BASE=ROOT/'northstar/PhaseRunner.Preview'
INSTALLED=Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview')
BACKUP=ROOT/'output/installed-backups/PhaseRunner.Preview-0.1.36-before-catwalks'

def owned(path,root):
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('File operation escaped its owned mod directory: '+str(path))

def stage(source,target,root):
    owned(target,root);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and os.path.samefile(source,target):return
    # Save space on C by sharing only the validated large release assets.
    if root==BASE and source.stat().st_size>10*1024*1024:
        if target.exists():target.unlink()
        os.link(source,target)
    else:
        shutil.copy2(source,target)

def finalize():
    bsp=PACKAGE/'mod/maps/mp_phase_runner.bsp'
    if digest(bsp)!=digest(TARGET):raise ValueError('Packaged BSP differs from tested candidate')
    unit=(ROOT/'logs/catwalk-unit.log').read_text(encoding='utf-8-sig')
    if 'Ran 9 tests' not in unit or '\nOK' not in unit or 'FAILED' in unit:
        raise ValueError('Catwalk regression checks failed')
    log=(ROOT/'logs/catwalk-0.1.37-validation.log').read_text(encoding='utf-8-sig')
    status=json.loads((PACKAGE/'build-status.json').read_text())
    probes=status['catwalk_native_probes']['counts']
    for name,count in probes.items():
        marker=f'Phase Runner catwalk {name} checks: {count}/{count} passed'
        if marker not in log:raise ValueError('Missing native check '+marker)
    for marker in ('collision probes: 565/565 hit','prop hull probes: 352/352 hit','edge clearance probes: 10/10 clear'):
        if marker not in log:raise ValueError('Missing baseline native collision check '+marker)
    if 'COMPILE ERROR' in log or 'SCRIPT ERROR' in log:raise ValueError('Native script error')
    loading=re.search(r'loading took ([0-9.]+)s',log)
    if not loading:raise ValueError('Renamed map did not load')
    if json.loads((PACKAGE/'mod.json').read_text())['Version']!='0.1.37':raise ValueError('Wrong release version')
    for mod in (BASE,INSTALLED,BACKUP):
        if json.loads((mod/'mod.json').read_text())['Version']!='0.1.36':raise ValueError('Unexpected baseline '+str(mod))
        if digest(mod/'mod/maps/mp_phase_runner_preview.bsp')!=digest(SOURCE):raise ValueError('Old map mismatch '+str(mod))
    prior_checks=json.loads((BACKUP/'checksums.json').read_text())
    for rel,sha in prior_checks.items():
        if digest(BACKUP/rel)!=sha:raise ValueError('Old backup checksum mismatch '+rel)
    # Verify every prior installed file, including historical reports outside the old manifest.
    prior_files={p.relative_to(INSTALLED).as_posix():digest(p) for p in INSTALLED.rglob('*') if p.is_file()}
    for rel,sha in prior_files.items():
        if not (BACKUP/rel).is_file() or digest(BACKUP/rel)!=sha:raise ValueError('Incomplete old-build backup '+rel)
    old_archive=ROOT/'output/PhaseRunner.Preview-0.1.36.zip'
    if not old_archive.is_file():raise ValueError('Old release archive missing')
    (ROOT/'logs/old-0.1.36-backup-verification.json').write_text(json.dumps(dict(backup=str(BACKUP),files=prior_files),indent=2))
    current=read_lumps(bsp,(*range(0x6a,0x7a),0x51));previous=read_lumps(SOURCE,range(0x6a,0x77))
    for i in range(0x6a,0x77):
        if current[i]!=previous[i]:raise ValueError('Portal records changed '+hex(i))
    visibility=validate_visibility(current[0x77],current[0x78],current[0x79],current[0x51])
    budget=audit(bsp)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Draw headroom insufficient')
    if digest(PACKAGE/'paks/phase_runner_world.rpak')!=digest(BACKUP/'paks/phase_runner_world.rpak'):
        raise ValueError('Existing world materials changed')
    if digest(PACKAGE/'mod/maps/mp_phase_runner.stbsp')!=digest(BACKUP/'mod/maps/mp_phase_runner_preview.stbsp'):
        raise ValueError('Streaming catalog changed')
    if digest(PACKAGE/'paks/phase_runner_presentation.rpak')!=status['map_presentation']['rpak_sha256']:
        raise ValueError('Loading artwork package mismatch')
    shutil.copy2(ROOT/'CATWALK_VISIBILITY.md',ROOT/'VISIBILITY.md')
    for doc in ('ART_TODO.md','LIGHTING.md','DEV_MATERIALS.md','INTERIOR_LIGHTING.md','VISIBILITY.md','CATWALKS.md','PRESENTATION.md'):
        shutil.copy2(ROOT/doc,PACKAGE/doc)
    for p in BACKUP.glob('*.json'):
        if p.name not in ('mod.json','checksums.json','build-status.json','runtime-validation.json'):
            shutil.copy2(p,PACKAGE/p.name)
    shutil.copy2(BACKUP/'runtime-validation.json',PACKAGE/'prior-rendering-validation.json')
    old_paths=json.loads((PACKAGE/'tunnel-walkways.json').read_text())
    old_paths['historical_provenance_only']=True;old_paths['replaced_by']='catwalks.json, version 0.1.37'
    (PACKAGE/'tunnel-walkways.json').write_text(json.dumps(old_paths,indent=2))
    (PACKAGE/'README.md').write_text('''# Phase Runner 0.1.37

Restart Northstar and load `map mp_phase_runner`.

The map is renamed from mp_phase_runner_preview. Original Phase Runner loading
artwork and lobby images are included, with display-name and description
resources for 13 languages. Both pipe paths are replaced by lit industrial
grating catwalks, metal supports and yellow railings along the same routes.

Tunnel visibility guards now include distant objects from both tunnel routes.
No connected portals are added. The sky and original cell/portal records are
preserved. Existing world materials, outdoor/interior lighting and unrelated
collision are retained; new catwalk surfaces have matching collision and a
separate lightmap bake.

Nine regressions pass. Native checks pass for 102 catwalk floor contacts,
204 rail contacts, 1,449 player-sized route sweeps in both directions, 1,449
route floor contacts, and the existing 927 collision probes. The renamed map
loads without script errors. All world meshes fit the native index budget
with 15.69% headroom. Client rendering, loading-screen appearance, localized
menu text and frame rate still need an in-game check.

Full old build with the original paths:
output/installed-backups/PhaseRunner.Preview-0.1.36-before-catwalks
Archive: output/PhaseRunner.Preview-0.1.36.zip
These paths are relative to the project root, not the game mod folder.

See CATWALKS.md, PRESENTATION.md, VISIBILITY.md and runtime-validation.json
for measured results and limits. Full texture mips remain resident, and the
renamed STBSP retains its existing content.
''',encoding='utf-8')
    evidence=dict(version='0.1.37',map_name='mp_phase_runner',bsp_sha256=digest(bsp),
        native_server_loaded=True,load_seconds=float(loading[1]),regression_tests=9,
        existing_collision_checks=927,catwalk_checks=probes,catwalk_routes_checked_both_directions=True,
        player_route_step_clearance=18,visibility=visibility,new_portal_connections=0,
        tunnel_guards_cover_all_objects_from_both_routes=True,draw_budget=budget,
        draw_headroom_percent=(1-budget['native_padded_indices']/WORLD_INDEX_CAPACITY)*100,
        catwalk_geometry=status['catwalk_release']['new_catwalk_triangles'],
        replaced_path_geometry=status['catwalk_release']['removed_old_path_triangles'],
        catwalk_light_bake=status['catwalk_release']['light_bake'],
        unrelated_drawn_corner_attributes_materials_and_lightmaps_exact=True,
        unrelated_collision_and_active_ownership_preserved=True,
        original_routes_and_elevations_exact=True,world_rpak_and_stbsp_content_unchanged=True,
        presentation=status['map_presentation'],old_build_backup=str(BACKUP),old_build_backup_files=len(prior_files),
        old_build_archive=str(old_archive),prior_evidence='prior-rendering-validation.json',
        client_rendering_verified=False,client_presentation_verified=False,client_performance_verified=False,
        limitation='Native dedicated checks validate collision and loading but do not exercise client rendering, '
        'UI artwork, localization display or frame rate. Conservative tunnel guards may increase draw work.')
    (PACKAGE/'runtime-validation.json').write_text(json.dumps(evidence,indent=2))
    checks={p.relative_to(PACKAGE).as_posix():digest(p) for p in PACKAGE.rglob('*') if p.is_file() and p.name!='checksums.json'}
    (PACKAGE/'checksums.json').write_text(json.dumps(checks,indent=2))
    for destination in (BASE,INSTALLED):
        for p in PACKAGE.rglob('*'):
            if p.is_file():stage(p,destination/p.relative_to(PACKAGE),destination)
        for rel,sha in checks.items():
            if digest(destination/rel)!=sha:raise ValueError('Installed checksum mismatch '+rel)
        # Remove only the superseded map files after the full new mod verifies.
        for suffix in ('.bsp','.stbsp'):
            obsolete=destination/('mod/maps/mp_phase_runner_preview'+suffix);owned(obsolete,destination)
            if obsolete.exists():
                if digest(obsolete)!=digest(BACKUP/obsolete.relative_to(destination)):
                    raise ValueError('Superseded map differs from saved backup')
                obsolete.unlink()
    print(f'Installed 0.1.37; {len(checks)} file hashes verified; complete old backup retained.',flush=True)
    archive=ROOT/'output/PhaseRunner.Preview-0.1.37.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in PACKAGE.rglob('*'):
            if p.is_file():z.write(p,Path('PhaseRunner.Preview')/p.relative_to(PACKAGE))
    with zipfile.ZipFile(archive) as z:
        for rel,sha in checks.items():
            h=hashlib.sha256()
            with z.open('PhaseRunner.Preview/'+rel) as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=sha:raise ValueError('Archive checksum mismatch '+rel)
    result=dict(version='0.1.37',map_name='mp_phase_runner',installed_files_verified=len(checks),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_hashes_verified=True,
        old_build_backup=str(BACKUP),old_build_files_verified=len(prior_files),old_build_archive=str(old_archive),
        regression_tests=9,existing_collision_checks=927,catwalk_checks=probes,load_seconds=float(loading[1]))
    (ROOT/'logs/catwalk-0.1.37-release.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':finalize()
