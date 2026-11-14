"""Give a map port its own level pack, so it no longer mounts on mp_coliseum.rpak.

Every port aliased `mp_<map>.rpak` to the stock `mp_coliseum.rpak` and listed its packs as Postloads of it. Titanfall
loads a map's level pack by the map's name, and the ports' world materials point at assets that only Coliseum's
level pack holds. Postloads are global, though: loading any converted map loaded every installed port's packs, and
with eight ports installed the game ran out of memory (Skulltown 0.1.0, 14 November 2026). Keying the packs to a map
regex or to the map's patch pack loads them out of order and draws everything pink.

What the ports take from Coliseum is small. Skulltown's world pack references 1,334 Coliseum ids: the shader set
`uberSamp2222_wld` and the three depth-pass materials `code_private/depth_{shadow,prepass,vsm}`, which use
`uberDepth_wld` and `uberDepthVsm_wld`; no textures. This builds `mp_<map>.rpak` holding exactly the Coliseum assets
the port's packs reference, plus their own dependencies, with RePak, at Coliseum's original asset paths
(docs/conversion/coliseum-asset-names.json). RePak derives asset ids from paths, so the copies have Coliseum's ids
and the port's packs need no change. Shader bytecode, input layouts and material constants are copied unchanged.
Then rpak.json drops the level alias and lists the port's packs as Postloads of its own level pack.

  python standalone_map_pak.py <mod folder> <map name>          e.g. northstar/ArenaSkulltown mp_skulltown
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import local_paths
from extract_native_material import NativePak
from extract_world_glass_shader import shader

ROOT = Path(__file__).resolve().parent
COLISEUM = ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak'   # decompressed stock mp_coliseum.rpak
COMMON = ROOT/'inputs/tf2-rpak-work/common.raw.rpak'       # shared shaders a Coliseum shader set may use
NAMES = ROOT/'docs/conversion/coliseum-asset-names.json'
REPAK = ROOT/'tools/repak/RePak.exe'
DEPTH = ('$depthShadowMaterial', '$depthPrepassMaterial', '$depthVSMMaterial', '$colpassMaterial')


def guid_refs(pak):
    """The pack's id-reference table: (page, offset) of every 8-byte asset id the loader resolves."""
    d = pak.data; streaming, segments, pages, _ = struct.unpack_from('<4H', d, 56)
    pointers, assets, refs = struct.unpack_from('<3I', d, 64)
    at = 88+streaming+segments*16+pages*12+pointers*8+assets*72
    return [struct.unpack_from('<2I', d, at+8*i) for i in range(refs)]


def referenced(paks, stock):
    """Coliseum asset ids the port's packs reference, closed over the Coliseum assets' own dependencies."""
    want = set()
    for p in paks:
        for r in guid_refs(p):
            g = struct.unpack_from('<Q', p.data, p.address(r))[0]
            if g in stock:
                want.add(g)
    queue = list(want)
    while queue:
        g = queue.pop(); pak, a = stock[g]
        if a['type'] == 'matl':
            spec, _ = pak.material(a)
            deps = [spec['shaderSet'], *spec['$textures'].values(), *(spec[f] for f in DEPTH)]
        elif a['type'] == 'shds':
            h = pak.address(a['header']); deps = ['0x%X' % v for v in struct.unpack_from('<2Q', pak.data, h+72)]
        else:
            deps = []
        for d in deps:
            v = int(d, 16)
            if v and v in stock and v not in want:
                want.add(v); queue.append(v)
    return want


_SHARED = {}


def shared():
    if not _SHARED:
        pak = NativePak(COMMON); _SHARED.update({a['guid']: (pak, a) for a in pak.assets})
    return _SHARED


