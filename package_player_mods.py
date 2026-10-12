"""Build player downloads with runtime files, a short README and a real screenshot.

Development ledgers remain in northstar/ and docs/. Runtime bytes are verified
against the working package after compression. Existing report-heavy downloads
are retained outside the player downloads before atomic replacement.
"""
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASES = {
    'PhaseRunner': {
        'version': '1.6.0', 'map': 'mp_phase_runner', 'title': 'Phase Runner',
        'screenshot': 'output/arena-fill/phase-runner/comparison/arena-overview-northstar.png',
        'notes': 'Restores 432 source scenery placements, including supported ground plants, flowers, small snow rocks and power equipment. Uses 97.04% of native world index capacity with no added dynamic entities. Preserves the Apex minimap, displays, paint, safety areas, team spawns, CTF, Hardpoint, Fastball, lighting and catwalks. Terrain layers, Attrition AI/navigation, animated shaders and full multiplayer balance remain incomplete.',
    },
    'ArenaComposite': {
        'version': '0.10.0', 'map': 'mp_arena_composite', 'title': 'Drop-Off',
        'screenshot': 'output/arena-fill/drop-off/comparison/south-overview-northstar.png',
        'notes': 'Preview for Skirmish, Pilots vs Pilots and Free For All. Restores 366 source placements: utility conduits, tanks, crates, furniture and structural details. Uses 97.06% of native world index capacity with no added dynamic entities. Preserves the Apex minimap, Northstar banners, displays, paint, lighting, room closures, safety volumes and ziplines. Some props, animated materials and source runtime colouring remain incomplete. Intro and evac are disabled.',
    },
}

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def runtime_files(source):
    paths = [source/'mod.json']
    for name in ('mod', 'paks'):
        paths.extend(p for p in (source/name).rglob('*') if p.is_file())
    if not paths[0].is_file():
        raise ValueError('Mod manifest is missing')
    if not any(p.suffix == '.bsp' for p in paths):
        raise ValueError('Map payload is missing')
    return sorted(paths)

def player_readme(name):
    release = RELEASES[name]
    return f'''# {release['title']} {release['version']} for Northstar

Close Titanfall 2. Extract `{name}` into `Titanfall2/R2Northstar/mods/`.
Enable it in Northstar's mod menu and restart. Disable any older copy of the
same map. Every player needs the same mod version.

Launch from the console:

```text
map {release['map']}
```

{release['notes']}

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
'''

def write_player_zip(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    name = source.name
    if name not in RELEASES:
        raise ValueError('Unknown player release')
    if not target.resolve().is_relative_to(ROOT/'output'):
        raise ValueError('Release destination must stay in workspace output')
    info = json.loads((source/'mod.json').read_text(encoding='utf-8-sig'))
    if info['Name'] != name or info['Version'] != RELEASES[name]['version']:
        raise ValueError('Unexpected mod identity/version')
    screenshot = ROOT/RELEASES[name]['screenshot']
    if not screenshot.is_file():
        raise ValueError('Verified game screenshot is missing')
    if target.exists():
        backup = ROOT/'output/distribution-backups'/(target.stem+'-with-reports.zip')
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            os.link(target,backup)
    temp = target.with_suffix('.zip.packaging')
    expected = {}
    print('Packaging player mod:',name,flush=True)
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for path in runtime_files(source):
            archive_path = name+'/'+path.relative_to(source).as_posix()
            z.write(path,archive_path); expected[archive_path] = digest(path)
        text = player_readme(name).encode('utf-8')
        z.writestr(name+'/README.md',text)
        expected[name+'/README.md'] = hashlib.sha256(text).hexdigest()
        z.write(screenshot,name+'/screenshot.png')
        expected[name+'/screenshot.png'] = digest(screenshot)
    print('Verifying archive contents and unchanged mod bytes:',name,flush=True)
    with zipfile.ZipFile(temp) as z:
        if set(z.namelist()) != set(expected):
            raise ValueError('Archive membership mismatch')
        for path, wanted in expected.items():
            h = hashlib.sha256()
            with z.open(path) as f:
                for block in iter(lambda:f.read(8 * 1024 * 1024),b''):
                    h.update(block)
            if h.hexdigest() != wanted:
                raise ValueError('Archive payload mismatch: '+path)
    temp.replace(target)
    sha = digest(target)
    target.with_suffix('.zip.sha256').write_text(sha+'  '+target.name+'\n')
    result = dict(path=str(target.relative_to(ROOT)),bytes=target.stat().st_size,
                  sha256=sha,verified_files=len(expected))
    print(json.dumps(result),flush=True)
    return result

def record_existing_releases():
    results = {}
    for name, release in RELEASES.items():
        target = ROOT/'output'/f"{name}-{release['version']}-Northstar.zip"
        with zipfile.ZipFile(target) as z:
            members = z.namelist()
            if not all(p.startswith(name+'/mod/') or p.startswith(name+'/paks/')
                       or p in {name+'/mod.json',name+'/README.md',name+'/screenshot.png'}
                       for p in members):
                raise ValueError('Unexpected player archive contents')
        results[name] = dict(path=str(target.relative_to(ROOT)),bytes=target.stat().st_size,
                             sha256=digest(target),verified_files=len(members))
    manifest = ROOT/f"output/PhaseRunner-{RELEASES['PhaseRunner']['version']}-release-manifest.json"
    if manifest.exists():
        backup = ROOT/'output/distribution-backups/PhaseRunner-1.1.0-release-manifest-with-reports.json'
        if not backup.exists():
            shutil.copy2(manifest,backup)
        report = json.loads(manifest.read_text())
        report['release'] = results['PhaseRunner']
        report['distribution_contents'] = 'Runtime files, short README and native game screenshot'
        manifest.write_text(json.dumps(report,indent=2))
    (ROOT/'output/player-distributions.json').write_text(json.dumps(results,indent=2))
    print('Both clean player distribution records updated.',flush=True)

if __name__ == '__main__':
    for name, release in RELEASES.items():
        write_player_zip(ROOT/'northstar'/name,
                         ROOT/'output'/f"{name}-{release['version']}-Northstar.zip")
    record_existing_releases()
