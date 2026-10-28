"""Local Northstar map controller. Uses the game's HTTP API and screenshot command."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(__file__).resolve().parent
SESSION = HOME / 'output/session.json'
CONTEXTS = ('ui', 'client', 'server')
MAP = re.compile(r'mp_[a-z0-9_]+\Z')
NAME = re.compile(r'[a-zA-Z0-9_-]{1,80}\Z')
MODES = ('tdm', 'ffa', 'ps', 'aitdm', 'ctf', 'cp', 'fastball', 'lts', 'ttdm', 'mfd')


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    tmp.replace(path)


def validate_job(context, payload):
    if context not in CONTEXTS:
        raise ValueError('Unknown script context')
    allowed = {'ui': {'load', 'console', 'screenshot', 'clear_ui', 'status'},
               'client': {'camera', 'camera_clear', 'status'},
               'server': {'player', 'camera_follow', 'camera_restore', 'trace', 'status', 'mode_check', 'respawn', 'spawn_probe'}}
    job = dict(payload)
    if job.get('op') not in allowed[context]:
        raise ValueError('Unsupported action for ' + context)
    if job['op'] == 'load':
        if not MAP.fullmatch(job.get('map', '')) or job.get('mode') not in MODES:
            raise ValueError('Use a raw mp_ map name and a supported mode')
    if job['op'] == 'respawn' and (type(job.get('team')) is not int or job['team'] not in (2, 3)):
        raise ValueError('Respawn team must be IMC (2) or Militia (3)')
    if job['op'] == 'spawn_probe':
        probes = job.get('points')
        if not isinstance(probes, list) or not 1 <= len(probes) <= 400:
            raise ValueError('Provide 1 to 400 spawn candidates')
        for point in probes:
            if not isinstance(point, list) or len(point) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 100000 for v in point):
                raise ValueError('Invalid spawn candidate')
        job['points'] = [[float(v) for v in point] for point in probes]
    if job['op'] == 'console':
        c = job.get('command', '')
        if not isinstance(c, str) or not c.strip() or len(c) > 2048 or '\x00' in c:
            raise ValueError('Invalid game console command')
    if job['op'] in ('camera', 'camera_follow', 'player', 'trace'):
        fields = ['px', 'py', 'pz'] + (['ex', 'ey', 'ez'] if job['op'] == 'trace' else ['pitch', 'yaw', 'roll'])
        if job['op'] == 'camera':
            fields += ['fov']
        for field in fields:
            v = job.get(field)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 100000:
                raise ValueError('Invalid coordinate: ' + field)
            job[field] = float(v)
        if job['op'] == 'camera' and not 10 <= job['fov'] <= 150:
            raise ValueError('Camera FOV must be between 10 and 150')
        if job['op'] == 'player' and not isinstance(job.get('freeze'), bool):
            raise ValueError('freeze must be boolean')
    return job


class Broker:
    """At-most-once delivery; a lost acknowledgement fails instead of replaying."""
    def __init__(self, run):
        self.run = Path(run)
        self.lock = threading.RLock()
        self.queues = {c: deque() for c in CONTEXTS}
        self.jobs = {}
        self.contexts = {}

    def submit(self, context, payload):
        payload = validate_job(context, payload)
        with self.lock:
            ident = uuid.uuid4().hex
            self.jobs[ident] = dict(id=ident, context=context, payload=payload, state='queued', submitted=time.time())
            self.queues[context].append(ident)
            self.event('submitted', self.jobs[ident])
            return ident

    def event(self, kind, data):
        self.run.mkdir(parents=True, exist_ok=True)
        with (self.run / 'events.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(dict(time=time.time(), event=kind, data=data)) + '\n')

    def poll(self, context, status):
        if context not in CONTEXTS or not isinstance(status, dict):
            raise ValueError('Invalid context status')
        with self.lock:
            self.contexts[context] = dict(status, received=time.time())
            if not self.queues[context]:
                return {}
            ident = self.queues[context].popleft()
            job = self.jobs[ident]
            job.update(state='delivered', delivered=time.time())
            return dict(job['payload'], id=ident)

    def ack(self, result):
        with self.lock:
            job = self.jobs.get(result.get('id'))
            if not job or job['state'] != 'delivered' or job['context'] != result.get('context'):
                raise ValueError('Unknown or mismatched acknowledgement')
            job.update(state='complete', result=result, completed=time.time())
            self.event('completed', job)

    def cancel(self, ident):
        with self.lock:
            job = self.jobs[ident]
            if job['state'] == 'queued':
                self.queues[job['context']].remove(ident)
            if job['state'] != 'complete':
                job.update(state='cancelled', cancelled=time.time())
                self.event('cancelled', job)


def owned_engine_error(pid):
    """Read an Engine Error dialog only from the controller's game process."""
    if os.name != 'nt' or not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    import ctypes
    api = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    api.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    api.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    api.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
    api.EnumChildWindows.argtypes = [ctypes.c_void_p, callback_type, ctypes.c_void_p]
    messages = []
    def caption(handle):
        buffer = ctypes.create_unicode_buffer(4096)
        api.GetWindowTextW(handle, buffer, len(buffer))
        return buffer.value
    def child(handle, unused):
        text = caption(handle).strip()
        if text and text not in ('OK', 'Cancel'):
            messages.append(text)
        return 1
    child_callback = callback_type(child)
    def window(handle, unused):
        owner = ctypes.c_uint32()
        api.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and caption(handle).strip() == 'Engine Error':
            api.EnumChildWindows(handle, child_callback, None)
        return 1
    window_callback = callback_type(window)
    api.EnumWindows(window_callback, None)
    return '\n'.join(messages)[:2048] if messages else None


