"""Isolated R5Reloaded map testing, native captures and Northstar comparisons."""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid

from protocol import Console, receive

HOME = Path(__file__).resolve().parent
ROOT = HOME.parent
SESSION = HOME / 'output/session.json'
SOURCE = Path('D:/Games/R5Reloaded/R5R Library/LIVE')
PROFILE = SOURCE.parent / 'MapHarness'
MARKER = '.r5-map-harness.json'
NAME = re.compile(r'[a-zA-Z0-9_-]{1,80}\Z')
MAP = re.compile(r'mp_[a-z0-9_]+\Z')
ASSETS = {'audio', 'materials', 'media', 'paks', 'stbsp', 'vpk'}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def map_name(name):
    if not MAP.fullmatch(name):
        raise ValueError('Use a raw mp_ map name')
    return name


def vector(values):
    if len(values) != 3 or any(not math.isfinite(float(v)) for v in values):
        raise ValueError('Expected three finite coordinates')
    return [float(v) for v in values]


def source_origin(origin, offset):
    return [a + b for a, b in zip(vector(origin), vector(offset))]


def stage(source=SOURCE, profile=PROFILE):
    source, profile = Path(source).resolve(), Path(profile).resolve()
    if SESSION.exists():
        active = json.loads(SESSION.read_text())
        if Path(active['profile']).resolve() == profile and owned_alive(active):
            raise RuntimeError('Stop the owned harness game before staging its files')
    if source == profile or source in profile.parents or profile in source.parents:
        raise ValueError('Harness installation must be separate from the source')
    if not (source / 'r5apex.exe').is_file():
        raise FileNotFoundError('R5Reloaded executable not found')
    marker = profile / MARKER
    if profile.exists() and not marker.exists():
        raise ValueError('Refusing to modify an unowned installation')
    if marker.exists():
        ownership = json.loads(marker.read_text())
        if ownership.get('source') != str(source) or ownership.get('owner') != 'r5-harness':
            raise ValueError('Harness installation belongs to a different owner or source')
    profile.mkdir(parents=True, exist_ok=True)
    write_json(marker, {'source': str(source), 'owner': 'r5-harness', 'version': 1})
    count = 0
    for original in source.rglob('*'):
        relative = original.relative_to(source)
        if any(p.lower() in ('logs', 'screenshots', '__pycache__', '.git') for p in relative.parts):
            continue
        if original.is_symlink():
            raise ValueError('Source contains a symlink; select a plain installation')
        if not original.is_file():
            continue
        dest = profile / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        asset = relative.parts[0].lower() in ASSETS
        if asset and dest.exists() and os.path.samefile(original, dest):
            continue
        if not asset and dest.exists() and not os.path.samefile(original, dest):
            a, b = original.stat(), dest.stat()
            if (a.st_size, a.st_mtime_ns) == (b.st_size, b.st_mtime_ns):
                continue
        # Unlink first: never overwrite a hardlink shared with the normal installation.
        if dest.exists():
            dest.unlink()
        if asset and original.drive == dest.drive:
            os.link(original, dest)
        else:
            shutil.copy2(original, dest)
        count += 1
    scripts = profile / 'platform/scripts/vscripts'
    shutil.copy2(HOME / 'scripts/_r5_map_harness.nut', scripts / '_r5_map_harness.nut')
    compile_list = scripts / 'scripts.rson'
    with compile_list.open('a', encoding='utf-8') as f:
        f.write('\nWhen: "SERVER || CLIENT"\nScripts: [ _r5_map_harness.nut ]\n')
    playlist = profile / 'platform/playlists_r5_patch.txt'
    if playlist.exists():
        content = playlist.read_text(encoding='utf-8')
        content, changes = re.subn(r'(\bdev_default\s*\{\s*inherit\s+survival_dev\s*vars\s*\{)', r'\1\n                max_players 2\n                min_players 1\n', content, count=1)
        if changes != 1:
            raise ValueError('Installed development playlist layout is unsupported')
        playlist.write_text(content, encoding='utf-8')
    return {'profile': str(profile), 'staged_files': count, 'asset_mode': 'hardlinks on same volume; independent scripts/config'}


