"""Extract a map from the current retail Apex install (no VPKs; maps live in RPaks).

Since the wrapped filesystem replaced VPKs, a map's BSP header and lumps are
`wrap` assets in `<map>_client_perm.rpak` / `<map>_client_temp.rpak`
(`maps/<map>.bsp`, `maps/<map>.bsp.NNNN.bsp_lump.client`), and its models,
materials and textures are in `<map>.rpak`. Packs are Oodle-compressed; the
locally built upstream RSX (r-ex/rsx, plus two local patches: raw BSP export
and `--exportformats`) reads them.

Output (WORK/<map>):
  maps/<map>.bsp + <map>.bsp.NNNN.bsp_lump   (rBSP v52.1, readable by bsp_tool) and <map>_*.ent
  models/<model>/<model>_LOD<n>.cast           (read with read_cast.py)
  assets.csv                                   (asset list of every pack)

  python extract_apex_current.py mp_rr_thunderdome [--no-models]
"""
import argparse
import shutil
import subprocess
from pathlib import Path

APEX = Path('D:/Games/Apex/paks/Win64')
RSX = Path('D:/Games/ApexToTitanfallWork/rsx-latest/bin/Release_NoGui/rsx.exe')
WORK = Path('D:/Games/ApexToTitanfallWork/apex-current')


def rsx(*args, log):
    with open(log, 'w', encoding='utf-8') as out:
        run = subprocess.run([str(RSX), '-nogui', '-nocachedb', *map(str, args)], stdout=out, stderr=subprocess.STDOUT)
    if run.returncode:
        raise RuntimeError(f'RSX failed ({run.returncode}); see {log}')


def extract(name, models=True):
    dest = WORK/name; dest.mkdir(parents=True, exist_ok=True)
    packs = [APEX/(name+s+'.rpak') for s in ('', '_client_perm', '_client_temp')]
    for p in packs:
        if not p.exists():
            raise FileNotFoundError(p)
    rsx('--list', dest/'assets.csv', '--listformat', 'csv', *packs, log=dest/'list.log')
    # BSP and lumps.
    raw = dest/'raw'
    shutil.rmtree(raw, ignore_errors=True)
    rsx('-export', '-exportfullpaths', '--exporttypes', 'wrap', '--exportdir', raw, *packs[1:], log=dest/'wrap.log')
    maps = dest/'maps'; maps.mkdir(exist_ok=True); count = 0
    for f in (raw/'wrap/maps').glob(name+'.bsp*'):
        if f.suffix == '.obj':
            continue
        target = f.name.replace('.client.bsp_lump', '.bsp_lump')  # bsp_tool's external lump naming
        shutil.move(str(f), str(maps/target)); count += 1
    for f in (raw/'wrap/maps').glob(name+'_*.ent'):  # env, fx, script, snd, spawn entity partitions
        shutil.move(str(f), str(maps/f.name)); count += 1
    overview = raw/'wrap/resource/overviews'/(name+'.txt')
    if overview.exists():
        (dest/'resource/overviews').mkdir(parents=True, exist_ok=True); shutil.move(str(overview), str(dest/'resource/overviews'/overview.name))
    header = (maps/(name+'.bsp')).read_bytes()[:8]
    if header[:4] != b'rBSP':
        raise ValueError('Exported BSP header is not rBSP')
    version = int.from_bytes(header[4:8], 'little')
    print(name, 'BSP', version & 0xFFFF, '.', version >> 16, count, 'files', flush=True)
    if models:
        out = dest/'models'
        rsx('-export', '--exporttypes', 'mdl_', '--exportformats', 'mdl_=CAST', '--exportthreads', '8',
            '--exportdir', dest/'raw-models', packs[0], log=dest/'models.log')
        out.mkdir(exist_ok=True); n = 0
        for folder in (dest/'raw-models/mdl').glob('*'):
            if folder.is_dir():
                shutil.rmtree(out/folder.name, ignore_errors=True); shutil.move(str(folder), str(out/folder.name)); n += 1
        print(name, n, 'models (Cast LODs)', flush=True)
        # Collision: RSX writes each model's Respawn BVH4 collision as a binary STL (build_composite_map.read_stl).
        rsx('-export', '--exporttypes', 'mdl_', '--exportformats', 'mdl_=STL (Respawn Physics)', '--exportthreads', '8',
            '--exportdir', dest/'raw-collision', packs[0], log=dest/'collision.log')
        stl = 0
        for f in (dest/'raw-collision/mdl').glob('*/*.stl'):
            if (out/f.parent.name).is_dir():
                shutil.move(str(f), str(out/f.parent.name/f.name)); stl += 1
        shutil.rmtree(dest/'raw-collision', ignore_errors=True)
        print(name, stl, 'model collision STLs', flush=True)
    shutil.rmtree(raw, ignore_errors=True); shutil.rmtree(dest/'raw-models', ignore_errors=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('map'); p.add_argument('--no-models', action='store_true')
    a = p.parse_args(); extract(a.map, not a.no_models)
