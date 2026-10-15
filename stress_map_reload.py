"""Repeat native load / respawn / postmatch-lobby / stock-map cycles and report script errors.

Used to tell map-caused VM corruption apart from harness flakiness:
  python stress_map_reload.py mp_party_crasher 8
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent/'test-harness'))
from harness import Controller


def run(target, cycles):
    c = Controller(); first = None
    for i in range(cycles):
        c.load(target, 'ps', 180); c.command('client', 'camera_clear')
        for team in (2, 3):
            c.command('server', 'respawn', team=team)
        c.command('ui', 'console', command='script SetGameState( eGameState.Postmatch )')
        deadline = time.monotonic()+90
        while time.monotonic() < deadline and c.request('/status')['contexts'].get('client', {}).get('level') != 'mp_lobby':
            time.sleep(1)
        try:
            c.load('mp_coliseum', 'ps', 180)
        except TimeoutError:
            print('cycle', i+1, 'stock map ready timeout', flush=True)
        logs = c.export_logs()
        if (logs['script_errors'] or logs['native_crashes']) and first is None:
            first = i+1
        print('cycle', i+1, 'script errors', len(logs['script_errors']), 'crashes', len(logs['native_crashes']), flush=True)
    print('first failure at cycle', first, flush=True)


if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]))
