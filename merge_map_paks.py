"""Make a map port standalone: one level pack `mp_<map>.rpak` instead of packs mounted on mp_coliseum.rpak.

The ports aliased `mp_<map>.rpak` to Coliseum's level pack and loaded their own packs as Postloads of it. Postloads
are global in Northstar, so every installed port's packs loaded for any converted map, and eight ports ran the game out
of memory (Skulltown 0.1.0, 14 November 2026). What was tested in the harness, 14 November:

| Mounting | Result |
| --- | --- |
| Postloads keyed to the map's own `mp_<map>.rpak` shipped in the mod | Never fire (Northstar loads it by its mod path) |
| Map regex (`^mp_<map>$`), with or without the Coliseum assets loaded first | Pink: the packs reload around the level change |
| Postloads keyed to `mp_<map>_patch.rpak` | Pink |
| Alias to another stock level pack (mp_coliseum_column, mp_lf_stacks) | Correct, but shared with that stock map |
| **Everything in one `mp_<map>.rpak` in the mod, no alias** | **Correct; nothing else loads** |

So this rebuilds every runtime pack of a port (world, props, fill, blends, displays...) from its RePak project into one
pack named after the map, together with the few Coliseum assets the world materials reference (standalone_map_pak:
a world shader set and the three depth-pass materials, at Coliseum's asset paths, so their ids are unchanged). Each
pack's project is found by the sha256 of its build output, so the merged pack is built from exactly what shipped; the
result must contain every asset id (with its type and header size) of the released packs plus the Coliseum copies.

  python merge_map_paks.py <installed or accepted mod folder> <map name> <output package folder>
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import local_paths
from extract_native_material import NativePak
import standalone_map_pak as level

ROOT = Path(__file__).resolve().parent
WORK = local_paths.path('APEX_WORK_ROOT')
SEARCH = (WORK/'new-arena-ports', WORK/'project-storage', WORK/'legacy-work', ROOT/'output')
PROJECT_NAMES = ('build.json', 'shader-build.json')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 24), b''):
            h.update(block)
    return h.hexdigest()


def relocated(path):
    """A project path, or where project-storage moved it (repo output/ and new-arena-ports outputs)."""
    p = Path(path)
    if p.exists():
        return p
    text = str(p).replace('\\', '/')
    for marker in ('/output/', '/new-arena-ports/'):
        if marker in text:
            tail = text.split(marker, 1)[1]
            for base in (WORK/'project-storage/output', WORK/'project-storage/new-arena-ports'):
                if (base/tail).exists():
                    return base/tail
    return p


def projects():
    found = {}
    for root in SEARCH:
        for name in PROJECT_NAMES:
            for f in root.rglob(name):
                try:
                    d = json.loads(f.read_text())
                except (ValueError, UnicodeDecodeError, OSError):
                    continue
                if isinstance(d, dict) and 'files' in d and 'name' in d and 'outputDir' in d:
                    found.setdefault(d['name'], []).append((f, d))
    return found


def find_project(pak, index):
    """The project whose build output is byte-identical to the released pack."""
    size, digest = pak.stat().st_size, None
    for f, d in index.get(pak.stem, []):
        out = relocated(d['outputDir'])/(d['name']+'.rpak')
        if out.exists() and out.stat().st_size == size:
            digest = digest or sha(pak)
            if sha(out) == digest and relocated(d['assetsDir']).exists():
                return f, d
    raise ValueError('No RePak project reproduces '+pak.name)


def ids(path):
    return {(a['guid'], a['type'], a['size']) for a in NativePak(Path(path)).assets}


def merge(mod, map_name, out):
    mod, out = Path(mod), Path(out); paks = mod/'paks'
    runtime = sorted(p for p in paks.glob('*.rpak') if not p.name.endswith('_presentation.rpak') and p.stem != map_name)
    index = projects(); used = [(p, *find_project(p, index)) for p in runtime]
    work = WORK/'new-arena-ports/level-paks'/map_name; config = json.loads((paks/'rpak.json').read_text())
    scratch = work/'source'; shutil.rmtree(scratch, ignore_errors=True); (scratch/'paks').mkdir(parents=True)
    for p in paks.glob('*.rpak'):
        os.link(p, scratch/'paks'/p.name)
    shutil.copy2(paks/'rpak.json', scratch/'paks/rpak.json')
    deps_report = level.build(scratch, map_name, work/'coliseum')  # the Coliseum copies alone, on a scratch copy
    deps = json.loads((work/'coliseum/build.json').read_text())
    merged = work/'merged'; shutil.rmtree(merged, ignore_errors=True); assets = merged/'assets'; assets.mkdir(parents=True)
    files, owner = [], {}
    for source_dir, entries in [(Path(deps['assetsDir']), deps['files'])]+[(relocated(d['assetsDir']), d['files']) for _, _, d in used]:
        files.extend(entries)
        for src in source_dir.rglob('*'):  # whole tree: materials name depth materials the file list omits
            if not src.is_file():
                continue
            rel = src.relative_to(source_dir); dst = assets/rel
            if dst.exists():
                if sha(dst) != sha(src):
                    raise ValueError(f'{rel} differs between {owner[rel]} and {source_dir}')
                continue
            dst.parent.mkdir(parents=True, exist_ok=True); owner[rel] = source_dir
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    manifest = dict(version=7, name=map_name, keepDevOnly=True, assetsDir=str(assets.resolve()),
                    outputDir=str((merged/'build').resolve()), compressLevel=0, hasDynamicLibrary=False, files=files)
    (merged/'build.json').write_text(json.dumps(manifest, indent=1))
    with (merged/'build.log').open('w') as log:
        subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str((merged/'build.json').resolve())], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    built = merged/'build'/(map_name+'.rpak')
    expected = set().union(*(ids(p) for p in runtime), ids(work/'coliseum/build'/(map_name+'.rpak')))
    got = ids(built)
    if got != expected:
        raise ValueError(f'Merged pack differs: {len(expected-got)} missing, {len(got-expected)} extra')
    # Output package: the mod with its runtime packs replaced by the level pack, mounted with no alias or Postload.
    shutil.rmtree(out, ignore_errors=True)
    for p in mod.rglob('*'):
        if p.is_file() and not (p.parent == paks and p.suffix == '.rpak' and not p.name.endswith('_presentation.rpak')) \
                and p.name != 'rpak.json':
            dst = out/p.relative_to(mod); dst.parent.mkdir(parents=True, exist_ok=True); os.link(p, dst)
    os.link(built, out/'paks'/built.name)
    aliases = {k: v for k, v in config.get('Aliases', {}).items() if k != map_name+'.rpak'}
    postload = {k: v for k, v in config.get('Postload', {}).items() if k.endswith('_presentation.rpak')}
    (out/'paks/rpak.json').write_text(json.dumps(dict(Aliases=aliases, Postload=postload), indent=2)+'\n')
    report = dict(map=map_name, level_pack=built.name, level_pack_bytes=built.stat().st_size, assets=len(got),
                  merged_packs={p.name: dict(bytes=p.stat().st_size, project=str(f.relative_to(WORK) if WORK in f.parents
                                              else f.relative_to(ROOT)).replace('\\', '/')) for p, f, _ in used},
                  coliseum_copies=deps_report['copied'], asset_ids_match_released=True, mounting='level pack, no alias')
    (out/'level-pack.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'coliseum_copies'}, indent=2))
    return report


if __name__ == '__main__':
    merge(*sys.argv[1:4])