def copy_file(source, dest):
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == source.stat().st_size and dest.stat().st_mtime_ns == source.stat().st_mtime_ns:
        return
    if dest.exists():
        dest.unlink()  # Never modify an immutable hardlink in place.
    if source.suffix.lower() in ('.bsp', '.stbsp', '.rpak') and source.stat().st_size > 10*1024*1024:
        try:
            os.link(source, dest)
            return
        except OSError:
            pass
    shutil.copy2(source, dest)


def copy_tree(source, dest):
    source = Path(source)
    for f in source.rglob('*'):
        if f.is_file():
            copy_file(f, Path(dest) / f.relative_to(source))


def clear_managed_package(profile, name):
    """Remove stale files only from this harness's three reserved folders."""
    profile=Path(profile).resolve()
    if name not in ('MapTest.Harness','PhaseRunner.Preview','MapTest.Extra') and not re.fullmatch(r'MapTest\.Extra[2-8]', name):
        raise ValueError('Unmanaged package folder')
    dest=profile/'mods'/name
    if dest.resolve().parent != (profile/'mods').resolve():
        raise ValueError('Managed package path escaped its profile')
    if dest.exists():
        shutil.rmtree(dest)


class Application:
    def __init__(self, game, profile, port, run, token, package, extra_package=None, runtime=None, launcher=None):
        self.game = Path(game).resolve()
        self.runtime = Path(runtime).resolve() if runtime else self.game/'R2Northstar'
        self.launcher = Path(launcher).resolve() if launcher else self.game/'NorthstarLauncher.exe'
        if self.launcher.parent != self.game or self.launcher.suffix.lower() != '.exe':
            raise ValueError('The test launcher must be an executable in the game directory')
        if not NAME.fullmatch(profile) or profile in ('R2Northstar', 'R2CollisionLab'):
            raise ValueError('A dedicated harness profile name is required')
        self.profile = self.game / profile
        self.port, self.token, self.package = port, token, Path(package).resolve()
        extras = extra_package if isinstance(extra_package, list) else ([extra_package] if extra_package else [])
        if len(extras) > 8:
            raise ValueError('At most eight extra packages are supported')
        self.extra_packages = [Path(p).resolve() for p in extras]
        self.run = Path(run).resolve()
        self.broker = Broker(self.run)
        self.process = None
        self.launch_lock = threading.Lock()

    def install(self):
        marker = self.profile / '.map-test-harness.json'
        if self.profile.exists() and not marker.exists():
            raise ValueError('Existing profile is not owned by this harness')
        if not self.launcher.is_file():
            raise ValueError('NorthstarLauncher.exe is missing')
        source = self.runtime
        if not (source/'Northstar.dll').is_file():
            raise ValueError('Selected Northstar runtime is missing Northstar.dll')
        self.profile.mkdir(parents=True, exist_ok=True)
        write_json(marker, dict(owner='MapTest.Harness', game=str(self.game)))
        copy_file(source / 'Northstar.dll', self.profile / 'Northstar.dll')
        enabled = {'Version': 1}
        for name in ('Northstar.Client', 'Northstar.Custom', 'Northstar.CustomServers'):
            src = source / 'mods' / name
            copy_tree(src, self.profile / 'mods' / name)
            mod = json.loads((src / 'mod.json').read_text(encoding='utf-8-sig'))
            enabled[mod['Name']] = {mod['Version']: True}
        packages = [(ROOT / 'northstar/MapTest.Harness', 'MapTest.Harness'), (self.package, 'PhaseRunner.Preview')]
        for i, source_package in enumerate(self.extra_packages, 1):
            packages.append((source_package, 'MapTest.Extra' + (str(i) if i > 1 else '')))
        for name in ('MapTest.Harness','PhaseRunner.Preview','MapTest.Extra', *('MapTest.Extra'+str(i) for i in range(2,9))):
            clear_managed_package(self.profile,name)
        for src, name in packages:
            copy_tree(src, self.profile / 'mods' / name)
            mod = json.loads((src / 'mod.json').read_text(encoding='utf-8-sig'))
            enabled[mod['Name']] = {mod['Version']: True}
        write_json(self.profile / 'enabledmods.json', enabled)

    def launch(self, mapname, mode, width=1280, height=720):
        validate_job('ui', dict(op='load', map=mapname, mode=mode))
        if not 640 <= width <= 3840 or not 360 <= height <= 2160:
            raise ValueError('Invalid render resolution')
        with self.launch_lock:
            if self.process is not None and self.process.poll() is None:
                raise ValueError('This harness game session is already running')
            self.install()
            with self.broker.lock:
                self.broker.contexts.clear()
                for job in list(self.broker.jobs.values()):
                    if job['state'] in ('queued', 'delivered'):
                        self.broker.cancel(job['id'])
            args = [str(self.launcher), '-profile='+self.profile.name,
                    '-multiple', '-novid', '-nosound', '-windowed', '-allowlocalhttp',
                    '-w', str(width), '-h', str(height), '+ip', '127.0.0.1', '+hostport', '37041',
                    '+sv_lan', '1', '+ns_report_server_to_masterserver', '0',
                    '+ns_report_sp_server_to_masterserver', '0', '+map_harness_enabled', '1',
                    '+map_harness_port', str(self.port), '+map_harness_token', self.token,
                    '+map_harness_generation', uuid.uuid4().hex,
                    '+phase_runner_local_test', '1', '+sv_cheats', '1', '+setplaylist', 'private_match',
                    '+mp_gamemode', mode, '+map', mapname]
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            self.process = subprocess.Popen(args, cwd=self.game, startupinfo=startup)
            self.broker.event('launch', dict(pid=self.process.pid, map=mapname, mode=mode, profile=self.profile.name))
            return dict(pid=self.process.pid, profile=self.profile.name)

    def status(self):
        with self.broker.lock:
            alive = self.process is not None and self.process.poll() is None
            return dict(game_running=alive, game_pid=self.process.pid if alive else None,
                        profile=str(self.profile), run=str(self.run), contexts=dict(self.broker.contexts))

    def stop_game(self):
        # Popen owns a handle to exactly the process this controller launched.
        with self.launch_lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=15)
            self.broker.event('stop', {})
        return dict(stopped=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+self.server.app.token)

    def do_GET(self):
        if not self.authorized():
            return self.reply(401, dict(error='Authorization required'))
        app = self.server.app
        if self.path == '/status':
            return self.reply(200, app.status())
        if self.path.startswith('/result/'):
            with app.broker.lock:
                job = app.broker.jobs.get(self.path.rsplit('/', 1)[-1])
                return self.reply(200 if job else 404, job or dict(error='Unknown job'))
        self.reply(404, dict(error='Unknown route'))

    def do_POST(self):
        if not self.authorized():
            return self.reply(401, dict(error='Authorization required'))
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 65536:
                return self.reply(413, dict(error='Request too large'))
            payload = json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(payload, dict):
                raise ValueError('Expected JSON object')
            app = self.server.app
            if self.path.startswith('/poll/'):
                result = app.broker.poll(self.path.rsplit('/', 1)[-1], payload)
            elif self.path == '/ack':
                app.broker.ack(payload)
                result = dict(ok=True)
            elif self.path == '/command':
                result = dict(id=app.broker.submit(payload.pop('context'), payload))
            elif self.path.startswith('/cancel/'):
                app.broker.cancel(self.path.rsplit('/', 1)[-1])
                result = dict(cancelled=True)
            elif self.path == '/launch':
                result = app.launch(payload['map'], payload.get('mode', 'tdm'), payload.get('width', 1280), payload.get('height', 720))
            elif self.path == '/stop-game':
                result = app.stop_game()
            elif self.path == '/shutdown':
                app.stop_game()
                result = dict(stopped=True)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                return self.reply(404, dict(error='Unknown route'))
            self.reply(200, result)
        except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as e:
            self.reply(400, dict(error=str(e)))


