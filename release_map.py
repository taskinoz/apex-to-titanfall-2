"""Stage, accept and package a new version of any map port (release_thunderdome.py's process, for every mod).

  python release_map.py stage <mod> <version> <source package>
  python release_map.py acceptance <mod> <version>   Northstar 1.31.14: every declared spawn clear and supported in PS
                                                      and FFA, both team respawns, weapon fire, postmatch lobby, stock
                                                      and map reload, clean logs
  python release_map.py finalize <mod> <version> <screenshot>   northstar/<mod>, validation receipt, player ZIP

The source package's build receipts (RECEIPTS) go into the public validation receipt, without local paths.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from repair_thunderdome import digest, write
import local_paths

ROOT = Path(__file__).resolve().parent
RECEIPTS = ('shadow-weld.json', 'visibility-cells-disabled.json', 'sun-rebake.json', 'sun-probes.json', 'csm-props.json', 'cubemaps.json',
            'native-prop-collision.json', 'collision-weld.json', 'visibility-cells.json', 'small-prop-fades.json',
            'pipeline.json')
PRIVATE = ('source', 'shots', 'path')  # local paths inside receipts
ACCEPTED = ('mod/resource/', 'mod/scripts/')  # staged from northstar/<mod>, not the build


def paths(mod, version):
    out = ROOT/'output'/f'{mod}-{version}'
    return out, out/'candidate'/mod, ROOT/'docs/candidates'/mod.lower()/f'port-{version}'


def map_name(mod):
    from package_player_mods import RELEASES
    return RELEASES[mod]['map']


def stage(mod, version, source):
    from package_player_mods import runtime_files
    out, candidate, _ = paths(mod, version); source = Path(source)
    if candidate.exists():
        raise ValueError('Staged candidate already exists: '+str(candidate))
    accepted = ROOT/'northstar'/mod
    for p in runtime_files(source):
        rel = p.relative_to(source); dest = candidate/rel; dest.parent.mkdir(parents=True, exist_ok=True)
        if p.name == 'mod.json':
            info = json.loads((accepted/'mod.json').read_text(encoding='utf-8-sig')); info['Version'] = version; write(dest, info)
        elif rel.as_posix().startswith(ACCEPTED) or rel.name.endswith('_presentation.rpak'):
            # The map builds change none of these; installed copies can carry regenerated presentation packs.
            shutil.copy2(accepted/rel, dest)
        else:
            os.link(p, dest)
    (out/'source.txt').write_text(str(source)+'\n')
    print('Staged', len(runtime_files(candidate)), 'runtime files', flush=True)


def acceptance(mod, version):
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    from validate_anniversary_native import postmatch
    from package_player_mods import runtime_files
    out, candidate, _ = paths(mod, version); level = map_name(mod)
    try:
        Controller().request('/shutdown', {}); time.sleep(2)
    except (OSError, ValueError, RuntimeError):
        pass
    command = [sys.executable, str(ROOT/'test-harness/harness.py'), 'start', '--profile', 'R2Anniversary14',
               '--runtime', str(ROOT/'tools/northstar-v1.31.14/runtime/R2Northstar'),
               '--launcher', str(local_paths.path('TITANFALL2_GAME')/'NorthstarAnniversaryLauncher.exe'), '--package', str(candidate),
               '--map', level, '--mode', 'ps', '--timeout', '600',  # Origin sign-in can take minutes
                '--extra-package', str(ROOT/'northstar/ApexMaps.UI')]
    with (out/'launch.log').open('w') as log:
        if subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode:
            raise RuntimeError('Native launch failed; see '+str(out/'launch.log'))
    c = Controller()
    mounted = next(p.parent for p in (Path(c.request('/status')['profile'])/'mods').glob('*/mod.json')
                   if json.loads(p.read_text(encoding='utf-8-sig')).get('Name') == mod)
    for p in runtime_files(candidate):
        assert digest(p) == digest(mounted/p.relative_to(candidate)), 'Mounted runtime mismatch'

    def living():
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            s = c.request('/status'); p = s.get('contexts', {}).get('client', {})
            if not s['game_running']:
                raise RuntimeError('Owned game exited')
            if p.get('level') == level and p.get('alive') and p.get('health', 0) > 0:
                return
            time.sleep(.5)
        raise RuntimeError('No living native player')
    reports = []
    try:
        for mode in ('ps', 'ffa'):
            if mode != 'ps':
                c.load(level, mode, 240)
            living(); time.sleep(3); r = c.command('server', 'mode_check')['data']; write(out/f'mode-{mode}.json', r)
            bad = [p for p in r['liveSpawns'] if not (p['clear'] and p['supported'])]
            declared = sum(r['entities'].get(k, 0) for k in ('info_spawnpoint_human_start', 'info_spawnpoint_human',
                                                           'info_spawnpoint_titan_start', 'info_spawnpoint_titan'))
            assert r['mode'] == mode and len(r['liveSpawns']) == declared > 0, 'Unexpected spawn set'
            assert not bad, f'{len(bad)} spawns not clear/supported: '+json.dumps(bad)
            for team in ((2, 3) if mode != 'ffa' else ()):
                c.command('server', 'respawn', team=team); living()
            c.command('ui', 'console', command='+attack'); time.sleep(.35); c.command('ui', 'console', command='-attack')
            time.sleep(1); living(); reports.append(r)
            print('Native mode passed:', mode, declared, 'supported and clear spawns', flush=True)
        postmatch(c, f'{mod} {version}')
        c.load('mp_coliseum', 'ps', 240); time.sleep(3)
        c.load(level, 'ps', 240); living(); time.sleep(3)
        shot = c.capture('release-reload')
        logs = c.export_logs()
        assert not logs['script_errors'] and not logs['native_crashes'], 'Native errors recorded'
    finally:
        c.request('/shutdown', {})
    write(out/'runtime-validation.json', dict(passed=True, version=version, runtime='1.31.14', modes=reports,
          both_team_respawns=True, weapon_fire_exercised=True, postmatch_lobby=True, stock_and_converted_reload=True,
          mounted_runtime_hash_verified=True, logs=logs, reload_capture=shot, single_client_only=True))
    print('PS/FFA, postmatch and stock/map reload acceptance passed', flush=True)


def finalize(mod, version, screenshot):
    from package_player_mods import RELEASES, runtime_files, write_player_zip, player_readme
    out, candidate, docs = paths(mod, version); source = Path((out/'source.txt').read_text().strip())
    # RELEASE_ZIP_DIR: build the ZIP on another drive when output/'s is full (5 November 2026: D: was).
    import package_player_mods
    if os.environ.get('RELEASE_ZIP_DIR'):
        package_player_mods.OUTPUT = Path(os.environ['RELEASE_ZIP_DIR']).resolve()
    release = package_player_mods.OUTPUT/f'{mod}-{version}-Northstar.zip'
    if release.exists():
        raise ValueError('Release archive already exists; do not overwrite it')
    if RELEASES[mod]['version'] != version:
        raise ValueError('Update the package_player_mods.py release entry first')
    proof = json.loads((out/'runtime-validation.json').read_text())
    assert proof['passed'] and proof['version'] == version
    package = ROOT/'northstar'/mod; backup = out/'working-before'
    if not backup.exists():
        shutil.copytree(package, backup)
    for p in runtime_files(candidate):
        dest = package/p.relative_to(candidate); dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix+'.releasing'); shutil.copy2(p, temp); temp.replace(dest)
    stale = {p.relative_to(package) for p in runtime_files(package)}-{p.relative_to(candidate) for p in runtime_files(candidate)}
    if stale:
        raise ValueError('Accepted mod has runtime files the candidate lacks: '+', '.join(map(str, stale)))
    shutil.copy2(screenshot, package/'screenshot.png')
    (package/'README.md').write_text(player_readme(mod), encoding='utf-8')
    bsp = next((package/'mod/maps').glob('*.bsp'))
    status = json.loads((package/'build-status.json').read_text())
    status.update(version=version, bsp_sha256=digest(bsp), client_verified=True, release_ready=True,
                  native_validation=docs.relative_to(ROOT).as_posix()+'/validation.json')
    write(package/'build-status.json', status)
    docs.mkdir(parents=True, exist_ok=True)
    clean = dict(proof); clean['logs'] = {k: v for k, v in proof['logs'].items() if k != 'path'}
    clean['reload_capture'] = {k: v for k, v in proof['reload_capture'].items() if k in ('sha256', 'width', 'height')}
    clean['build'] = {}
    for name in RECEIPTS:
        if (source/name).exists():
            clean['build'][name] = {k: v for k, v in json.loads((source/name).read_text()).items() if k not in PRIVATE}
    clean['runtime_sha256'] = {p.relative_to(package).as_posix(): digest(p) for p in runtime_files(package)}
    write(docs/'validation.json', clean)
    result = write_player_zip(package, release); write(docs/'release.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    action, *a = sys.argv[1:]
    {'stage': stage, 'acceptance': acceptance, 'finalize': finalize}[action](*a)
