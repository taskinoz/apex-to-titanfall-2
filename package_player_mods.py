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
# output/ may be a junction into project storage (manage_project_storage.py relocate).
OUTPUT = (ROOT/'output').resolve()


def workspace_path(target):
    return str(Path('output')/Path(target).resolve().relative_to(OUTPUT))
RELEASES = {
    'PhaseRunner': {
        'version': '1.7.2',
        'map': 'mp_phase_runner',
        'title': 'Phase Runner',
        'screenshot': 'output/arena-fill/phase-runner/comparison/arena-overview-northstar.png',
        'notes': 'The control-room consoles in both bases are drawn from the full Apex mesh with lighting taken from their own surface, so their panels no longer look stretched or streaky. Includes 1.7.1: flicker-free base floors, container frames, smooth catwalks, and 1.7.0 blending, ground tiling and rock collision.',
    },
    'ArenaComposite': {
        'version': '0.10.1',
        'map': 'mp_arena_composite',
        'title': 'Drop-Off',
        'screenshot': 'output/arena-fill/drop-off/comparison/south-overview-northstar.png',
        'notes': 'Preview for Skirmish, Pilots vs Pilots and Free For All. Restores 366 source placements: utility conduits, tanks, crates, furniture and structural details. Uses 97.06% of native world index capacity with no added dynamic entities. Preserves the Apex minimap, Northstar banners, displays, paint, lighting, room closures, safety volumes and ziplines. Some props, animated materials and source runtime colouring remain incomplete. Intro and evac are disabled.',
    },
    'ApexFiringRange': {
        'version': '0.5.1',
        'map': 'mp_apex_firing_range',
        'title': 'Firing Range',
        'screenshot': 'northstar/ApexFiringRange/screenshot.png',
        'notes': 'Rocks now collide with the shape you see: 329 rocks drawn at coarse detail had full-detail Apex collision, which left invisible rock to bump into and visible rock to fall into. Their collision is now the drawn shape, and spawns that stood on the old shape were moved onto the visible ground. Invisible player clips left around the missing shooting-range targets are removed. Invisible collision across the playable area drops from about 16% to under 3% of collision surface. Includes 0.5.0 blending and rock detail. Weapon stations, targets, foliage and AI navigation remain absent. Restart between previews.',
    },
    'ArenaPartyCrasher': {
        'version': '0.6.4',
        'map': 'mp_party_crasher',
        'title': 'Party Crasher',
        'screenshot': 'northstar/ArenaPartyCrasher/screenshot.png',
        'notes': 'Adds a new Northstar billboard image to the curved Oasis screen, matching the Drop-Off banner artwork. Geometry, collision, lighting and gameplay are unchanged from 0.6.3.',
    },
    'ArenaOverflow': {
        'version': '0.4.1',
        'map': 'mp_overflow',
        'title': 'Overflow',
        'screenshot': 'northstar/ArenaOverflow/screenshot.png',
        'notes': 'Fixes z-fighting and flat textures from Apex overlays that were drawn as solid surfaces on top of the surface below: stencil lettering (REFINERY, the capsules) and arrow signs are now proper decals, the flat brown dirt sheet over the asphalt is removed, and the lava no longer flickers between its glow and a grey duplicate. The invisible barrier in the ceiling opening is an Apex player clip and is kept. Known issue (also in 0.4.0): about one load in five can crash Northstar at spawn; restart and load again.',
    },
    'ArenaThermalStation': {
        'version': '0.1.2',
        'map': 'mp_thermal_station',
        'title': 'Thermal Station',
        'screenshot': 'northstar/ArenaThermalStation/screenshot.png',
        'notes': "Thermal Station, the World's Edge area Apex used as an Arenas map. The storm-ring wall now looks the same on every side: it is self-lit with no sun shading, which had left two sides see-through and two orange. Rebuilds no longer stack extra copies of the ring, which had darkened the map. The lava-flow ground is dark cooled crust with glowing cracks, not a bright white sheet. Coplanar dirt overlays that z-fought with the asphalt are removed. The minimap is regenerated. Requires ApexMaps.UI 0.2.1.",
    },
    'ArenaThunderdome': {
        'version': '0.1.1',
        'map': 'mp_thunderdome',
        'title': 'Thunderdome',
        'screenshot': 'northstar/ArenaThunderdome/screenshot.png',
        'notes': 'Thunderdome from the current retail Apex release: the hovering arena inside its stadium ring. Props now collide (Apex collision exported per model), and about 1,500 more props are drawn using cheaper LODs and simplified heavy pipes and frames. Terrain blending, vertex-painted metal, ziplines, lava and out-of-bounds volumes and 88 Apex spawns. Grass and small rock clusters are thinned to fit the draw budget; material colours use neutral tints. Requires ApexMaps.UI 0.2.0.',
    },
}
# The shared UI companion ships as its own download (one UI atlas serves all five maps;
# no map pack carries its own), so map archives never overwrite a newer companion.
SHARED_UI = 'ApexMaps.UI'

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

