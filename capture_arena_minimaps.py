"""Collect native radar screenshots, configuration queries and reload evidence.

Requires the isolated Northstar controller with both map packages installed.
Runtime state and credentials stay in ignored output directories.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from build_arena_minimaps import MAPS, OUT, ROOT, digest
sys.path.insert(0, str(ROOT/'test-harness'))
from harness import Controller

SHOTS = {
    'ArenaComposite': [
        ('center-north', [0, 2200, 900], [22, 90, 0]),
        ('center-east', [0, 2200, 900], [22, 0, 0]),
        ('west-spawn', [-3296, 1000, 220], [0, 90, 0]),
        ('east-spawn', [3296, 1000, 220], [0, 270, 0]),
        ('north-platform', [0, 5000, 450], [0, 90, 0]),
    ],
    'PhaseRunner': [
        ('center-north', [0, -2600, -1216], [0, 90, 0]),
        ('center-east', [0, -2600, -1216], [0, 0, 0]),
        ('west-building', [-6080, -1530.2, -773.9], [10, 90, 0]),
        ('east-building', [6283.9, -1417, -773.9], [10, 270, 0]),
        ('tunnel', [-2163.4, 3016.3, -910.4], [0, 0, 0]),
    ],
}


def capture(package):
    config = MAPS[package]
    c = Controller()
    state = c.wait_map(config['map'], timeout=300)
    # Let the multiplayer countdown and automatic spawn complete before moving.
    time.sleep(20)
    folder = OUT/'runtime'/package
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for name, origin, angles in SHOTS[package]:
        c.camera(origin, angles, fov=90, settle=3)
        capture = c.capture(package.lower()+'-minimap-'+name)
        dest = folder/(name+'.png')
        shutil.copy2(capture['path'], dest)
        assert digest(dest) == capture['sha256']
        assert capture['state']['game_pid'] == state['game_pid']
        records.append(dict(name=name, origin=origin, angles=angles, fov=90,
                            screenshot=str(dest.relative_to(ROOT)), native_capture=capture))
    command = ('script_client printt("ARENA_MINIMAP_'+package+'", '
               'Minimap_GetAssetForKey("minimap"), Minimap_GetFloatForKey("pos_x"), '
               'Minimap_GetFloatForKey("pos_y"), Minimap_GetFloatForKey("scale"))')
    c.command('ui', 'console', command=command)
    time.sleep(1)
    logs = c.export_logs()
    assert not logs['script_errors'], logs['script_errors']
    text = (c.run/'game.log').read_text(errors='replace')
    prefix = 'ARENA_MINIMAP_'+package+' $"overviews/'+config['map']+'" '
    lines = [s for s in text.splitlines() if prefix in s]
    assert lines, 'Native overview query missing: '+prefix
    marker = lines[-1].split(prefix)[-1]
    actual = [float(s) for s in marker.split()]
    assert len(actual) == 3 and all(abs(a-b)<.0001 for a,b in zip(actual, [*config['corner'], config['scale']]))
    staged = Path(c.session['game'])/c.session['profile']/'mods'/('PhaseRunner.Preview' if package=='ArenaComposite' else 'MapTest.Extra')
    checked = []
    for rel in ('paks/'+config['pack']+'.rpak', 'mod/resource/overviews/'+config['map']+'.txt', 'paks/rpak.json'):
        assert digest(staged/rel) == digest(ROOT/'northstar'/package/rel)
        checked.append(rel)
    report = dict(package=package, map=config['map'], game_pid=state['game_pid'],
                  run=str(c.run), shots=records, configuration_query=marker,
                  staged_files_verified=checked, logs=logs)
    (folder/'captures.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(package=package, captures=len(records), game_pid=state['game_pid'],
                         config_verified=True, script_errors=logs['script_errors'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', choices=MAPS)
    capture(parser.parse_args().package)
