"""Turn a Northstar harness route run into a port-only gallery for the comparison site.

Current-Apex ports (Thermal Station, Thunderdome) have no R5Reloaded source to capture, so their site entries carry
Northstar captures only. This writes the comparison folder publish_comparison_site.py reads: hash-verified PNGs
named <shot>-northstar.png and a comparison.json whose pairs have no `r5r` capture. Shots named `warmup` (the
first capture after a map load, while streaming settles) are left out.

  python publish_port_gallery.py <map id> <route.json> <harness route-result.json> <output folder>
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def gallery(map_id, route, result, out):
    row = next(r for r in json.loads((ROOT/'site/maps.json').read_text(encoding='utf-8'))['maps'] if r['id'] == map_id)
    route = json.loads(Path(route).read_text()); result = json.loads(Path(result).read_text())
    if route['map'] != row['target_map'] or result['map'] != row['target_map']:
        raise ValueError('Route is not for '+row['target_map'])
    captures = {re.sub(r'-[0-9a-f]{8}$', '', Path(c['path']).stem): c for c in result['captures']}
    out = Path(out); out.mkdir(parents=True, exist_ok=True); shots, pairs = [], []
    for shot in route['shots']:
        if shot['name'] == 'warmup':
            continue
        c = captures[shot['name']]; name = shot['name']+'-northstar.png'
        shutil.copy2(c['path'], out/name)
        digest = hashlib.sha256((out/name).read_bytes()).hexdigest()
        if digest != c['sha256']:
            raise ValueError('Capture hash mismatch: '+name)
        shots.append({k: shot[k] for k in ('name', 'origin', 'angles', 'fov')})
        pairs.append(dict(name=shot['name'], northstar=dict(width=c['width'], height=c['height'], captured=c['captured'],
                                                             sha256=digest, gallery_path=name)))
    data = dict(route=dict(title=route.get('title', row['name']), source_map=row['source_map'], target_map=row['target_map'],
                           source_offset=[0, 0, 0], mode=route.get('mode'), shots=shots), pairs=pairs)
    (out/'comparison.json').write_text(json.dumps(data, indent=2))
    print(json.dumps(dict(map=map_id, shots=len(pairs), folder=str(out))))


if __name__ == '__main__':
    gallery(*sys.argv[1:5])