Close Titanfall 2. Move the old map folder to a backup outside `mods/`, then
extract `{name}` into `Titanfall2/R2Northstar/mods/`. Replace the old folder
rather than merging; obsolete atlas files must be removed. Enable it in
Northstar's mod menu and restart. Disable any older copy of the same map.
Every player needs the same mod version.

The loading artwork and minimap come from the shared `ApexMaps.UI` companion,
a separate download (`ApexMaps.UI-<version>-Northstar.zip`). Install it once
for all five Apex maps and keep the newest version; map archives do not
include it, so installing a map never replaces your companion.

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
    if not target.resolve().is_relative_to(OUTPUT):
        raise ValueError('Release destination must stay in workspace output')
    info = json.loads((source/'mod.json').read_text(encoding='utf-8-sig'))
    if info['Name'] != name or info['Version'] != RELEASES[name]['version']:
        raise ValueError('Unexpected mod identity/version')
    from map_pack_lifetime import audit, audit_shared
    audit_shared()
    audit(source/'paks', RELEASES[name]['map'])
    screenshot = ROOT/RELEASES[name]['screenshot']
    if not screenshot.is_file():
        raise ValueError('Verified game screenshot is missing')
    if target.exists():
        backup = ROOT/'output/distribution-backups'/(target.stem+'-with-reports.zip')
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():
            try:
                os.link(target,backup)
            except OSError:
                shutil.copy2(target,backup)
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
    result = dict(path=workspace_path(target),bytes=target.stat().st_size,
                  sha256=sha,verified_files=len(expected))
    print(json.dumps(result),flush=True)
    return result

def write_ui_zip(target=None):
    """Standalone download of the shared ApexMaps.UI companion (loading artwork and minimaps)."""
    import zipfile as _zip
    shared = ROOT/'northstar'/SHARED_UI
    info = json.loads((shared/'mod.json').read_text(encoding='utf-8-sig'))
    target = Path(target or ROOT/'output'/f"{SHARED_UI}-{info['Version']}-Northstar.zip").resolve()
    files = [shared/'mod.json', *sorted(p for p in (shared/'paks').rglob('*') if p.is_file())]
    text = (f"# {SHARED_UI} {info['Version']} for Northstar\n\nShared loading artwork and minimaps for the seven Apex map conversions "
            "(Phase Runner, Drop-Off, Firing Range, Party Crasher, Overflow, Thermal Station, Thunderdome). Extract `ApexMaps.UI` into "
            "`Titanfall2/R2Northstar/mods/`, replacing any older copy, and enable it. One shared UI atlas serves every map; "
            "keep only the newest version.\n").encode('utf-8')
    temp = target.with_suffix('.zip.packaging'); expected = {}
    with _zip.ZipFile(temp, 'w', _zip.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for path in files:
            arc = SHARED_UI+'/'+path.relative_to(shared).as_posix(); z.write(path, arc); expected[arc] = digest(path)
        z.writestr(SHARED_UI+'/README.md', text); expected[SHARED_UI+'/README.md'] = hashlib.sha256(text).hexdigest()
    with _zip.ZipFile(temp) as z:
        if set(z.namelist()) != set(expected):
            raise ValueError('UI archive membership mismatch')
        for arc, wanted in expected.items():
            if hashlib.sha256(z.read(arc)).hexdigest() != wanted:
                raise ValueError('UI archive payload mismatch: '+arc)
    temp.replace(target); sha = digest(target)
    target.with_suffix('.zip.sha256').write_text(sha+'  '+target.name+'\n')
    result = dict(path=workspace_path(target), bytes=target.stat().st_size, sha256=sha, verified_files=len(expected))
    print(json.dumps(result), flush=True)
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
        results[name] = dict(path=workspace_path(target),bytes=target.stat().st_size,
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
    ledger = ROOT/'output/player-distributions.json'
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    previous.update(results)
    ledger.write_text(json.dumps(previous,indent=2))
    print('Player distribution records updated for', ', '.join(results), flush=True)

if __name__ == '__main__':
    ui = write_ui_zip()
    for name, release in RELEASES.items():
        write_player_zip(ROOT/'northstar'/name,
                         ROOT/'output'/f"{name}-{release['version']}-Northstar.zip")
    record_existing_releases()
    ledger = ROOT/'output/player-distributions.json'; data = json.loads(ledger.read_text()); data[SHARED_UI] = ui
    ledger.write_text(json.dumps(data, indent=2))
