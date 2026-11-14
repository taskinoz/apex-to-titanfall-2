"""Give a retail port's unresolved world materials their original textures from Apex's shared packs.

A map pack's material export (extract_apex_current.py, RSX) only holds the textures that pack owns; a material
whose textures live in common*.rpak exports with `unavailable` slots, so the world build draws it grey or white.
Skulltown (November 2026) had 30 such materials, among them its skull and rib bones and most of its sand. This
exports the missing materials again from the common packs plus the map pack (RSX resolves their textures there),
then rebuilds the world RPak with them: repair_thunderdome.materials' process for any retail port, and the BSP is
unchanged (the materials keep their names).

* GUID-named materials (`0xCC8B317C2431D`, Cast's top digits) are resolved through an asset list of the same packs.
* Layered (`_bm`) materials take their first layer's maps: the native world shader draws one layer, and the first
  layer is the authored surface (bone, rock) with sand blended over it.
* Sky, tool, cubemap-projection and translucent materials are left out (`SKIP`); retire_meshes removes the first
  two kinds' meshes from the draw.

  python recover_shared_materials.py skulltown [<package to update>]
"""
import csv
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import local_paths
from new_arena_ports import CONFIG, ROOT, folder
from repair_thunderdome import digest, write

PACKS = ('common_early.rpak', 'common.rpak', 'common(01).rpak', 'common_mp.rpak', 'common_mp(01).rpak')
SKIP = ('sky', 'tools', 'cubemap', 'transparent', '_trans', 'stencil', 'decal', 'breachglass', 'test_colors')
SLOTS = (('_col', '0', 'albedo'), ('_nml', '1', 'normal'), ('_gls', '2', 'gloss'), ('_spc', '3', 'spec'))
CAP = 1024


