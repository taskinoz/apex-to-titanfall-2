"""Capture original candidate maps through the existing isolated R5R harness."""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'r5-harness'))
from harness import Controller

ROUTES = {
    'party-crasher': ('mp_rr_party_crasher', [
        ('overview', [3385.96265, -1591.92493, 2220.44629], [12, 97.7711029, 0]),
        ('mirage-voyage', [-1949.47925, -565.452087, 1366.40222], [0, -4.39630127, 0]),
        ('plaza', [416.486328, 2083.01709, 562.318604], [0, -83.0055008, 0]),
    ]),
    'overflow': ('mp_rr_aqueduct', [
        ('overview', [-324.00824, -6295.51123, 1393.36169], [15, 61.8894501, 0]),
        ('industrial-lanes', [4536.32324, -4842.01514, 627.977661], [0, 168.955353, 0]),
        ('central-cover', [-763.161804, -5228.40234, 477.852356], [0, 124.9048, 0]),
    ]),
    'firing-range': ('mp_rr_canyonlands_staging', [
        ('overview', [26507.6, -6928, -26600], [22, 90, 0]),
    ]),
}


def main():
    ident = sys.argv[1]
    name, shots = ROUTES[ident]
    c = Controller()
    status = c.status()
    if any(vm['map'] != name for vm in status.values()):
        c.load(name)
    time.sleep(10)
    out = ROOT / 'docs/candidates' / ident
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for label, origin, angles in shots:
        c.camera(origin, angles, fov=90, settle=8)
        record = c.capture(ident + '-' + label)
        records.append(record)
        print(json.dumps(record), flush=True)
        shutil.copy2(record['path'], out / (label + '.png'))
        (out / 'captures.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    logs = c.export_logs()
    print(json.dumps({'logs': logs}), flush=True)


if __name__ == '__main__':
    main()