class Controller:
    def __init__(self, session=SESSION):
        self.session = json.loads(Path(session).read_text(encoding='utf-8'))
        self.run = Path(self.session['run'])

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        r = Request(self.session['url']+path, data=data, headers={
            'Authorization': 'Bearer '+self.session['token'], 'Content-Type': 'application/json'})
        try:
            with urlopen(r, timeout=180 if path == '/launch' else 30) as response:
                return json.load(response)
        except HTTPError as e:
            raise RuntimeError(json.loads(e.read()).get('error', str(e))) from e

    def command(self, context, op, timeout=20, **values):
        ident = self.request('/command', dict(context=context, op=op, **values))['id']
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            job = self.request('/result/'+ident)
            if job['state'] == 'complete':
                result = job['result']
                if not result['ok']:
                    raise RuntimeError(result.get('error', 'Game command failed'))
                return result
            time.sleep(.2)
        self.request('/cancel/'+ident, {})
        raise TimeoutError(f'{context}/{op} timed out; inspect {self.run}')

    def wait_map(self, name, timeout=120, after=0, generation=None):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            s = self.request('/status')
            if not s['game_running']:
                raise RuntimeError('The isolated game process exited')
            engine_error = owned_engine_error(s.get('game_pid'))
            if engine_error:
                self.export_logs()
                raise RuntimeError('Native Engine Error: ' + engine_error.replace(self.session['token'], '[session-token]'))
            contexts = s['contexts']
            now = time.time()
            if all(c in contexts and contexts[c].get('level') == name and contexts[c].get('ready')
                   and not contexts[c].get('loading') and contexts[c]['received'] > after
                   and (generation is None or contexts[c].get('generation') == generation)
                   and now-contexts[c]['received'] < 3 for c in CONTEXTS):
                return s
            time.sleep(.5)
        raise TimeoutError(f'Map {name} did not become ready; inspect {self.run}')

    def load(self, name, mode='tdm', timeout=120):
        validate_job('ui', dict(op='load', map=name, mode=mode))
        state = self.request('/status')
        previous = state.get('contexts', {}).get('server', {})
        if state.get('game_running') and previous.get('mode') in ('lts', 'ttdm'):
            # An automated close of the stock Titan-selection menu can assert
            # while deregistering BUTTON_BACK. Start a fresh owned process for
            # switches out of Titan-only modes instead of closing that menu.
            exported = self.export_logs()
            if exported:
                shutil.copy2(self.run/'game.log', self.run/('game-before-titan-switch-'+time.strftime('%Y%m%d-%H%M%S')+'.log'))
            self.request('/stop-game', {})
            self.request('/launch', dict(map=name, mode=mode))
            return self.wait_map(name, timeout)
        client = state.get('contexts', {}).get('client', {})
        if client.get('ready') and client.get('camera') and time.time()-client.get('received', 0) < 3:
            self.command('client', 'camera_clear')
        stamp = time.time()
        result = self.command('ui', 'load', map=name, mode=mode)
        # Do not confuse old same-map heartbeats with a completed reload.
        time.sleep(3)
        return self.wait_map(name, timeout, after=stamp, generation=result['generation'])

    def camera(self, origin, angles, fov=75, settle=2):
        values = dict(zip(('px', 'py', 'pz', 'pitch', 'yaw', 'roll'), [*origin, *angles]))
        self.command('ui', 'clear_ui')
        # Keep streaming/PVS and the protected player at the view, in both engines.
        self.command('server', 'camera_follow', **dict(values, pz=origin[2]-64))
        result = self.command('client', 'camera', **values, fov=fov)
        state = result.get('data', {})
        if len(state.get('origin', [])) != 3 or any(abs(a-b) > .05 for a,b in zip(state['origin'], origin)):
            raise RuntimeError('Native camera position differs from the requested route')
        if len(state.get('angles', [])) != 3 or any(abs((a-b+180)%360-180) > .05 for a,b in zip(state['angles'], angles)):
            raise RuntimeError('Native camera angles differ from the requested route')
        time.sleep(settle)
        return result

    def capture(self, label, timeout=20):
        if not NAME.fullmatch(label):
            raise ValueError('Screenshot label must be a simple name')
        game = Path(self.session['game'])
        profile = game / self.session['profile']
        documents = Path(os.environ.get('USERPROFILE', '~'))/'Documents/Respawn/Titanfall2'
        folders = [game/'screenshots', game/'r2/screenshots', profile/'screenshots', documents/'screenshots', documents/'local/screenshots']
        def files():
            return {p: (p.stat().st_mtime_ns, p.stat().st_size) for f in folders if f.exists()
                    for p in f.rglob('*') if p.is_file() and p.suffix.lower() in ('.tga', '.jpg', '.jpeg', '.png', '.bmp')}
        before = files()
        state = self.request('/status')
        self.command('ui', 'screenshot')
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            current = files()
            fresh = sorted((p for p, v in current.items() if before.get(p) != v and v[1] > 0), key=lambda p:current[p][0], reverse=True)
            if fresh:
                p = fresh[0]
                size = p.stat().st_size
                time.sleep(.5)
                if p.stat().st_size != size:
                    continue
                shots = self.run/'screenshots'
                shots.mkdir(parents=True, exist_ok=True)
                dest = shots/(label+'-'+uuid.uuid4().hex[:8]+p.suffix.lower())
                shutil.copy2(p, dest)
                # Pillow only converts the game's lossless TGA container to PNG.
                sys.path.insert(0, str(ROOT/'tools/lighting-python'))
                from PIL import Image
                with Image.open(dest) as im:
                    im.load()
                    width, height = im.size
                    if width < 640 or height < 360:
                        raise RuntimeError('Unexpected screenshot dimensions')
                    png = dest.with_suffix('.png')
                    if dest != png:
                        im.save(png)
                record = dict(path=str(png), native_path=str(dest), width=width, height=height,
                              captured=time.time(), sha256=hashlib.sha256(png.read_bytes()).hexdigest(), state=state)
                write_json(png.with_suffix('.json'), record)
                return record
            time.sleep(.25)
        raise TimeoutError('The game did not write a screenshot. See session logs; no desktop-capture fallback is used.')

    def export_logs(self):
        profile = Path(self.session['game'])/self.session['profile']
        candidates = sorted((profile/'logs').glob('nslog*.txt'), key=lambda p:p.stat().st_mtime)
        if not candidates:
            return None
        text = candidates[-1].read_text(encoding='utf-8-sig', errors='replace')
        dest = self.run/'game.log'
        dest.write_text(text.replace(self.session['token'], '[session-token]'), encoding='utf-8')
        errors = [s for s in text.splitlines() if 'SCRIPT ERROR' in s or 'COMPILE ERROR' in s or 'ERROR: Script' in s]
        crashes = [s for s in text.splitlines() if 'Northstar has crashed!' in s]
        return dict(path=str(dest), script_errors=errors, native_crashes=crashes)


