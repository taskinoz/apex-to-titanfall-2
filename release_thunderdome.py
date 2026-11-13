"""Thunderdome 0.3.0: native static props, visibility cells, welded prop collision. Same acceptance as 0.2.0.

The runtime comes from the native-prop pipeline output (run_prop_pipeline.py); 0.2.0 was packaged locally but never
published, so the new build takes 0.3.0.

  python release_thunderdome.py stage       runtime files from the pipeline output with mod.json at VERSION
  python release_thunderdome.py acceptance  Northstar 1.31.14: every spawn clear/supported in PS and FFA (96; 0.2.0
                                            had 88), both team
                                            respawns, weapon fire, postmatch lobby, stock and map reload, clean logs
  python release_thunderdome.py finalize    northstar/ArenaThunderdome, validation receipt and the player ZIP
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
VERSION = '0.3.0'
SOURCE = local_paths.path('APEX_WORK_ROOT')/'new-arena-ports/candidates/ArenaThunderdome-uv-props'
OUT = ROOT/'output'/f'thunderdome-{VERSION}'
CANDIDATE = OUT/'candidate/ArenaThunderdome'
DOCS = ROOT/'docs/candidates/thunderdome'/f'port-{VERSION}'
REPORTS = ('native-prop-collision.json', 'collision-weld.json', 'visibility-cells.json',
           'small-prop-fades.json', 'pipeline.json')


def stage():
    from package_player_mods import runtime_files
    if CANDIDATE.exists():
        raise ValueError('Staged candidate already exists: '+str(CANDIDATE))
    for p in runtime_files(SOURCE):
        dest = CANDIDATE/p.relative_to(SOURCE); dest.parent.mkdir(parents=True, exist_ok=True)
        if p.name == 'mod.json':
            mod = json.loads(p.read_text(encoding='utf-8-sig')); mod['Version'] = VERSION; write(dest, mod)
        else:
            os.link(p, dest)
    print('Staged', len(runtime_files(CANDIDATE)), 'runtime files', flush=True)


def acceptance():
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    from validate_anniversary_native import postmatch
    try:
        Controller().request('/shutdown', {}); time.sleep(2)
    except (OSError, ValueError, RuntimeError):
        pass
    command = [sys.executable, str(ROOT/'test-harness/harness.py'), 'start', '--profile', 'R2Anniversary14',
               '--runtime', str(ROOT/'tools/northstar-v1.31.14/runtime/R2Northstar'),
               '--launcher', str(local_paths.path('TITANFALL2_GAME')/'NorthstarAnniversaryLauncher.exe'), '--package', str(CANDIDATE),
               '--map', 'mp_thunderdome', '--mode', 'ps', '--timeout', '240', '--extra-package', str(ROOT/'northstar/ApexMaps.UI')]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/'launch.log').open('w') as log:
        if subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode:
            raise RuntimeError('Native launch failed; see '+str(OUT/'launch.log'))
    c = Controller()
    mounted = next(p.parent for p in (Path(c.request('/status')['profile'])/'mods').glob('*/mod.json')
                   if json.loads(p.read_text(encoding='utf-8-sig')).get('Name') == 'ArenaThunderdome')
    from package_player_mods import runtime_files
    for p in runtime_files(CANDIDATE):
        assert digest(p) == digest(mounted/p.relative_to(CANDIDATE)), 'Mounted runtime mismatch'

    def living():
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            s = c.request('/status'); p = s.get('contexts', {}).get('client', {})
            if not s['game_running']:
                raise RuntimeError('Owned game exited')
            if p.get('level') == 'mp_thunderdome' and p.get('alive') and p.get('health', 0) > 0:
                return
            time.sleep(.5)
        raise RuntimeError('No living native player')
    reports = []
    try:
        for mode in ('ps', 'ffa'):
            if mode != 'ps':
                c.load('mp_thunderdome', mode, 240)
            living(); time.sleep(3); r = c.command('server', 'mode_check')['data']
            bad = [p for p in r['liveSpawns'] if not (p['clear'] and p['supported'])]
            write(OUT/f'mode-{mode}.json', r)
            declared = r['entities']['info_spawnpoint_human_start']+r['entities']['info_spawnpoint_human']
            assert r['mode'] == mode and len(r['liveSpawns']) == declared >= 88, 'Unexpected spawn set'
            assert not bad, f'{len(bad)} spawns not clear/supported: '+json.dumps(bad)
            for team in ((2, 3) if mode != 'ffa' else ()):
                c.command('server', 'respawn', team=team); living()
            c.command('ui', 'console', command='+attack'); time.sleep(.35); c.command('ui', 'console', command='-attack')
            time.sleep(1); living(); reports.append(r)
            print('Native mode passed:', mode, declared, 'supported and clear spawns', flush=True)
        postmatch(c, 'Thunderdome '+VERSION)
        c.load('mp_coliseum', 'ps', 240); time.sleep(3)
        c.load('mp_thunderdome', 'ps', 240); living(); time.sleep(3)
        shot = c.capture('thunderdome-reload')
        logs = c.export_logs()
        assert not logs['script_errors'] and not logs['native_crashes'], 'Native errors recorded'
    finally:
        c.request('/shutdown', {})
    write(OUT/'runtime-validation.json', dict(passed=True, version=VERSION, runtime='1.31.14', modes=reports,
          both_team_respawns=True, weapon_fire_exercised=True, postmatch_lobby=True, stock_and_converted_reload=True,
          mounted_runtime_hash_verified=True, logs=logs, reload_capture=shot, single_client_only=True))
    print('PS/FFA, postmatch and stock/map reload acceptance passed', flush=True)


def finalize(screenshot):
    from package_player_mods import RELEASES, runtime_files, write_player_zip, player_readme
    release = ROOT/'output'/f'ArenaThunderdome-{VERSION}-Northstar.zip'
    if release.exists():
        raise ValueError('Release archive already exists; do not overwrite it')
    if RELEASES['ArenaThunderdome']['version'] != VERSION:
        raise ValueError('Update the package_player_mods.py release entry first')
    proof = json.loads((OUT/'runtime-validation.json').read_text())
    assert proof['passed'] and proof['version'] == VERSION
    package = ROOT/'northstar/ArenaThunderdome'; backup = OUT/'working-before'
    if not backup.exists():
        shutil.copytree(package, backup)
    for p in runtime_files(CANDIDATE):
        dest = package/p.relative_to(CANDIDATE); dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix+'.releasing'); shutil.copy2(p, temp); temp.replace(dest)
    stale = {p.relative_to(package) for p in runtime_files(package)}-{p.relative_to(CANDIDATE) for p in runtime_files(CANDIDATE)}
    if stale:
        raise ValueError('Accepted mod has runtime files the candidate lacks: '+', '.join(map(str, stale)))
    shutil.copy2(screenshot, package/'screenshot.png')
    (package/'README.md').write_text(player_readme('ArenaThunderdome'), encoding='utf-8')
    status = json.loads((package/'build-status.json').read_text())
    status.update(version=VERSION, bsp_sha256=digest(package/'mod/maps/mp_thunderdome.bsp'), client_verified=True,
                  release_ready=True, native_validation=f'docs/candidates/thunderdome/port-{VERSION}/validation.json')
    write(package/'build-status.json', status)
    DOCS.mkdir(parents=True, exist_ok=True)
    clean = dict(proof); clean['logs'] = {k: v for k, v in proof['logs'].items() if k != 'path'}
    clean['reload_capture'] = {k: v for k, v in proof['reload_capture'].items() if k in ('sha256', 'width', 'height')}
    clean['build'] = {name: json.loads((SOURCE/name).read_text()) for name in REPORTS}
    clean['build']['pipeline.json'].pop('source')  # a local build path
    clean['runtime_sha256'] = {p.relative_to(package).as_posix(): digest(p) for p in runtime_files(package)}
    write(DOCS/'validation.json', clean)
    result = write_player_zip(package, release); write(DOCS/'release.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    {'stage': stage, 'acceptance': acceptance}.get(sys.argv[1], lambda: finalize(sys.argv[2]))()
