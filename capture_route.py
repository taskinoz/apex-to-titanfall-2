"""Capture a test-harness route after an explicit respawn (maps whose intro leaves no live player).

  python capture_route.py test-harness/routes/overflow-survey-2.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent/'test-harness'))
from harness import Controller


def run(path):
    route = json.loads(Path(path).read_text()); c = Controller()
    c.load(route['map'], route.get('mode', 'ps'), 180); c.command('client', 'camera_clear'); c.command('server', 'respawn', team=2)
    shots = []
    for shot in route['shots']:
        c.camera(shot['origin'], shot['angles'], shot.get('fov', 75), shot.get('settle', 2)); shots.append(c.capture(shot['name']))
    c.command('client', 'camera_clear')
    print(json.dumps(dict(run=str(c.run), captures=len(shots), logs=c.export_logs()['native_crashes'])), flush=True)


if __name__ == '__main__':
    run(sys.argv[1])
