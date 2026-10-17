"""Verify every exported image, latest build camera and historical snapshot."""
import json
import re
import subprocess
from pathlib import Path
from PIL import Image
from refresh_site_captures import ROOT,OUT,SNAPSHOT,write
from package_player_mods import digest


def verify():
    site=ROOT/'site/dist';catalogue=json.loads((site/'catalogue.json').read_text())
    previous=json.loads(subprocess.check_output(['git','show','HEAD:site/dist/catalogue.json'],cwd=ROOT))
    prior_count=0
    for old in previous['maps']:
        current_map=next(m for m in catalogue['maps'] if m['id']==old['id'])
        snapshots={s['id']:s for s in current_map['snapshots']}
        for snapshot in old['snapshots']:
            if snapshots.get(snapshot['id'])!=snapshot:raise ValueError('Historical snapshot changed')
            prior_count+=1
    html=(site/'index.html').read_text(encoding='utf-8')
    embedded=re.search(r'<script id="catalogue" type="application/json">(.*?)</script>',html,re.S)
    if not embedded or json.loads(embedded[1])!=catalogue:raise ValueError('Portable HTML catalogue differs')
    count=0;all_paths=set();summary={}
    configurations={m['id']:m for m in json.loads((ROOT/'site/maps.json').read_text())['maps']}
    for m in catalogue['maps']:
        config=configurations[m['id']];current=json.loads((ROOT/'northstar'/config['package']/'mod.json').read_text())['Version']
        latest=next(s for s in m['snapshots'] if s['id']==m['latest'])
        if m['latest']!=SNAPSHOT or latest['version']!=current or m['version']!=current:raise ValueError('Stale default build')
        route=json.loads((OUT/m['id']/'route.json').read_text());native=json.loads((OUT/m['id']/'native-captures.json').read_text())
        captures={r['shot']['name']:r for r in native['captures']}
        if len(latest['shots'])!=len(route['shots']):raise ValueError('Incomplete latest gallery')
        for q in latest['shots']:
            wanted=next(s for s in route['shots'] if s['name']==q['name'])
            if any(q[k]!=wanted[k] for k in ('origin','angles','fov')):raise ValueError('Public camera mismatch')
            private=captures[q['name']]['capture']
            if private['sha256']!=q['northstar']['sha256']:raise ValueError('Public native image is not tested capture')
            if not private['state']['contexts']['client']['alive']:raise ValueError('Dead camera player')
        summary[m['id']]=dict(version=current,views=len(latest['shots']))
        for snap in m['snapshots']:
            for q in snap['shots']:
                for engine in ('r5r','northstar'):
                    record=q[engine];relative=Path(record['image']);path=site/relative
                    if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe public asset path')
                    if record['image'] in all_paths:raise ValueError('Duplicate snapshot path')
                    all_paths.add(record['image'])
                    if digest(path)!=record['sha256']:raise ValueError('Image hash mismatch: '+record['image'])
                    with Image.open(path) as im:
                        if im.size!=(record['width'],record['height']):raise ValueError('Image dimensions differ')
                    count+=1
    serialized=json.dumps(catalogue).lower()
    for private in ('session-token','password','bearer ','c:\\users','d:\\games','native_path','game_pid'):
        if private in serialized:raise ValueError('Private capture metadata leaked')
    if len(summary)!=5 or sum(m['views'] for m in summary.values())!=53:raise ValueError('Unexpected map/view coverage')
    report=dict(maps=summary,latest_views=53,latest_images=106,total_images_verified=count,
                portable_html_matches_catalogue=True,all_images_hash_and_dimensions_verified=True,
                private_metadata_excluded=True,old_snapshots_preserved=True,historical_snapshot_records_verified=prior_count)
    write(ROOT/'docs/site-image-refresh-validation-2026-10-18.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':verify()
