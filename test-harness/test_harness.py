import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
from harness import Application, Broker, Handler, validate_job


class HarnessTests(unittest.TestCase):
    def test_engine_dialog_is_reported_before_readiness_timeout(self):
        from harness import Controller
        from unittest.mock import patch
        c = Controller.__new__(Controller)
        c.session = {'token':'private-test-value'}
        c.request = lambda _: dict(game_running=True,game_pid=17,contexts={})
        c.export_logs = lambda: None
        with patch('harness.owned_engine_error', return_value='More than 20 UI atlases private-test-value') as diagnostic:
            with self.assertRaisesRegex(RuntimeError, '20 UI atlases \\[session-token\\]'):
                c.wait_map('mp_test', 1)
            diagnostic.assert_called_once_with(17)

    def test_camera_moves_streaming_player_before_native_view_and_checks_result(self):
        from harness import Controller
        c = Controller.__new__(Controller)
        calls = []
        def command(context, op, **values):
            calls.append((context, op, values))
            return {'data': {'origin': [10, 20, 100], 'angles': [0, 90, 0]}}
        c.command = command
        c.camera([10, 20, 100], [0, 90, 0], 90, 0)
        self.assertEqual([(x,y) for x,y,_ in calls], [('ui','clear_ui'), ('server','camera_follow'), ('client','camera')])
        self.assertEqual(calls[1][2]['pz'], 36)
        self.assertEqual(calls[2][2]['pz'], 100)
        with self.assertRaises(RuntimeError):
            c.camera([10, 20, 101], [0, 90, 0], 90, 0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.broker = Broker(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_delivery_is_not_replayed_and_requires_matching_context(self):
        ident = self.broker.submit('ui', dict(op='status'))
        self.assertEqual(self.broker.poll('client', dict(ready=True)), {})
        self.assertEqual(self.broker.poll('ui', dict(ready=True))['id'], ident)
        self.assertEqual(self.broker.poll('ui', dict(ready=True)), {})
        with self.assertRaises(ValueError):
            self.broker.ack(dict(id=ident, context='server', ok=True))
        self.broker.ack(dict(id=ident, context='ui', ok=True))
        with self.assertRaises(ValueError):
            self.broker.ack(dict(id=ident, context='ui', ok=True))
        self.assertEqual(self.broker.jobs[ident]['state'], 'complete')

    def test_timeout_cancellation_prevents_late_execution(self):
        ident = self.broker.submit('ui', dict(op='console', command='screenshot'))
        self.broker.cancel(ident)
        self.assertEqual(self.broker.poll('ui', dict(ready=True)), {})
        self.assertEqual(self.broker.jobs[ident]['state'], 'cancelled')

    def test_map_names_coordinates_and_contexts_are_validated(self):
        for name in ('../mp_coliseum', 'mp_coliseum;quit', 'mp_coliseum\nquit'):
            with self.assertRaises(ValueError):
                validate_job('ui', dict(op='load', map=name, mode='tdm'))
        with self.assertRaises(ValueError):
            validate_job('client', dict(op='console', command='quit'))
        base = dict(op='camera', px=0, py=1, pz=2, pitch=0, yaw=90, roll=0, fov=75)
        for bad in (float('nan'), float('inf'), True, '1', 999999):
            with self.assertRaises(ValueError):
                validate_job('client', dict(base, px=bad))
        self.assertEqual(validate_job('client', base)['fov'], 75.)

    def test_install_refuses_an_unowned_profile(self):
        game = self.root/'game'
        profile = game/'R2MapHarness'
        profile.mkdir(parents=True)
        sentinel = profile/'keep.txt'
        sentinel.write_text('unchanged')
        app = Application(game, 'R2MapHarness', 39131, self.root/'run', 'token', self.root/'package')
        with self.assertRaises(ValueError):
            app.install()
        self.assertEqual(sentinel.read_text(), 'unchanged')
        for name in ('R2Northstar', 'R2CollisionLab', '../other'):
            with self.assertRaises(ValueError):
                Application(game, name, 39131, self.root/'run', 'token', self.root/'package')

    def test_titan_mode_switch_restarts_only_owned_controller_session(self):
        from harness import Controller
        c = Controller.__new__(Controller)
        c.run = self.root
        (c.run/'game.log').write_text('native test log')
        calls = []
        def request(path, body=None):
            calls.append((path, body))
            if path == '/status':
                return dict(game_running=True, contexts=dict(server=dict(mode='lts')))
            return {}
        c.request = request
        c.export_logs = lambda: dict(path=str(c.run/'game.log'))
        c.wait_map = lambda name, timeout: dict(level=name)
        self.assertEqual(c.load('mp_phase_runner', 'mfd')['level'], 'mp_phase_runner')
        self.assertEqual([p for p,_ in calls], ['/status', '/stop-game', '/launch'])
        self.assertEqual(calls[-1][1], dict(map='mp_phase_runner', mode='mfd'))
        self.assertEqual(len(list(c.run.glob('game-before-titan-switch-*.log'))), 1)

    def test_package_switch_removes_stale_map_files(self):
        from harness import clear_managed_package
        profile=self.root/'owned-profile'
        dest=profile/'mods/PhaseRunner.Preview'
        (dest/'mod/maps').mkdir(parents=True)
        (dest/'mod/maps/mp_old.bsp').write_bytes(b'old map')
        clear_managed_package(profile,'PhaseRunner.Preview')
        self.assertFalse(dest.exists())
        with self.assertRaises(ValueError):
            clear_managed_package(profile,'Northstar.Client')

    def test_http_auth_and_game_roundtrip(self):
        app = Application(self.root, 'R2MapHarness', 39131, self.root/'run', 'test-token', self.root/'package')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def request(path, body=None, token='test-token'):
            req = Request(origin+path, data=None if body is None else json.dumps(body).encode(), headers={'Authorization':'Bearer '+token})
            with urlopen(req, timeout=3) as response:
                return json.load(response)
        try:
            with self.assertRaises(HTTPError) as error:
                request('/status', token='wrong')
            self.assertEqual(error.exception.code, 401)
            ident = request('/command', dict(context='server', op='status'))['id']
            command = request('/poll/server', dict(level='mp_coliseum', ready=True))
            self.assertEqual(command['id'], ident)
            request('/ack', dict(id=ident, context='server', ok=True, data=dict(players=1)))
            self.assertEqual(request('/result/'+ident)['result']['data']['players'], 1)
            self.assertEqual(request('/status')['contexts']['server']['level'], 'mp_coliseum')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