def process_stamp(pid):
    if os.name != 'nt':
        raise RuntimeError('Native launch/stop currently requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    times = [ctypes.c_uint64() for _ in range(4)]
    try:
        exit_code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            return None
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        return times[0].value
    finally:
        kernel.CloseHandle(handle)


def stop(session=None):
    session = session or json.loads(SESSION.read_text())
    pid = session['pid']
    if not owned_alive(session):
        return {'stopped': False, 'reason': 'Owned game already exited'}
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(1, False, pid)
    if not handle:
        raise OSError('Cannot stop owned R5R game')
    try:
        if not kernel.TerminateProcess(handle, 0):
            raise OSError('Stopping owned game failed')
    finally:
        kernel.CloseHandle(handle)
    return {'stopped': True}


def owned_alive(session):
    stamp = session.get('process_stamp')
    return isinstance(stamp, int) and stamp > 0 and process_stamp(session['pid']) == stamp


def launch(name, source=SOURCE, profile=PROFILE, port=37042):
    map_name(name)
    if SESSION.exists():
        old = json.loads(SESSION.read_text())
        if owned_alive(old):
            raise RuntimeError('Harness game is running; use load or stop first')
    stage(source, profile)
    profile = Path(profile).resolve()
    with socket.socket(socket.AF_INET6) as probe:
        probe.bind(('::1', port))
    token = secrets.token_urlsafe(32)
    run = HOME / 'output' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    run.mkdir(parents=True)
    # The engine executes its own RCON config after command-line convars. Put
    # the settings in that copied config so it cannot reset the password.
    rcon_config = '\n'.join(['hostport ' + str(port), 'rcon_encryptframes 0',
        'net_processTimeBudget 0',
        'sv_rcon_useloopbacksocket 1', 'sv_rcon_maxconnections 8', 'sv_rcon_sendlogs 1',
        'sv_rcon_password "' + token + '"', 'rcon_debug 0', ''])
    for filename in ('rcon_server.cfg', 'rcon_server_dev.cfg'):
        (profile / 'platform/cfg/tools' / filename).write_text(rcon_config, encoding='utf-8')
    args = [str(profile / 'r5apex.exe'), '-launcher', '1', '-dev', '-devsdk', '-multiple', '-novid',
            '-windowed', '-w', '1280', '-h', '720', '-offline', '-playlistfile', 'playlists_r5_patch.txt',
            '+exec', 'system/offline_client.cfg', '+cl_setname', 'MapHarness',
            '+hostport', str(port), '+sv_cheats', '1', '+developer', '1', '+rcon_encryptframes', '0',
            '+sv_rcon_useloopbacksocket', '1', '+sv_rcon_maxconnections', '8', '+sv_rcon_sendlogs', '1',
            '+sv_rcon_password', token, '+setplaylist', 'dev_default', '+map', name]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (run / 'process.log').open('wb') as out:
        process = subprocess.Popen(args, cwd=profile, stdout=out, stderr=out, startupinfo=startup)
    session = {'pid': process.pid, 'process_stamp': process_stamp(process.pid), 'profile': str(profile),
               'source': str(Path(source).resolve()), 'run': str(run), 'port': port, 'password': token,
               'map': name, 'launched': time.time(), 'generation': uuid.uuid4().hex}
    if not session['process_stamp']:
        raise RuntimeError('R5R exited during startup; inspect ' + str(run / 'process.log'))
    write_json(SESSION, session)
    controller = Controller(session)
    controller.wait_signon(0, 180)
    return controller.wait_map(name, 40)


class Controller:
    def __init__(self, session=None):
        self.session = session or json.loads(SESSION.read_text())
        self.run = Path(self.session['run'])
        self.profile = Path(self.session['profile'])

    def connect(self):
        if not owned_alive(self.session):
            raise RuntimeError('Owned R5R game exited; inspect the session logs')
        return Console(self.session['port'], self.session['password'])

    def script(self, context, expression, timeout=10):
        if context not in ('server', 'client', 'ui'):
            raise ValueError('Expected server, client or UI context')
        ticket = uuid.uuid4().hex
        expression = expression.replace('$TICKET', '"' + ticket + '"')
        command = {'server':'script', 'client':'script_client', 'ui':'script_ui'}[context] + ' ' + expression
        prefix = 'R5H:' + ticket + ':'
        deadline = time.monotonic() + timeout
        with self.connect() as console:
            console.execute(command)
            while time.monotonic() < deadline:
                # SDK script prints are written to script.log but may not be
                # echoed to netcon. Both are native acknowledgements; tickets
                # ensure old log content cannot satisfy a new command.
                logs = sorted(self.profile.glob('platform/logs/*/script.log'), key=lambda p:p.stat().st_mtime, reverse=True)
                for path in logs[:2]:
                    with path.open('rb') as native:
                        native.seek(max(0, path.stat().st_size - 65536))
                        content = native.read().decode('utf-8', 'replace')
                    if prefix in content:
                        try:
                            return json.JSONDecoder().raw_decode(content.split(prefix, 1)[1])[0]
                        except json.JSONDecodeError:
                            pass  # Logger may still be flushing a partial acknowledgement.
                console.sock.settimeout(.2)
                try:
                    answer = console.read()
                except socket.timeout:
                    continue
                message = answer['message']
                if prefix in message:
                    payload = message.split(prefix, 1)[1].splitlines()[0]
                    return json.JSONDecoder().raw_decode(payload)[0]
                if 'SCRIPT ERROR' in message or 'COMPILE ERROR' in message:
                    raise RuntimeError(message[:600])
        raise TimeoutError('R5R script did not acknowledge the command')

    def console(self, command):
        if not command.strip() or '\n' in command or '\r' in command:
            raise ValueError('Expected one console command')
        with self.connect() as console:
            console.execute(command)
        return {'sent': True}

    def status(self):
        return {ctx: self.script(ctx, 'R5H_Status($TICKET)') for ctx in ('server', 'client')}

    def wait_signon(self, offset, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not owned_alive(self.session):
                self.export_logs()
                raise RuntimeError('R5R exited during loading; see ' + str(self.run / 'game.log'))
            with (self.run / 'process.log').open('rb') as log:
                log.seek(offset)
                content = log.read().decode('utf-8', 'replace')
            if 'signon state: SIGNONSTATE_FULL' in content:
                time.sleep(2)
                return
            time.sleep(1)
        self.export_logs()
        raise TimeoutError('R5R did not finish native signon; see ' + str(self.run / 'game.log'))

    def wait_map(self, name, timeout=120, previous=None):
        map_name(name)
        deadline = time.monotonic() + timeout
        last = ''
        while time.monotonic() < deadline:
            try:
                state = self.status()
                if all(v['map'] == name and v['ready'] and (not previous or v.get('instance') != previous[ctx].get('instance')) for ctx, v in state.items()):
                    self.session['map'] = name
                    write_json(SESSION, self.session)
                    return state
            except (OSError, ConnectionError, ValueError, TimeoutError) as exc:
                last = type(exc).__name__
            error_logs = sorted(self.profile.glob('platform/logs/*/error.log'), key=lambda p:p.stat().st_mtime, reverse=True)
            if error_logs and error_logs[0].stat().st_mtime >= self.session['launched']:
                content = error_logs[0].read_text(encoding='utf-8', errors='replace')
                failures = [line for line in content.splitlines() if 'Connection to server overflowed' in line or 'COMPILE ERROR' in line or 'SCRIPT ERROR' in line]
                if failures:
                    self.export_logs()
                    raise RuntimeError('Native R5R load failure: ' + failures[-1][:400])
            time.sleep(2)
        self.export_logs()
        raise TimeoutError('R5R map did not become ready: ' + last)

    def load(self, name, timeout=180):
        map_name(name)
        previous = self.status()
        self.script('client', 'R5H_ClearCamera($TICKET)')
        offset = (self.run / 'process.log').stat().st_size
        self.console('map ' + name)
        self.wait_signon(offset, timeout)
        self.session['camera'] = None
        self.session['generation'] = uuid.uuid4().hex
        return self.wait_map(name, timeout, previous)

    def camera(self, origin, angles, fov=90, settle=3):
        origin, angles = vector(origin), vector(angles)
        if not math.isfinite(fov) or not 30 <= fov <= 120:
            raise ValueError('FOV must be between 30 and 120')
        pos = lambda v: '<' + ','.join(format(n, '.8g') for n in v) + '>'
        self.clear_ui()
        self.script('server', 'foreach(entity p in GetPlayerArray()) p.SetPhysics(MOVETYPE_NOCLIP); R5H_Status($TICKET)')
        # Move the player too: camera-only movement leaves streaming/PVS at the spawn.
        self.script('server', 'R5H_Player($TICKET,' + pos([origin[0], origin[1], origin[2] - 64]) + ',' + pos(angles) + ')')
        result = self.script('client', 'R5H_Camera($TICKET,' + pos(origin) + ',' + pos(angles) + ',' + str(float(fov)) + ')')
        if 'origin' in result and any(abs(a-b) > .05 for a,b in zip(result['origin'],origin)):
            raise RuntimeError('Native camera position differs from the requested route')
        if 'angles' in result and any(abs((a-b+180)%360-180) > .05 for a,b in zip(result['angles'],angles)):
            raise RuntimeError('Native camera angles differ from the requested route')
        self.session['camera'] = {'origin': origin, 'angles': angles, 'fov': fov}
        write_json(SESSION, self.session)
        time.sleep(settle)
        return result

    def clear_ui(self):
        return self.script('ui', 'if(!IsEULAAccepted()) throw "First-run agreement requires user action"; CloseAllMenus(); print("R5H:" + $TICKET + ":{\\\"ready\\\":1}")')

    def capture(self, label, timeout=25):
        if not NAME.fullmatch(label):
            raise ValueError('Invalid screenshot label')
        folders = [self.profile / 'screenshots', self.profile / 'platform/screenshots']
        def files():
            return {p: (p.stat().st_mtime_ns, p.stat().st_size) for folder in folders if folder.exists()
                    for p in folder.rglob('*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tga', '.bmp') and p.is_file()}
        state = self.status()
        if any(v['map'] != self.session['map'] or not v['ready'] for v in state.values()):
            raise RuntimeError('Screenshot map is not ready or differs from the session')
        self.clear_ui()
        time.sleep(.5)
        before = files()
        self.console('screenshot')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            fresh = [p for p, stamp in files().items() if before.get(p) != stamp and stamp[1]]
            if fresh:
                native = max(fresh, key=lambda p: p.stat().st_mtime_ns)
                size = native.stat().st_size
                time.sleep(.5)
                if native.stat().st_size != size:
                    continue
                sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
                from PIL import Image
                dest = self.run / 'screenshots' / (label + '-' + uuid.uuid4().hex[:8] + '.png')
                dest.parent.mkdir(exist_ok=True)
                with Image.open(native) as image:
                    image.load()
                    width, height = image.size
                    if width < 640 or height < 360:
                        raise RuntimeError('Unexpected native screenshot dimensions')
                    image.save(dest)
                record = {'path': str(dest), 'native_path': str(native), 'width': width, 'height': height,
                          'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(), 'captured': time.time(),
                          'map': self.session['map'], 'camera': self.session.get('camera'), 'state': state,
                          'generation': self.session['generation'], 'engine': 'r5r'}
                write_json(dest.with_suffix('.json'), record)
                return record
            time.sleep(.25)
        self.export_logs()
        raise TimeoutError('R5R did not write a native screenshot')

    def export_logs(self):
        result = []
        logs = sorted([*self.profile.glob('logs/**/*'), *self.profile.glob('platform/logs/**/*')], key=lambda p: p.stat().st_mtime)
        for original in logs:
            if not original.is_file() or original.suffix.lower() not in ('.log', '.txt'):
                continue
            if original.stat().st_mtime < self.session['launched']:
                continue
            content = original.read_text(encoding='utf-8', errors='replace')
            content = content.replace(self.session['password'], '[REDACTED]')
            content = re.sub(r'(?im)^.*(?:rcon_key|NetKey|encryption key|sv_rcon_password|Remote server access.*with key).*$', '[RCON credential redacted]', content)
            relative = original.relative_to(self.profile)
            dest = self.run / 'logs' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding='utf-8')
            result.append(str(dest))
        original = self.run / 'process.log'
        if original.exists():
            content = original.read_text(encoding='utf-8', errors='replace')
            content = content.replace(self.session['password'], '[REDACTED]')
            content = re.sub(r'(?im)^.*(?:rcon_key|NetKey|encryption key|sv_rcon_password|Remote server access.*with key).*$', '[credential redacted]', content)
            dest = self.run / 'game.log'
            dest.write_text(content, encoding='utf-8')
            result.append(str(dest))
        return {'files': result}


def route(controller, path):
    job = json.loads(Path(path).read_text())
    controller.load(job['source_map'])
    captures = []
    for shot in job['shots']:
        controller.camera(source_origin(shot['origin'], job['source_offset']), shot['angles'], shot.get('fov', 90), shot.get('settle', 3))
        captures.append(controller.capture(shot['name']))
    result = {'route': str(Path(path).resolve()), 'captures': captures, 'logs': controller.export_logs()}
    write_json(controller.run / 'route-result.json', result)
    return result


def cached_source_captures(saved, job):
    captures = saved['captures']
    if saved['route'] != job or len(captures) > len(job['shots']):
        raise ValueError('Saved source captures belong to a different route')
    for record, shot in zip(captures, job['shots']):
        expected = dict(origin=source_origin(shot['origin'], job['source_offset']),
                        angles=shot['angles'], fov=shot.get('fov',90))
        if record.get('map') != job['source_map'] or record.get('camera') != expected:
            raise ValueError('Saved source capture has a different map or camera')
        if hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Saved source screenshot changed')
    return list(captures)


def compare(path, target, simultaneous=False, resume=False):
    job = json.loads(Path(path).read_text())
    spec = importlib.util.spec_from_file_location('northstar_harness', ROOT / 'test-harness/harness.py')
    ns = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ns)
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    captures = cached_source_captures(json.loads((target/'source-captures.json').read_text()),job) if resume else []
    r5, tf = (Controller() if len(captures) < len(job['shots']) else None), None
    try:
        tf = ns.Controller()
        state = tf.request('/status')
    except (OSError, ValueError, RuntimeError):
        state = {'game_running':False}
    if state['game_running'] and not simultaneous and r5:
        tf.request('/stop-game', {})
    if r5:
        r5.load(job['source_map'])
        write_json(target/'source-captures.json', {'route':job,'captures':captures})
        for shot in job['shots'][len(captures):]:
            if not NAME.fullmatch(shot['name']):
                raise ValueError('Invalid route label')
            fov = shot.get('fov', 90)
            r5.camera(source_origin(shot['origin'], job['source_offset']), shot['angles'], fov, shot.get('settle', 3))
            a = r5.capture(shot['name'])
            captures.append(a)
            # A later native game failure must not discard completed views.
            write_json(target/'source-captures.json', {'route':job,'captures':captures})
    if r5 and not simultaneous:
        r5.export_logs()
        stop(r5.session)
        time.sleep(2)
    newly_started = False
    restarted = False
    try:
        if tf is None:
            tf = ns.Controller()
        tf_state = tf.request('/status')
    except (OSError, ValueError, RuntimeError):
        args = ns.parser().parse_args(['start', '--map', job['target_map'], '--mode', job.get('mode','tdm'),
            '--package', str(ROOT/'northstar/ArenaComposite'), '--extra-package', str(ROOT/'northstar/PhaseRunner')])
        ns.start(args)
        newly_started = True
        tf = ns.Controller()
        tf_state = tf.request('/status')
    if newly_started:
        pass  # start already waited for this map; a second reload is unnecessary.
    elif tf_state['game_running']:
        contexts = tf_state.get('contexts', {})
        ready = all(ctx in contexts and contexts[ctx].get('ready') and contexts[ctx].get('level') == job['target_map'] and time.time()-contexts[ctx]['received'] < 3 for ctx in ns.CONTEXTS)
        if not ready:
            tf.request('/stop-game', {})
            tf.request('/launch', {'map':job['target_map'], 'mode':job.get('mode', 'tdm')})
            tf.wait_map(job['target_map'], 180)
            restarted = True
    else:
        tf.request('/launch', {'map':job['target_map'], 'mode':job.get('mode', 'tdm')})
        tf.wait_map(job['target_map'], 180)
        restarted = True
    if newly_started or restarted:
        # Player entities exist before Titanfall's opening countdown/UI ends.
        time.sleep(20)
    pairs = []
    for shot, a in zip(job['shots'], captures):
        fov = shot.get('fov', 90)
        tf.camera(shot['origin'], shot['angles'], fov, shot.get('settle', 3))
        b = tf.capture(shot['name'])
        if (a['width'], a['height']) != (b['width'], b['height']):
            raise RuntimeError('Capture resolutions differ; set both games to the same resolution')
        for engine, record in [('r5r', a), ('northstar', b)]:
            dest = target / (shot['name'] + '-' + engine + '.png')
            shutil.copy2(record['path'], dest)
            record['gallery_path'] = dest.name
        pairs.append({'name': shot['name'], 'r5r': a, 'northstar': b, 'route_camera': shot})
    result = {'route': job, 'pairs': pairs, 'captured': time.time()}
    write_json(target / 'comparison.json', result)
    sections = []
    for pair in pairs:
        name = html.escape(pair['name'])
        a, b = pair['r5r']['gallery_path'], pair['northstar']['gallery_path']
        sections.append(f'<section><h2>{name}</h2><div class="pair"><figure><figcaption>R5R · Apex source</figcaption><img src="{a}"></figure><figure><figcaption>Northstar · Titanfall 2</figcaption><img src="{b}"></figure></div><details><summary>Overlay comparison</summary><div class="overlay"><img src="{a}"><img class="top" src="{b}"></div><input type="range" min="0" max="100" value="50" aria-label="Titanfall opacity" oninput="this.previousElementSibling.lastElementChild.style.opacity=this.value/100"></details></section>')
    (target / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Map build comparison</title><style>body{background:#101722;color:#eef2f8;font:16px system-ui;margin:24px}h1{font-size:24px}.pair{display:flex;gap:12px}figure{margin:0;width:50%}img{width:100%;display:block}figcaption{padding:8px}section{margin-bottom:32px}.overlay{position:relative;max-width:1280px}.top{position:absolute;inset:0;opacity:.5}input{width:min(100%,1280px)}summary{padding:12px;cursor:pointer}</style><h1>' + html.escape(job['title']) + '</h1><p>Identical world positions after the documented coordinate offset; matched camera angles, FOV and resolution. Native game screenshots.</p>' + ''.join(sections), encoding='utf-8')
    if r5:
        r5.export_logs()
    tf.export_logs()
    return {'gallery': str(target / 'index.html'), 'pairs': len(pairs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('stage', 'launch'):
        p = sub.add_parser(action)
        p.add_argument('--source', type=Path, default=SOURCE)
        p.add_argument('--profile', type=Path, default=PROFILE)
        if action == 'launch':
            p.add_argument('map')
            p.add_argument('--port', type=int, default=37042)
    sub.add_parser('status')
    sub.add_parser('stop')
    sub.add_parser('logs')
    sub.add_parser('camera-clear')
    p = sub.add_parser('load'); p.add_argument('map')
    p = sub.add_parser('camera'); p.add_argument('origin', type=float, nargs=3); p.add_argument('--angles', type=float, nargs=3, default=[0,0,0]); p.add_argument('--fov', type=float, default=90)
    p = sub.add_parser('capture'); p.add_argument('label')
    p = sub.add_parser('console'); p.add_argument('command')
    p = sub.add_parser('route'); p.add_argument('path', type=Path)
    p = sub.add_parser('compare'); p.add_argument('path', type=Path); p.add_argument('--output', type=Path, default=HOME/'output/comparison'); p.add_argument('--simultaneous', action='store_true'); p.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.action == 'stage': result = stage(args.source, args.profile)
    elif args.action == 'launch': result = launch(args.map, args.source, args.profile, args.port)
    elif args.action == 'stop': result = stop()
    elif args.action == 'compare': result = compare(args.path, args.output, args.simultaneous, args.resume)
    else:
        c = Controller()
        if args.action == 'status': result = c.status()
        elif args.action == 'load': result = c.load(args.map)
        elif args.action == 'camera': result = c.camera(args.origin, args.angles, args.fov)
        elif args.action == 'capture': result = c.capture(args.label)
        elif args.action == 'console': result = c.console(args.command)
        elif args.action == 'logs': result = c.export_logs()
        elif args.action == 'camera-clear':
            result = c.script('client', 'R5H_ClearCamera($TICKET)')
            c.script('server', 'foreach(entity p in GetPlayerArray()) p.SetPhysics(MOVETYPE_WALK); R5H_Status($TICKET)')
            c.session['camera'] = None
            write_json(SESSION, c.session)
        elif args.action == 'route': result = route(c, args.path)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
