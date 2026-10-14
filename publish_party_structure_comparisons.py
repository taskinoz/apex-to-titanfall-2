"""Publish only matched, hash-verified Party Crasher roof and edge references."""
import json
import shutil
from pathlib import Path
from package_player_mods import ROOT, digest
from publish_comparison_site import export


def publish():
    root=ROOT/'output/party-edge-roof'
    source=json.loads((root/'source.json').read_text())
    native=json.loads((root/'native.json').read_text())
    refs={r['name']:r for r in source['captures']}
    actual={r['name']:r for r in native['shots']}
    route=dict(native['route']);route['shots']=[s for s in route['shots'] if s['name'] in refs]
    gallery=root/'comparison';gallery.mkdir(exist_ok=True)
    pairs=[]
    for shot in route['shots']:
        r5=refs[shot['name']]['source'];ns=actual[shot['name']]['northstar']
        if r5['map']!=route['source_map'] or ns['state']['contexts']['client']['level']!=route['target_map']:
            raise ValueError('Wrong capture map')
        for meta,wanted in ((r5['camera']['origin'],shot['origin']),
                            (ns['state']['contexts']['client']['origin'],shot['origin'])):
            if any(abs(a-b)>.05 for a,b in zip(meta,wanted,strict=True)):
                raise ValueError('Camera position mismatch')
        for angles in (r5['camera']['angles'],ns['state']['contexts']['client']['angles']):
            if any(abs((a-b+180)%360-180)>.05 for a,b in zip(angles,shot['angles'],strict=True)):
                raise ValueError('Camera angle mismatch')
        if r5['camera']['fov']!=shot['fov']:
            raise ValueError('Source FOV mismatch')
        pair=dict(name=shot['name'])
        for engine,meta in (('r5r',r5),('northstar',ns)):
            if digest(meta['path'])!=meta['sha256']:raise ValueError('Capture hash changed')
            dest=gallery/(shot['name']+'-'+engine+'.png');shutil.copy2(meta['path'],dest)
            pair[engine]={k:meta[k] for k in ('width','height','captured','sha256')}
            pair[engine]['gallery_path']=dest.name
        if (r5['width'],r5['height'])!=(ns['width'],ns['height']):raise ValueError('Resolution mismatch')
        pairs.append(pair)
    (gallery/'comparison.json').write_text(json.dumps(dict(route=route,pairs=pairs),indent=2))
    path=ROOT/'site/maps.json';catalogue=json.loads(path.read_text())
    row=next(r for r in catalogue['maps'] if r['id']=='party-crasher')
    from finalize_party_structure import NOTE
    row.update(comparison=gallery.relative_to(ROOT).as_posix(),
               route='r5-harness/routes/party-crasher-edge-roof-survey.json',notes='0.4.0: '+NOTE)
    path.write_text(json.dumps(catalogue,indent=2)+'\n')
    findings={'party-crasher':{
        'spawn-right':['Boundary rock geometry and retained source wall sections are restored. Source foliage, animated advertising and atmosphere remain richer.'],
        'opposite-spawn-right':['Recovered structures use original Apex transforms and source-owned collision. Lighting and source effects remain approximations.'],
        'west-edge':['Original facade/window modules now close structural gaps; some dense inset windows remain outside this recovery budget.'],
        'east-edge':['Additional source windows and structural sections are retained. This is an exterior diagnostic camera view.'],
        'north-roof':['Source rooftop vents are restored. Source foliage and animated billboard effects remain incomplete.'],
        'south-roof':['Original rooftop equipment is recovered; this angle is partly occluded by the adjoining building and planter. Dense source roof vegetation remains omitted.']}}
    (ROOT/'site/party-structure-findings.json').write_text(json.dumps(findings,indent=2)+'\n')
    export('2026-10-14-party-structure',findings=findings,map_ids={'party-crasher'},refresh_versions=True)
    print('Published',len(pairs),'matched roof/edge views; earlier snapshots retained',flush=True)


if __name__=='__main__':publish()
