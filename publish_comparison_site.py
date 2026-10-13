"""Export a portable, secret-free static comparison and future release site.

Keep snapshots outside private harness output. No game session, absolute local
path, process ID, log or credential is copied into the public catalogue.
"""
import argparse, hashlib, json, re, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SITE=ROOT/'site'
SLUG=re.compile(r'[a-z0-9][a-z0-9-]{0,70}\Z')

def export(snapshot, comparison_overrides=None, include_downloads=False, findings=None, map_ids=None):
    if not SLUG.fullmatch(snapshot):raise ValueError('Invalid snapshot name')
    catalogue=json.loads((SITE/'maps.json').read_text(encoding='utf-8'))
    dist=SITE/'dist';dist.mkdir(parents=True,exist_ok=True)
    public_path=dist/'catalogue.json'
    previous=json.loads(public_path.read_text()) if public_path.exists() else {'maps':[]}
    old={m['id']:m for m in previous['maps']}
    maps=[]
    for row in catalogue['maps']:
        if not SLUG.fullmatch(row['id']):raise ValueError('Invalid map ID')
        if map_ids is not None and row['id'] not in map_ids:
            if row['id'] not in old:raise ValueError('Cannot preserve an unpublished map: '+row['id'])
            maps.append(old[row['id']]);continue
        source=ROOT/(comparison_overrides or {}).get(row['id'],row['comparison'])
        data=json.loads((source/'comparison.json').read_text())
        if data['route']['source_map']!=row['source_map'] or data['route']['target_map']!=row['target_map']:
            raise ValueError('Wrong map comparison: '+row['id'])
        mod=json.loads((ROOT/'northstar'/row['package']/'mod.json').read_text())
        target=dist/'captures'/row['id']/snapshot;target.mkdir(parents=True,exist_ok=True)
        shots=[]
        for pair,shot in zip(data['pairs'],data['route']['shots'],strict=True):
            if pair['name']!=shot['name'] or not SLUG.fullmatch(pair['name']):raise ValueError('Invalid shot')
            record={'name':pair['name'],'origin':shot['origin'],'angles':shot['angles'],'fov':shot.get('fov',90)}
            observations=(findings or {}).get(row['id'],{}).get(pair['name'])
            if observations:
                if not isinstance(observations,list) or not all(isinstance(x,str) for x in observations):
                    raise ValueError('Findings must be a list of plain-text observations')
                record['findings']=observations
            for engine in ('r5r','northstar'):
                meta=pair[engine];filename=pair['name']+'-'+engine+'.png'
                image=source/meta['gallery_path']
                if image.parent.resolve()!=source.resolve():raise ValueError('Image leaves comparison folder')
                digest=hashlib.sha256(image.read_bytes()).hexdigest()
                if digest!=meta['sha256']:raise ValueError('Capture hash mismatch: '+filename)
                dest=target/filename
                if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:
                    raise ValueError('Snapshot is immutable; choose a new snapshot label')
                shutil.copy2(image,dest)
                record[engine]={'image':dest.relative_to(dist).as_posix(),'sha256':digest,
                                'width':meta['width'],'height':meta['height'],'captured':meta['captured']}
            shots.append(record)
        item={k:row[k] for k in ('id','name','source_map','target_map','status','description','modes','notes','download')}
        item.update(version=mod['Version'],source_offset=data['route']['source_offset'])
        if include_downloads:
            releases=json.loads((ROOT/'output/player-distributions.json').read_text())
            release=releases[row['package']];archive=ROOT/release['path']
            if row['package']+'-'+mod['Version']+'-Northstar.zip'!=archive.name:
                raise ValueError('Download version differs from map package')
            h=hashlib.sha256()
            with archive.open('rb') as f:
                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
            if h.hexdigest()!=release['sha256']:raise ValueError('Release ZIP hash mismatch')
            dest=dist/'downloads'/archive.name;dest.parent.mkdir(exist_ok=True)
            shutil.copy2(archive,dest);item['download']=dest.relative_to(dist).as_posix()
            item['download_sha256']=h.hexdigest();item['download_bytes']=archive.stat().st_size
        snapshots=old.get(row['id'],{}).get('snapshots',[])
        fresh={'id':snapshot,'version':mod['Version'],'shots':shots}
        prior=next((s for s in snapshots if s['id']==snapshot),None)
        if prior and prior!=fresh:raise ValueError('Snapshot metadata changed; choose a new label')
        if not prior:snapshots.append(fresh)
        item['snapshots']=snapshots;item['latest']=snapshot;maps.append(item)
    public={'title':catalogue['title'],'maps':maps}
    public_path.write_text(json.dumps(public,indent=2),encoding='utf-8')
    template=(SITE/'index.template.html').read_text(encoding='utf-8')
    embedded=json.dumps(public).replace('<','\\u003c')
    (dist/'index.html').write_text(template.replace('/*CATALOGUE*/',embedded),encoding='utf-8')
    for asset in ('style.css','viewer.js'):shutil.copy2(SITE/asset,dist/asset)
    print(json.dumps({'site':str(dist/'index.html'),'maps':len(maps),'snapshot':snapshot,'public_paths_only':True}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--snapshot',required=True)
    p.add_argument('--drop-off',help='Workspace-relative comparison directory')
    p.add_argument('--phase-runner',help='Workspace-relative comparison directory')
    p.add_argument('--include-downloads',action='store_true',help='Copy verified current player ZIPs into the static site')
    p.add_argument('--findings',type=Path,help='Reviewed plain-text observations, keyed by map ID and shot name')
    p.add_argument('--maps',nargs='+',help='Update only these maps, preserving other published snapshots exactly')
    a=p.parse_args();overrides={k:v for k,v in [('drop-off',a.drop_off),('phase-runner',a.phase_runner)] if v}
    findings=json.loads(a.findings.read_text(encoding='utf-8')) if a.findings else None
    if a.maps and not set(a.maps)<=set(r['id'] for r in json.loads((SITE/'maps.json').read_text())['maps']):
        raise ValueError('Unknown map selection')
    export(a.snapshot,overrides,a.include_downloads,findings,set(a.maps) if a.maps else None)
