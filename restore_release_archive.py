"""Restore one exact historical ZIP from the authenticated GitHub draft archive.

Requires GitHub CLI authentication and an installed Zstandard CLI. The backup
manifest and every downloaded/reconstructed byte stream are SHA-256 verified.
Only the requested ZIP is left in the chosen destination.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REPO='taskinoz/apex-to-titanfall-2'
ARCHIVE='build-archive-2026-10-25'
BETA='maps-beta-2026-10-25'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def basename(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name in {'.','..'}:
        raise ValueError('Unsafe archive filename')
    return name


def run(*args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode:raise RuntimeError(p.stderr.strip())


def download(tag,name,directory):
    basename(name)
    if tag not in {BETA,ARCHIVE}:raise ValueError('Unexpected release tag')
    path=directory/name
    if not path.exists():
        run('gh','release','download',tag,'--repo',REPO,'--pattern',name,'--dir',str(directory))
    return path


def check(path,size,sha):
    if not re.fullmatch('[0-9a-f]{64}',sha) or path.stat().st_size!=size or digest(path)!=sha:
        raise ValueError('Backup hash or size mismatch: '+path.name)


def zpath(path,executable):
    value=path.resolve().as_posix()
    if os.name=='nt' and 'cygwin' in str(executable).lower():
        return '/cygdrive/'+value[0].lower()+value[2:]
    return str(path.resolve())


def chain(manifest,requested):
    if not manifest.get('complete') or manifest.get('repository')!=REPO:
        raise ValueError('Incomplete or unexpected archive manifest')
    entries={r['name']:r for r in manifest['objects']}
    if len(entries)!=len(manifest['objects']):raise ValueError('Ambiguous archive names')
    if requested not in entries:raise ValueError('Archive not found: '+requested)
    steps=[]; visiting=set()
    def walk(name):
        basename(name)
        if name in visiting:raise ValueError('Cyclic archive references')
        visiting.add(name)
        row=entries[name]
        basename(row['asset_name'])
        if row['encoding']=='zstd-patch':
            basename(row['base_name'])
            if row['base_tag']==ARCHIVE:
                walk(row['base_name'])
                if entries[row['base_name']]['original_sha256']!=row['base_sha256']:
                    raise ValueError('Reference manifest mismatch')
            elif row['base_tag']!=BETA:raise ValueError('Unexpected base release')
        elif row['encoding']!='zip':raise ValueError('Unsupported backup encoding')
        steps.append(row)
        visiting.remove(name)
    walk(requested)
    return steps


def restore(name,destination,zstd,local_current=None):
    basename(name)
    if not name.endswith('.zip'):raise ValueError('Choose an original ZIP filename')
    destination=destination.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/name
    if target.exists():raise ValueError('Destination already exists; preserve it')
    with tempfile.TemporaryDirectory(prefix='release-restore-',dir=destination) as temporary:
        temp=Path(temporary).resolve()
        if temp.parent!=destination:raise ValueError('Restore workspace escaped destination')
        manifest=json.loads(download(ARCHIVE,'archival-objects.json',temp).read_text())
        steps=chain(manifest,name)
        previous=None
        for row in steps:
            asset=download(ARCHIVE,row['asset_name'],temp)
            check(asset,row['asset_bytes'],row['asset_sha256'])
            output=temp/row['name']
            base=None
            if row['encoding']=='zstd-patch':
                if row['base_tag']==BETA:
                    candidate=local_current/row['base_name'] if local_current else None
                    base=candidate if candidate and candidate.is_file() else download(BETA,row['base_name'],temp)
                else:base=temp/row['base_name']
                check(base,row['base_bytes'],row['base_sha256'])
                with output.open('xb') as stream:
                    proc=subprocess.run([str(zstd),'-d','-q','-c','-M4096',
                        '--patch-from='+zpath(base,zstd),zpath(asset,zstd)],stdout=stream,stderr=subprocess.PIPE)
                if proc.returncode:raise RuntimeError(proc.stderr.decode(errors='replace'))
            check(output,row['original_bytes'],row['original_sha256'])
            # All disposable intermediates must be files inside this newly
            # created checked temporary directory. Local current ZIPs survive.
            for disposable in {previous,asset if row['encoding']=='zstd-patch' else None,base}:
                if disposable and disposable!=output and disposable.resolve().parent==temp:
                    disposable.unlink(missing_ok=True)
            previous=output
            print('Restored and verified:',row['name'],flush=True)
        # A concurrent file appearing at the destination must never be replaced.
        # Both paths share a volume; a hardlink publishes these verified bytes
        # atomically, and temporary cleanup removes only the temporary name.
        try:
            os.link(temp/name,target)
        except FileExistsError:
            raise
        except OSError:
            with (temp/name).open('rb') as src,target.open('xb') as dst:
                shutil.copyfileobj(src,dst,8*1024*1024)
            wanted=steps[-1]
            check(target,wanted['original_bytes'],wanted['original_sha256'])
    print(str(target))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('filename')
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--local-current',type=Path)
    p.add_argument('--zstd',type=Path,default=Path(shutil.which('zstd') or 'zstd'))
    args=p.parse_args()
    restore(args.filename,args.destination,args.zstd,args.local_current)