def serve(args):
    run = HOME/'output'/time.strftime('%Y%m%d-%H%M%S')
    run.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(24)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.app = Application(args.game, args.profile, args.port, run, token, args.package, args.extra_package,args.runtime,args.launcher)
    session = dict(url=f'http://127.0.0.1:{args.port}', token=token, run=str(run), game=str(server.app.game), profile=args.profile, controller_pid=os.getpid(),runtime=str(server.app.runtime),launcher=str(server.app.launcher))
    write_json(SESSION, session)
    write_json(run/'session.json', session)
    try:
        server.serve_forever()
    finally:
        server.app.stop_game()
        server.server_close()


def start(args):
    try:
        Controller().request('/status')
    except (OSError, ValueError, RuntimeError):
        (HOME/'output').mkdir(parents=True, exist_ok=True)
        with (HOME/'output/controller.log').open('ab') as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve', '--game', args.game,
                              '--profile', args.profile, '--port', str(args.port), '--package', args.package,
                              *(['--runtime',args.runtime] if args.runtime else []),
                              *(['--launcher',args.launcher] if args.launcher else []),
                              *[value for extra in (args.extra_package or []) for value in ('--extra-package', extra)]],
                             stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            try:
                c = Controller()
                c.request('/status')
                break
            except (OSError, ValueError, RuntimeError):
                time.sleep(.25)
        else:
            raise RuntimeError('Controller failed to start; inspect test-harness/output/controller.log')
    c = Controller()
    if c.session['game'] != str(Path(args.game).resolve()) or c.session['profile'] != args.profile:
        raise ValueError('Another harness configuration is running; stop it first')
    expected_runtime=str(Path(args.runtime).resolve() if args.runtime else Path(args.game).resolve()/'R2Northstar')
    expected_launcher=str(Path(args.launcher).resolve() if args.launcher else Path(args.game).resolve()/'NorthstarLauncher.exe')
    previous_runtime=c.session.get('runtime',str(Path(c.session['game'])/'R2Northstar'))
    previous_launcher=c.session.get('launcher',str(Path(c.session['game'])/'NorthstarLauncher.exe'))
    if previous_runtime!=expected_runtime or previous_launcher!=expected_launcher:
        raise ValueError('Another harness runtime is running; stop it before changing versions')
    c.request('/launch', dict(map=args.map, mode=args.mode, width=args.width, height=args.height))
    return c.wait_map(args.map, args.timeout)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    for action in ('serve', 'start'):
        s = sub.add_parser(action)
        s.add_argument('--game', default='D:/Games/Titanfall2')
        s.add_argument('--profile', default='R2MapHarness')
        s.add_argument('--runtime',help='Read-only Northstar runtime root containing Northstar.dll and core mods')
        s.add_argument('--launcher',help='Owned alternate launcher executable in the game directory')
        s.add_argument('--port', type=int, default=39131)
        s.add_argument('--package', default=str(ROOT/'northstar/PhaseRunner' if (ROOT/'northstar/PhaseRunner/mod.json').exists() else ROOT/'northstar/PhaseRunner.Preview'))
        s.add_argument('--extra-package', action='append', help='Enable another map package; repeat to test a combined installation')
        if action == 'start':
            s.add_argument('--map', default='mp_phase_runner')
            s.add_argument('--mode', choices=MODES, default='tdm')
            s.add_argument('--width', type=int, default=1280)
            s.add_argument('--height', type=int, default=720)
            s.add_argument('--timeout', type=float, default=120)
    sub.add_parser('status')
    for action in ('load', 'launch'):
        s = sub.add_parser(action)
        s.add_argument('map')
        s.add_argument('--mode', choices=MODES, default='tdm')
        s.add_argument('--timeout', type=float, default=120)
    s = sub.add_parser('camera')
    s.add_argument('origin', type=float, nargs=3)
    s.add_argument('--angles', type=float, nargs=3, default=[0, 0, 0])
    s.add_argument('--fov', type=float, default=75)
    s.add_argument('--settle', type=float, default=2)
    s = sub.add_parser('player')
    s.add_argument('origin', type=float, nargs=3)
    s.add_argument('--angles', type=float, nargs=3, default=[0, 0, 0])
    s.add_argument('--unfreeze', action='store_true')
    s = sub.add_parser('trace')
    s.add_argument('start', type=float, nargs=3)
    s.add_argument('--end', type=float, nargs=3, required=True)
    s = sub.add_parser('capture')
    s.add_argument('label')
    s = sub.add_parser('console')
    s.add_argument('command')
    s = sub.add_parser('route')
    s.add_argument('path', type=Path)
    sub.add_parser('camera-clear')
    sub.add_parser('mode-check')
    s = sub.add_parser('respawn')
    s.add_argument('--team', type=int, choices=(2, 3), required=True)
    sub.add_parser('stop-game')
    sub.add_parser('stop')
    return p