def rsx(args, cwd, log):
    with log.open('w') as stream:
        subprocess.run([str(local_paths.rsx()), '-nogui', '-nocachedb', *map(str, args)], cwd=cwd, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def export(ident, names):
    out = folder(ident)/'shared-export'; out.mkdir(exist_ok=True)
    packs = local_paths.apex_paks(); inputs = [packs/n for n in (*PACKS, CONFIG[ident]['source']+'.rpak') if (packs/n).exists()]
    inventory = out/'all-assets.csv'
    if not inventory.exists():
        rsx(['--list', inventory, '--listformat', 'csv', *inputs], out, out/'list.log')
    rows = [r for r in csv.DictReader(inventory.open(encoding='utf-8-sig')) if r['type'] == 'matl']
    aliases = {}
    for n in names:
        if n.startswith('0x'):
            for r in rows:
                if r['guid'].upper().lstrip('0').startswith(n[2:].upper()):
                    base = r['asset_name'].replace('\\', '/').rsplit('/', 1)[-1].removesuffix('.rpak')
                    aliases[n] = base.rsplit('_', 1)[0]; break
    wanted = sorted({aliases.get(n, n) for n in names})
    rsx(['-export', '-matltextures', '--texnames', 'semantic', '--exportformats', 'txtr=DDS (Highest Mip),matl=Uber (Raw)',
         '--exporttypes', 'matl', '--exportfilter', ','.join(wanted), '--exportthreads', '4', '--exportdir', out, *inputs],
        out, out/'export.log')
    return out/'exported_files/material', aliases


def recover(ident, package=None):
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from optimize_preview_textures import dds, FORMATS
    slug = ident.replace('-', '_'); mats = folder(ident)/'materials'; assets = mats/'assets'
    manifest = json.loads((mats/'build.json').read_text()); mapping = json.loads((mats/'mapping.json').read_text())
    missing = [n for n, v in mapping['materials'].items() if not v.get('recovered') and not any(s in n.lower() for s in SKIP)]
    exported, aliases = export(ident, missing)
    index = {}
    for path in sorted(exported.glob('*/*.json'), key=lambda p: ('_wldc' not in p.stem, '_rgdp' not in p.stem)):
        if path.stem != path.parent.name or '_colpass' in path.stem:
            continue
        spec = json.loads(path.read_text()); index.setdefault(spec.get('name', '').rsplit('/', 1)[-1].lower(), (path, spec))
    files = {f['_path']: f for f in manifest['files']}; original = set(files); rows, deferred, converted = [], {}, {}
    for name in missing:
        key = aliases.get(name, name).lower()
        if key not in index:
            deferred[name] = 'No original material in the shared or map packs'; continue
        path, spec = index[key]; types = spec.get('$textureTypes', {}); textures = {}; proof = []
        for semantic, slot, label in SLOTS:
            refs = sorted((k for k, t in types.items() if t == semantic), key=int)  # first layer first
            src = next((path.parent/(Path(spec['$textures'][k]).stem+'.dds') for k in refs
                        if (path.parent/(Path(spec['$textures'][k]).stem+'.dds')).exists()), None)
            if src is None:
                continue
            identity = (digest(src), semantic)
            if identity not in converted:
                target = f'texture/{slug}/shared_{name.lower()}_{label}.rpak'
                dest = (assets/target).with_suffix('.dds'); dest.parent.mkdir(parents=True, exist_ok=True)
                info = dds(src.read_bytes()); scale = min(1, CAP/max(info['width'], info['height']))
                temp = mats/'conversion'/f'shared_{name.lower()}_{label}'; temp.mkdir(parents=True, exist_ok=True)
                run = subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f',
                                      FORMATS[info['format']][0], '-dx10', '-w', str(max(1, int(info['width']*scale))),
                                      '-h', str(max(1, int(info['height']*scale))), '-o', str(temp.resolve()), str(src.resolve())],
                                     capture_output=True, text=True)
                if run.returncode:
                    raise ValueError(run.stdout+run.stderr)
                raw = bytearray((temp/(src.stem+'.dds')).read_bytes())
                if semantic == '_col' and struct.unpack_from('<I', raw, 128)[0] in (71, 74, 77, 98):
                    struct.pack_into('<I', raw, 128, struct.unpack_from('<I', raw, 128)[0]+1)  # albedo is sRGB
                dest.write_bytes(raw); files[target] = {'_type': 'txtr', '_path': target, '$disableStreaming': True}
                converted[identity] = target
            textures[slot] = converted[identity]; proof.append(dict(semantic=semantic, source=src.name, target=textures[slot]))
        if '0' not in textures:
            deferred[name] = 'No resolved base colour'; continue
        native_name = mapping['materials'][name]['name']
        paths = [f for f in files if f.startswith('material/') and f.endswith('.rpak') and (assets/f).with_suffix('.json').exists()
                 and json.loads((assets/f).with_suffix('.json').read_text()).get('name') in (native_name, native_name+'_colpass')]
        if not paths:
            deferred[name] = 'No native material entry'; continue
        for f in paths:
            target = (assets/f).with_suffix('.json'); native = json.loads(target.read_text())
            native['$textures'].update(textures); write(target, native)
        layered = len([t for t in types.values() if t == '_col']) > 1
        mapping['materials'][name].update(recovered=True, textures=textures, source=aliases.get(name, name),
            native_source_channels='Shared-pack original maps'+(', first layer of a layered material' if layered else ''))
        rows.append(dict(material=name, source_material=spec['name'], triangles=mapping['missing'].get(name, 0),
                         layered=layered, textures=proof))
    manifest['files'] = [f for p, f in files.items() if p not in original]+manifest['files']  # new textures first
    write(mats/'build.json', manifest); write(mats/'mapping.json', mapping)
    with (mats/'build.log').open('w') as log:
        subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str((mats/'build.json').resolve())], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    built = mats/'build'/(slug+'_world.rpak')
    report = dict(recovered=len(rows), recovered_triangles=sum(r['triangles'] for r in rows), deferred=deferred,
                  materials=rows, unique_new_textures=len(converted), world_rpak_bytes=built.stat().st_size)
    if package:
        target = Path(package)/'paks'/built.name; temp = target.with_suffix('.new.rpak')
        shutil.copy2(built, temp); temp.replace(target)
        write(Path(package)/'shared-materials.json', report)
    write(folder(ident)/'shared-materials.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'materials'}, indent=2))


if __name__ == '__main__':
    recover(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
