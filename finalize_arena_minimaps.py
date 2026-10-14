"""Verify the minimap-only runtime delta and package the native-tested releases."""
import json
import shutil
from pathlib import Path

from build_arena_minimaps import MAPS, OUT, ROOT, verify_pack
from package_player_mods import RELEASES, digest, runtime_files, write_player_zip, record_existing_releases


def radar_visible(path):
    # Check only the native radar artwork, excluding compass and player marker.
    # This rejects the black radar captured during the initial scale mismatch.
    from PIL import Image
    with Image.open(path) as image:
        assert image.size == (1280, 720), 'Radar check uses the 1280x720 harness layout'
        image = image.convert('RGB')
        colourful = sum(max(image.getpixel((x, y)))-min(image.getpixel((x, y))) > 12
            for x in range(100, 225) for y in range(112, 204)
            if 10**2 < (x-162)**2+(y-142)**2 < 65**2)
    assert colourful > 400, 'Native radar image is blank: '+str(path)
    return colourful


def verify():
    baseline = json.loads((OUT/'baseline-runtime.json').read_text())
    result = {}
    pids = set()
    for package, config in MAPS.items():
        mod = ROOT/'northstar'/package
        current = {p.relative_to(mod).as_posix():digest(p) for p in runtime_files(mod)}
        additions = {'paks/'+config['pack']+'.rpak', 'mod/resource/overviews/'+config['map']+'.txt'}
        assert set(current) == set(baseline[package]) | additions
        permitted_changes = {'mod.json', 'paks/rpak.json'}
        unchanged = [path for path, sha in baseline[package].items() if path not in permitted_changes]
        assert all(current[path] == baseline[package][path] for path in unchanged), 'Existing runtime changed'
        mapping = json.loads((mod/'paks/rpak.json').read_text())
        before = json.loads((OUT/config['pack']/'rpak-before.json').read_text())
        before.setdefault('Postload', {}).pop(config['pack']+'.rpak', None)
        before[config['pack']+'.rpak'] = '^'+config['map']+'$'
        assert mapping == before, 'Unexpected loading configuration changes'
        pack = verify_pack(mod/'paks'/(config['pack']+'.rpak'), config)
        captures = json.loads((OUT/'runtime'/package/'captures.json').read_text())
        assert len(captures['shots']) == 5 and captures['map'] == config['map']
        pids.add(captures['game_pid'])
        for shot in captures['shots']:
            assert digest(ROOT/shot['screenshot']) == shot['native_capture']['sha256']
            radar_visible(ROOT/shot['screenshot'])
            assert shot['native_capture']['state']['contexts']['client']['level'] == config['map']
        result[package] = dict(version=RELEASES[package]['version'], native_runtime_verified=True,
            native_screenshots=5, unchanged_existing_runtime_files=len(unchanged), pack=pack,
            corner=config['corner'], scale=config['scale'], configuration_query=captures['configuration_query'])
    reload = json.loads((OUT/'runtime/reload.json').read_text())
    assert pids == {reload['game_pid']}, 'Map-switch validation must use the same owned game process'
    assert not reload['logs']['script_errors']
    radar_visible(Path(reload['capture']['path']))
    assert digest(reload['capture']['path']) == reload['capture']['sha256']
    assert reload['capture']['state']['contexts']['client']['level'] == 'mp_arena_composite'
    report = dict(maps=result, reload_order=['mp_arena_composite','mp_phase_runner','mp_arena_composite'],
                  same_process_verified=True, script_errors=[], native_screenshots=11)
    (OUT/'validation.json').write_text(json.dumps(report, indent=2))
    return report


def finalize():
    report = verify()
    proof = ROOT/'docs/minimaps';proof.mkdir(exist_ok=True)
    for package, config in MAPS.items():
        mod = ROOT/'northstar'/package;release = RELEASES[package]
        title = release['title'];slug = 'phase-runner' if package=='PhaseRunner' else 'drop-off'
        shutil.copy2(ROOT/release['screenshot'], proof/(slug+'.png'))
        identity = json.loads((mod/'mod.json').read_text())
        assert identity['Version'] == release['version']
        identity['Description'] = title+' with native minimap, source display artwork, PBR and preserved collision.'
        (mod/'mod.json').write_text(json.dumps(identity,indent=2)+'\n')
        old = (mod/'README.md').read_text(encoding='utf-8')
        if not old.startswith('# '+title+' '+release['version']):
            (mod/'README.md').write_text('# '+title+' '+release['version']+' for Northstar\n\n'+
                release['notes']+'\n\nThe minimap uses the original Apex artwork with corrected native radar scale. '+
                'See MINIMAPS.md for conversion details and checks.\n\n## Previous release notes\n\n'+old,encoding='utf-8')
        notes = (ROOT/'docs/arena-minimaps-2026-10-13.md').read_text()
        (mod/'MINIMAPS.md').write_text(notes.replace('](minimaps/', '](../../docs/minimaps/'))
        (mod/'minimap-validation.json').write_text(json.dumps(report['maps'][package],indent=2))
        status = mod/'build-status.json'
        if status.exists():
            value = json.loads(status.read_text());value.update(version=release['version'],minimap=report['maps'][package])
            status.write_text(json.dumps(value,indent=2))
        checksums = {p.relative_to(mod).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p))
            for p in sorted(mod.rglob('*')) if p.is_file() and p.name!='checksums.json'}
        (mod/'checksums.json').write_text(json.dumps(checksums,indent=2))
        write_player_zip(mod, ROOT/'output'/f"{package}-{release['version']}-Northstar.zip")
    record_existing_releases()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    finalize()
