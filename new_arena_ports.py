"""Isolated, reproducible workspaces for the three approved additional ports."""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = '0.3.1'
GAME = Path('D:/Games/R5Reloaded/R5R Library/LIVE')
WORK = Path(os.environ.get('APEX_PORT_WORK', str(ROOT / 'output/new-arena-ports'))).resolve()
CONFIG = {
    'overflow': dict(name='Overflow', source='mp_rr_aqueduct', target='mp_overflow',
        package='ArenaOverflow', offset=[0, 0, 0],
        bounds=[[-9000, -11000, -6000], [9000, 3500, 7500]]),
    'party-crasher': dict(name='Party Crasher', source='mp_rr_party_crasher', target='mp_party_crasher',
        package='ArenaPartyCrasher', offset=[0, 0, 0],
        bounds=[[-10000, -8500, -5000], [10000, 11000, 9000]]),
    'firing-range': dict(name='Firing Range', source='mp_rr_canyonlands_staging', target='mp_apex_firing_range',
        package='ApexFiringRange', offset=[-32000, 7000, 28000],
        bounds=[[-14500, -13000, -6000], [14500, 14500, 12000]]),
    # A World's Edge area Apex used as an Arenas map (docs/candidates/poi-survey-2026-10-19.md).
    'thermal-station': dict(name='Thermal Station', source='mp_rr_desertlands_mu2', target='mp_thermal_station',
        package='ArenaThermalStation', offset=[19900, 20500, 4000],
        bounds=[[-6800, -6500, -2500], [6800, 6500, 7000]]),
}


def folder(ident):
    return WORK / ident


def source_bsp(ident):
    return ROOT / 'inputs/candidates' / ident / 'maps' / (CONFIG[ident]['source'] + '.bsp')


def prepare_assets(ident):
    from extract_map import extract
    from decompress_rpak import decompress
    from stage_rpak_streams import stage
    c = CONFIG[ident]
    dest = folder(ident)
    dest.mkdir(parents=True, exist_ok=True)
    extract(GAME / 'vpk' / ('englishclient_' + c['source'] + '.bsp.pak000_dir.vpk'),
            ROOT / 'inputs/candidates' / ident)
    extract(GAME / 'vpk' / ('englishserver_' + c['source'] + '.bsp.pak000_dir.vpk'),
            dest / 'server', 'maps/*')
    tool = dest / 'legion'
    tool.mkdir(exist_ok=True)
    for name in ('LegionPlus.exe', 'LegionPlus.cfg', 'binkawin64.dll', 'mileswin64.dll'):
        target = tool / name
        if not target.exists():
            shutil.copy2(ROOT / 'tools/composite-legion' / name, target)
    rows = []
    for suffix in ('', '_loadscreen'):
        name = c['source'] + suffix
        original = GAME / 'paks/Win64' / (name + '.rpak')
        pak = dest / 'paks' / (name + '.rpak')
        pak.parent.mkdir(exist_ok=True)
        if not pak.exists():
            header = original.read_bytes()[:128]
            flags = struct.unpack_from('<H', header, 6)[0]
            if flags & 0x8000:
                decompress(original, pak, normalize=True)
            elif not flags & 0x100:
                shutil.copy2(original, pak)
            else:
                raise ValueError('Unsupported non-ZSTD compressed source RPak')
        if not pak.with_suffix('.streams.json').exists():
            stage(pak, GAME / 'paks/Win64')
        log = dest / (name + '-export.log')
        marker = dest / (name + '-export.json')
        if not marker.exists():
            flags = ['--loadimages', '--imgfmt', 'png'] if suffix else [
                '--loadmodels', '--loadmaterials', '--mdlfmt', 'rmdl',
                '--imgfmt', 'dds', '--skinexport', '--matcpu', 'cpu']
            with log.open('w', encoding='utf-8') as output:
                run = subprocess.run([str(tool / 'LegionPlus.exe'), '--export', str(pak), *flags],
                                     cwd=tool, stdout=output, stderr=subprocess.STDOUT)
            if run.returncode:
                raise RuntimeError('Asset export failed; inspect ' + str(log))
            marker.write_text(json.dumps(dict(source=name, returncode=run.returncode,
                models=len(list((tool / 'exported_files/models').glob('*/*.rmdl'))),
                materials=len(list((tool / 'exported_files/materials').glob('*/*_albedoTexture.dds')))),
                indent=2), encoding='utf-8')
        rows.append(json.loads(marker.read_text()))
        print(ident, rows[-1], flush=True)
    (dest / 'asset-preparation.json').write_text(json.dumps(dict(config=c, exports=rows), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['assets'])
    p.add_argument('map', choices=[*CONFIG, 'all'])
    a = p.parse_args()
    for ident in CONFIG if a.map == 'all' else [a.map]:
        prepare_assets(ident)