def build(mod, map_name, work):
    mod = Path(mod); paks_dir = mod/'paks'; work = Path(work)
    config = json.loads((paks_dir/'rpak.json').read_text())
    names = {int(k, 16): v for k, v in json.loads(NAMES.read_text())['assets'].items()}
    col = NativePak(COLISEUM); stock = {a['guid']: (col, a) for a in col.assets}
    own = [NativePak(p) for p in sorted(paks_dir.glob('*.rpak')) if p.name != map_name+'.rpak']
    want = referenced(own, stock)
    kinds = {g: stock[g][1]['type'] for g in want}
    if any(k not in ('matl', 'shds', 'shdr') for k in kinds.values()):
        raise ValueError('Coliseum textures or other asset types are referenced; extend the copy: '
                         + str({hex(g): k for g, k in kinds.items() if k not in ('matl', 'shds', 'shdr')}))
    assets = work/'assets'; shutil.rmtree(work, ignore_errors=True); assets.mkdir(parents=True)
    files = []
    for g in sorted(g for g, k in kinds.items() if k == 'shds'):
        pak, a = stock[g]; h = pak.address(a['header']); vs, ps = struct.unpack_from('<2Q', pak.data, h+72)
        vt, pt, samplers = struct.unpack_from('<3H', pak.data, h+24); first, resources = struct.unpack_from('<2H', pak.data, h+30)
        lookup = lambda v: stock.get(v) or shared()[v]
        pixel, _ = shader(*lookup(ps)); vertex, _ = shader(*lookup(vs))
        path = names[g]; target = (assets/path).with_suffix('.msw'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'MSW\x03\x01'+struct.pack('<2Q3H2B2I', ps, vs, pt, vt, samplers, first, resources, 37, 37+len(pixel))
                           + pixel+vertex)
        files.append(dict(_type='shds', _path=path))
    for g in sorted(g for g, k in kinds.items() if k == 'matl'):
        pak, a = stock[g]; spec, uber = pak.material(a); path = names[g]
        spec['shaderSet'] = names[int(spec['shaderSet'], 16)]
        for f in DEPTH:
            v = int(spec[f], 16)
            spec[f] = names[v] if v in want else spec[f]
        spec['blendStates'] = (spec['blendStates']+['0x0']*8)[:8]
        target = assets/path; target.parent.mkdir(parents=True, exist_ok=True)
        target.with_suffix('.json').write_text(json.dumps(spec, indent=2)); target.with_suffix('.uber').write_bytes(uber)
        files.append(dict(_type='matl', _path=path))
    manifest = dict(version=7, name=map_name, keepDevOnly=True, assetsDir=str(assets.resolve()), outputDir=str((work/'build').resolve()),
                    compressLevel=0, hasDynamicLibrary=False, files=files)
    (work/'build.json').write_text(json.dumps(manifest, indent=2))
    run = subprocess.run([str(REPAK), str((work/'build.json').resolve())], capture_output=True, text=True)
    (work/'build.log').write_text(run.stdout+run.stderr); run.check_returncode()
    built = work/'build'/(map_name+'.rpak'); made = {a['guid'] for a in NativePak(built).assets}
    missing = {g for g, k in kinds.items() if k != 'shdr'}-made
    if missing:
        raise ValueError('Rebuilt level pack lacks Coliseum ids: '+', '.join(hex(g) for g in missing))
    shutil.copy2(built, paks_dir/built.name)
    # Mount the port's packs on its own level pack instead of the shared Coliseum alias.
    aliases = {k: v for k, v in config.get('Aliases', {}).items() if k != map_name+'.rpak'}
    postload = {k: (v if v == 'common.rpak' else map_name+'.rpak') for k, v in config.get('Postload', {}).items()}
    new = dict(Aliases=aliases, Postload=postload) if aliases else dict(Postload=postload)
    (paks_dir/'rpak.json').write_text(json.dumps(new, indent=2)+'\n')
    report = dict(map=map_name, level_pack=built.name, level_pack_bytes=built.stat().st_size,
                  copied={k: sorted(names[g] for g in want if kinds[g] == k) for k in ('shds', 'matl')},
                  shaders_embedded=sorted(names[g] for g in want if kinds[g] == 'shdr'), same_asset_ids=True)
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    mod, map_name = sys.argv[1], sys.argv[2]
    build(mod, map_name, Path(sys.argv[3]) if len(sys.argv) > 3 else
          local_paths.path('APEX_WORK_ROOT')/'new-arena-ports/level-paks'/map_name)
