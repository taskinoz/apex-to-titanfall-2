"""Capture original Apex references for the accepted expanded native routes."""
import hashlib
import json
import sys
from pathlib import Path
from map_pack_lifetime import ROOT
sys.path.insert(0,str(ROOT/'r5-harness'))
from harness import Controller


def capture():
    c=Controller()
    for ident in ('firing-range','party-crasher','overflow'):
        route=json.loads((ROOT/'r5-harness/routes'/(ident+'-expanded-survey.json')).read_text())
        if not all(v['map']==route['source_map'] and v['ready'] for v in c.status().values()):
            c.load(route['source_map'])
        out=ROOT/'output/atlas-lifetime/r5r'/ident
        out.mkdir(parents=True,exist_ok=True)
        captures=[]
        for shot in route['shots']:
            origin=[a+b for a,b in zip(shot['origin'],route['source_offset'])]
            c.camera(origin,shot['angles'],shot['fov'],shot['settle'])
            image=c.capture(ident+'-'+shot['name'])
            if hashlib.sha256(Path(image['path']).read_bytes()).hexdigest()!=image['sha256']:
                raise ValueError('Native source capture hash mismatch')
            captures.append(dict(name=shot['name'],source=image))
            (out/'captures.json').write_text(json.dumps(dict(route=route,captures=captures),indent=2))
            print(ident,shot['name'],image['path'],flush=True)
        c.script('client','R5H_ClearCamera($TICKET)')
        c.export_logs()


if __name__=='__main__':capture()
