"""Verify matched native cameras, public screenshots and unchanged runtime files."""
import hashlib
import json
import zipfile
from pathlib import Path
from PIL import Image
from package_player_mods import RELEASES, digest, runtime_files

ROOT=Path(__file__).resolve().parent

def near(actual,wanted,angles=False):
    if not isinstance(actual,list) or len(actual)!=3:
        raise ValueError('Missing native camera coordinates')
    delta=[((a-b+180)%360-180) if angles else a-b for a,b in zip(actual,wanted)]
    if any(abs(d)>.05 for d in delta):
        raise ValueError('Native coordinates differ from route')

def verify():
    report={'date':'2026-10-12','maps':{},'runtime_unchanged':{},'checks':{}}
    for name in ('drop-off','phase-runner'):
        folder=ROOT/'r5-harness/output'/f'{name}-survey'
        data=json.loads((folder/'comparison.json').read_text())
        job=data['route']
        if len(data['pairs'])!=len(job['shots']):raise ValueError('Incomplete route')
        records=[]
        for pair,shot in zip(data['pairs'],job['shots'],strict=True):
            if pair['name']!=shot['name']:raise ValueError('Wrong view order')
            source=[a+b for a,b in zip(shot['origin'],job['source_offset'])]
            for engine in ('r5r','northstar'):
                record=pair[engine]
                image=folder/record['gallery_path']
                if digest(image)!=record['sha256']:raise ValueError('Native screenshot hash changed')
                with Image.open(image) as im:
                    if im.size!=(1280,720) or im.size!=(record['width'],record['height']):
                        raise ValueError('Capture resolution differs')
                if engine=='r5r':
                    if record['map']!=job['source_map']:raise ValueError('Source map differs')
                    contexts=record['state']
                    for context in ('server','client'):
                        if contexts[context]['map']!=job['source_map'] or not contexts[context]['ready']:
                            raise ValueError('Source context is not ready')
                    near(contexts['client']['origin'],source)
                    near(contexts['client']['angles'],shot['angles'],True)
                    if record['camera']['fov']!=shot.get('fov',90):raise ValueError('Source FOV differs')
                else:
                    contexts=record['state']['contexts']
                    for context in ('ui','client','server'):
                        if contexts[context]['level']!=job['target_map'] or not contexts[context]['ready']:
                            raise ValueError('Target context is not ready')
                    near(contexts['client']['origin'],shot['origin'])
                    near(contexts['client']['angles'],shot['angles'],True)
                    near(contexts['server']['playerOrigin'],[shot['origin'][0],shot['origin'][1],shot['origin'][2]-64])
            records.append({'view':shot['name'],'source_sha256':pair['r5r']['sha256'],'port_sha256':pair['northstar']['sha256']})
        report['maps'][name]={'pairs':len(records),'native_cameras_verified':True,'captures':records}
    catalogue=json.loads((ROOT/'site/dist/catalogue.json').read_text())
    public_images=[]
    for m in catalogue['maps']:
        for snapshot in m['snapshots']:
            for shot in snapshot['shots']:
                for engine in ('r5r','northstar'):
                    record=shot[engine]
                    path=ROOT/'site/dist'/record['image']
                    if digest(path)!=record['sha256']:raise ValueError('Public capture differs')
                    public_images.append(record['image'])
    if len(public_images)!=len(set(public_images)):raise ValueError('Duplicate public capture path')
    serialized=json.dumps(catalogue).lower()
    for private in ('session-token','password','bearer ','c:\\users','d:\\games','native_path','game_pid'):
        if private in serialized:raise ValueError('Private metadata leaked into public catalogue')
    report['checks']['public_pngs_verified']=len(public_images)
    releases=json.loads((ROOT/'output/player-distributions.json').read_text())
    for name in RELEASES:
        source=ROOT/'northstar'/name
        release=releases[name]
        archive=ROOT/release['path']
        if digest(archive)!=release['sha256']:raise ValueError('Release archive changed')
        hashes={}
        with zipfile.ZipFile(archive) as z:
            for path in runtime_files(source):
                relative=path.relative_to(source).as_posix()
                wanted=digest(path)
                h=hashlib.sha256()
                with z.open(name+'/'+relative) as f:
                    for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
                if h.hexdigest()!=wanted:raise ValueError('Runtime changed: '+relative)
                hashes[relative]=wanted
        report['runtime_unchanged'][name]={'version':RELEASES[name]['version'],'runtime_files':hashes,'archive_sha256':release['sha256']}
        print(name+': runtime files match the existing release',flush=True)
    out=ROOT/'output/area-survey/validation.json'
    out.write_text(json.dumps(report,indent=2))
    print(json.dumps({'native_pairs':sum(m['pairs'] for m in report['maps'].values()),'public_pngs':len(public_images),'validation':str(out)}))

if __name__=='__main__':verify()
