"""Archive exact historical ZIPs using verified Zstandard deltas where smaller.

Every delta is decoded and SHA-256 checked before upload. References form a
strictly ordered chain ending at a complete ZIP; no current runtime is edited.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import manage_release_archives as m

ZSTD = Path('C:/tools/cygwin/bin/zstd.exe')
OBJECTS = m.REPORT/'archival-objects.json'
DELTAS = m.REPORT/'deltas'


def cygwin(path):
    value = Path(path).resolve().as_posix()
    return '/cygdrive/'+value[0].lower()+value[2:]


def group(row):
    for name in [*m.RELEASES,m.SHARED_UI]:
        if row['name'].startswith(name+'-') or row['name'].startswith(name+'.Preview-'):
            return name
    return None


def version(row):
    match = re.search(r'-(\d+)\.(\d+)\.(\d+)',row['name'])
    return tuple(map(int,match.groups())) if match else (0,0,0)


def references(rows):
    bases = {}
    for name in [*m.RELEASES,m.SHARED_UI]:
        ordered = sorted((r for r in rows if group(r)==name and (r['current'] or r['bytes']>=50*1024*1024)),
                         key=lambda r:(version(r),r['current'],r['scope']=='output'),reverse=True)
        for index,row in enumerate(ordered):
            if index and not row['current'] and row['bytes']>=50*1024*1024:
                bases[(row['scope'],row['name'])]=ordered[index-1]
    return bases


def restored_hash(base,patch):
    proc=subprocess.Popen([str(ZSTD),'-d','-c','-q','-M4096','--patch-from='+cygwin(base),cygwin(patch)],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    h=hashlib.sha256(); size=0
    for data in iter(lambda:proc.stdout.read(8*1024*1024),b''):
        h.update(data); size+=len(data)
    error=proc.stderr.read().decode(errors='replace')
    if proc.wait():raise RuntimeError(error)
    return size,h.hexdigest()


def build_object(row,base,prior):
    original=m.source(row)
    stat=original.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(row['bytes'],row['mtime_ns']):
        raise ValueError('Archive changed since inventory: '+row['name'])
    if prior:
        path=(DELTAS/prior['asset_name'] if prior['encoding']=='zstd-patch' else original)
        if (prior['original_sha256'],prior['original_bytes'])!=(row['sha256'],row['bytes']):
            raise ValueError('Prior backup has different provenance')
        if path.is_file() and m.sha(path)==prior['asset_sha256']:
            return prior,path
        raise ValueError('Saved backup object changed')
    proof={'scope':row['scope'],'name':row['name'],'original_bytes':row['bytes'],
           'original_sha256':row['sha256'],'encoding':'zip','asset_name':row['name'],
           'asset_bytes':row['bytes'],'asset_sha256':row['sha256'],'restored_sha256':row['sha256']}
    if base:
        reference=m.source(base)
        st=reference.stat()
        if (st.st_size,st.st_mtime_ns)!=(base['bytes'],base['mtime_ns']):
            raise ValueError('Reference archive changed')
        path=DELTAS/(row['name']+'.zst')
        if not path.exists():
            proc=subprocess.run([str(ZSTD),'-3','-T1','--mmap-dict','--no-progress',
                                 '--patch-from='+cygwin(reference),cygwin(original),'-o',cygwin(path)],
                                capture_output=True,text=True)
            if proc.returncode:raise RuntimeError(proc.stderr)
        if path.stat().st_size < row['bytes']*.95:
            if restored_hash(reference,path)!=(row['bytes'],row['sha256']):
                raise ValueError('Delta does not restore exact original: '+row['name'])
            proof.update(encoding='zstd-patch',asset_name=path.name,asset_bytes=path.stat().st_size,
                         asset_sha256=m.sha(path),base_name=base['name'],base_scope=base['scope'],
                         base_sha256=base['sha256'],base_bytes=base['bytes'],
                         base_tag=m.BETA if base['current'] else m.ARCHIVE)
            return proof,path
        # This owned generated file is disposable; its resolved parent is fixed.
        if path.resolve().parent != DELTAS.resolve():raise ValueError('Delta escaped storage')
        path.unlink()
    return proof,original


def upload(proof,path,existing):
    asset=existing.get(proof['asset_name'])
    if not asset:
        for attempt in range(3):
            try:
                m.gh('release','upload',m.ARCHIVE,str(path),'--repo',m.REPO)
                break
            except RuntimeError:
                asset=next((a for a in m.release(m.ARCHIVE)['assets'] if a['name']==proof['asset_name']),None)
                if asset and asset.get('state')=='uploaded':break
                if attempt==2:raise
        asset=next(a for a in m.release(m.ARCHIVE)['assets'] if a['name']==proof['asset_name'])
    if (asset.get('state'),asset.get('size'),asset.get('digest'))!=('uploaded',proof['asset_bytes'],'sha256:'+proof['asset_sha256']):
        raise ValueError('Remote backup differs: '+proof['asset_name'])
    return {**proof,'asset_id':asset['id'],'remote_verified':True}


def main():
    data=json.loads(m.PLAN.read_text())
    if not data.get('inventory_complete'):raise ValueError('Incomplete inventory')
    DELTAS.mkdir(parents=True,exist_ok=True)
    beta=m.release(m.BETA)
    if beta['draft'] or not beta['prerelease']:raise ValueError('Current beta is not published')
    for row in (r for r in data['files'] if r['current']):
        asset=next(a for a in beta['assets'] if a['name']==row['name'])
        if (asset['size'],asset.get('digest'))!=(row['bytes'],'sha256:'+row['sha256']):
            raise ValueError('Beta reference differs')
    archive=m.release(m.ARCHIVE)
    if not archive['draft']:raise ValueError('History must remain a draft')
    existing={a['name']:a for a in archive['assets']}
    saved=json.loads(OBJECTS.read_text()) if OBJECTS.exists() else {'complete':False,'objects':[]}
    proofs={(r['scope'],r['name']):r for r in saved['objects']}
    bases=references(data['files'])
    history=[r for r in data['files'] if not r['current']]
    def work(row):
        key=(row['scope'],row['name'])
        prior=proofs.get(key)
        if prior and prior.get('remote_verified'):
            asset=existing.get(prior['asset_name'])
            if asset and (asset.get('state'),asset.get('size'),asset.get('digest'))==('uploaded',prior['asset_bytes'],'sha256:'+prior['asset_sha256']):
                if prior['original_sha256']!=row['sha256']:raise ValueError('Prior original differs')
                return prior
        proof,path=build_object(row,bases.get(key),proofs.get(key))
        return upload(proof,path,existing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(work,r) for r in history]
        for future in as_completed(futures):
            try:
                proof=future.result()
            except Exception:
                for pending in futures:pending.cancel()
                raise
            proofs[(proof['scope'],proof['name'])]=proof
            m.save(OBJECTS,{'date':'2026-10-25','complete':False,'repository':m.REPO,
                           'beta_tag':m.BETA,'archive_tag':m.ARCHIVE,'objects':list(proofs.values())})
            if proof['encoding']=='zstd-patch':
                disposable=DELTAS/proof['asset_name']
                if disposable.exists():
                    if disposable.resolve().parent!=DELTAS.resolve() or m.sha(disposable)!=proof['asset_sha256']:
                        raise ValueError('Unexpected disposable delta')
                    disposable.unlink()  # Uploaded hash and durable receipt already verified.
            print(f"Backed up {len(proofs)}/{len(history)}: {proof['name']} ({proof['asset_bytes']/2**20:.1f} MiB; {proof['encoding']})",flush=True)
    # Cross-check every original and every reference before recording completion.
    for row in history:
        proof=proofs[(row['scope'],row['name'])]
        if proof['original_sha256']!=row['sha256']:raise ValueError('Original proof mismatch')
        if proof['encoding']=='zstd-patch' and proof['base_tag']==m.ARCHIVE:
            base=proofs[(proof['base_scope'],proof['base_name'])]
            if base['original_sha256']!=proof['base_sha256']:raise ValueError('Reference chain mismatch')
    saved={'date':'2026-10-25','complete':True,'repository':m.REPO,
           'beta_tag':m.BETA,'archive_tag':m.ARCHIVE,'objects':list(proofs.values())}
    m.save(OBJECTS,saved)
    for path in [OBJECTS,m.ROOT/'restore_release_archive.py',m.REPORT/'archive-manifest.json']:
        prior=next((a for a in m.release(m.ARCHIVE)['assets'] if a['name']==path.name),None)
        if prior is None:m.gh('release','upload',m.ARCHIVE,str(path),'--repo',m.REPO)
        elif prior.get('digest')!='sha256:'+m.sha(path):raise ValueError('Manifest already differs')
    print(json.dumps({'historical_archives':len(history),
                      'original_GiB':sum(r['bytes'] for r in history)/2**30,
                      'remote_GiB':sum(r['asset_bytes'] for r in proofs.values())/2**30}),flush=True)


def prune_uploaded():
    saved=json.loads(OBJECTS.read_text())
    remote=m.release(m.ARCHIVE)
    if not remote['draft']:raise ValueError('Unexpected archive visibility')
    assets={a['name']:a for a in remote['assets']}
    count=0
    for proof in saved['objects']:
        if proof['encoding']!='zstd-patch' or not proof.get('remote_verified'):continue
        path=DELTAS/proof['asset_name']
        if path.resolve().parent!=DELTAS.resolve():raise ValueError('Delta escaped reviewed directory')
        if not path.exists():continue
        asset=assets.get(path.name)
        if not asset or (asset['size'],asset.get('digest'))!=(proof['asset_bytes'],'sha256:'+proof['asset_sha256']):
            raise ValueError('No matching remote delta')
        if m.sha(path)!=proof['asset_sha256']:raise ValueError('Local delta changed')
        path.unlink()
        count+=1
    print('Removed verified uploaded temporary deltas:',count,flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--prune-uploaded']:prune_uploaded()
    elif sys.argv[1:]:raise SystemExit('Usage: archive_release_history.py [--prune-uploaded]')
    else:main()
