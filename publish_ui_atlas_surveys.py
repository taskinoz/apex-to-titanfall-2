"""Assemble accepted native/R5R captures; preserve private paths outside the site."""
import hashlib
import json
import shutil
from pathlib import Path
from map_pack_lifetime import ROOT


def build():
    pairs_config={'firing-range':'ApexFiringRange','party-crasher':'ArenaPartyCrasher','overflow':'ArenaOverflow'}
    config_path=ROOT/'site/maps.json';catalogue=json.loads(config_path.read_text())
    for ident,package in pairs_config.items():
        source=json.loads((ROOT/'output/atlas-lifetime/r5r'/ident/'captures.json').read_text())
        native=json.loads((ROOT/'output/atlas-lifetime'/(package+'.json')).read_text())
        route=source['route'];pairs=[]
        if len(source['captures'])!=len(route['shots']) or len(native['shots'])!=len(route['shots']):
            raise ValueError('Expanded capture route incomplete: '+ident)
        gallery=ROOT/'output/ui-atlas-surveys'/ident;gallery.mkdir(parents=True,exist_ok=True)
        for shot,r5,ns in zip(route['shots'],source['captures'],native['shots'],strict=True):
            if {shot['name'],r5['name'],ns['name']}!={shot['name']} or ns['camera']!=shot:
                raise ValueError('Camera route changed between engines')
            expected_source=[a+b for a,b in zip(shot['origin'],route['source_offset'])]
            a=r5['source'];b=ns['northstar']
            if a['map']!=route['source_map'] or b['state']['contexts']['client']['level']!=route['target_map']:
                raise ValueError('Capture belongs to a different active map')
            for actual,wanted in ((a['camera']['origin'],expected_source),(a['state']['client']['origin'],expected_source),
                                  (b['state']['contexts']['client']['origin'],shot['origin'])):
                if any(abs(x-y)>.05 for x,y in zip(actual,wanted,strict=True)):
                    raise ValueError('Captured camera position differs from route')
            pair=dict(name=shot['name'],route_camera=shot)
            for engine,meta in (('r5r',r5['source']),('northstar',ns['northstar'])):
                if hashlib.sha256(Path(meta['path']).read_bytes()).hexdigest()!=meta['sha256']:
                    raise ValueError('Native capture hash mismatch')
                dest=gallery/(shot['name']+'-'+engine+'.png');shutil.copy2(meta['path'],dest)
                pair[engine]={k:meta[k] for k in ('width','height','captured','sha256')}
                pair[engine]['gallery_path']=dest.name
            if (pair['r5r']['width'],pair['r5r']['height'])!=(pair['northstar']['width'],pair['northstar']['height']):
                raise ValueError('Comparison resolutions differ')
            pairs.append(pair)
        (gallery/'comparison.json').write_text(json.dumps(dict(route=route,pairs=pairs),indent=2))
        row=next(r for r in catalogue['maps'] if r['id']==ident)
        row.update(comparison=gallery.relative_to(ROOT).as_posix(),route='r5-harness/routes/'+ident+'-expanded-survey.json')
        row['notes']='0.3.1 fixes the combined-install UI atlas crash using the shared ApexMaps.UI companion. Adds five new matched viewpoints. '+row['notes']
        print(ident,len(pairs),'matched native comparisons assembled',flush=True)
    for row in catalogue['maps']:
        if row['id'] not in pairs_config:
            row['notes']+=' The UI atlas hotfix shares loading artwork and minimaps through ApexMaps.UI; geometry and lighting are unchanged.'
    config_path.write_text(json.dumps(catalogue,indent=2)+'\n')


if __name__=='__main__':build()