def main():
    args = parser().parse_args()
    if args.action == 'serve':
        return serve(args)
    if args.action == 'start':
        result = start(args)
    else:
        c = Controller()
        if args.action == 'status':
            result = c.request('/status')
        elif args.action == 'load':
            result = c.load(args.map, args.mode, args.timeout)
        elif args.action == 'launch':
            c.request('/launch', dict(map=args.map, mode=args.mode))
            result = c.wait_map(args.map, args.timeout)
        elif args.action == 'camera':
            result = c.camera(args.origin, args.angles, args.fov, args.settle)
        elif args.action == 'camera-clear':
            result = c.command('client', 'camera_clear')
            c.command('server', 'camera_restore')
        elif args.action == 'mode-check':
            result = c.command('server', 'mode_check')
        elif args.action == 'respawn':
            result = c.command('server', 'respawn', team=args.team)
        elif args.action == 'player':
            result = c.command('server', 'player', **dict(zip(('px', 'py', 'pz', 'pitch', 'yaw', 'roll'), [*args.origin, *args.angles])), freeze=not args.unfreeze)
        elif args.action == 'trace':
            result = c.command('server', 'trace', **dict(zip(('px', 'py', 'pz', 'ex', 'ey', 'ez'), [*args.start, *args.end])))
        elif args.action == 'capture':
            result = c.capture(args.label)
        elif args.action == 'console':
            result = c.command('ui', 'console', command=args.command)
        elif args.action == 'route':
            route = json.loads(args.path.read_text())
            c.load(route['map'], route.get('mode', 'tdm'))
            result = dict(map=route['map'], captures=[])
            for shot in route['shots']:
                c.camera(shot['origin'], shot['angles'], shot.get('fov', 75), shot.get('settle', 2))
                result['captures'].append(c.capture(shot['name']))
            result['logs'] = c.export_logs()
            if result['logs'] and result['logs']['script_errors']:
                raise RuntimeError('Route encountered script errors')
            write_json(c.run/'route-result.json', result)
        elif args.action == 'stop-game':
            result = c.request('/stop-game', {})
            result['logs'] = c.export_logs()
        elif args.action == 'stop':
            result = dict(logs=c.export_logs())
            result.update(c.request('/shutdown', {}))
        else:
            raise ValueError('Unknown action')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, TimeoutError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
