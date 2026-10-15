"""Move ignored output off C and deduplicate immutable generated assets safely.

Source Git files, game installations, scripts and configuration are excluded.
Each moved file is hashed during copying and re-read before removing its source.
Hardlinks are restricted to explicitly chosen generated binary extensions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent
STORE = Path('D:/Games/ApexToTitanfallWork/project-storage')
BINARY = {'.bsp', '.stbsp', '.rpak', '.starpak', '.npz', '.bin', '.dds', '.vg', '.rmdl', '.phy'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(8*1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def relocate():
    source, target = ROOT/'output', STORE/'output'
    STORE.mkdir(parents=True, exist_ok=True)
    if source.is_junction():
        if source.resolve() != target.resolve():
            raise ValueError('Unexpected output junction')
        print('Output already relocated')
        return
    if source.resolve().parent != ROOT or source.is_symlink():
        raise ValueError('Output escaped the workspace')
    files, links = [], []
    for base, dirs, names in os.walk(source, followlinks=False):
        base = Path(base)
        for name in list(dirs):
            path = base/name
            if path.is_junction() or path.is_symlink():
                if path != source/'distribution-backups' or path.resolve() != Path('D:/Games/ApexToTitanfallWork/new-arena-ports/distribution-backups-archive'):
                    raise ValueError('Unreviewed nested directory link: '+str(path))
                links.append(path)
                dirs.remove(name)
            else:
                files.append(path)
        files.extend(base/name for name in names)
    receipt = STORE/'relocation.json'
    rows = json.loads(receipt.read_text())['files'] if receipt.exists() else []
    total = 0
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        dest = target/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            sha = digest(path)
            if dest.stat().st_size != path.stat().st_size or digest(dest) != sha:
                raise ValueError('Conflicting archived file: '+str(relative))
        else:
            temporary = dest.with_name(dest.name+'.relocating')
            h = hashlib.sha256()
            with path.open('rb') as src, temporary.open('wb') as dst:
                for data in iter(lambda: src.read(8*1024*1024), b''):
                    dst.write(data)
                    h.update(data)
                dst.flush()
                os.fsync(dst.fileno())
            sha = h.hexdigest()
            if digest(temporary) != sha or temporary.stat().st_size != path.stat().st_size:
                raise ValueError('Copy verification failed: '+str(relative))
            shutil.copystat(path, temporary)
            os.replace(temporary, dest)
        size = path.stat().st_size
        # Only the checked workspace source file is removed, never a directory tree.
        if path.resolve().is_relative_to(source.resolve()):
            path.unlink()
        else:
            raise ValueError('Source changed during relocation')
        rows.append(dict(path=relative.as_posix(), bytes=size, sha256=sha))
        total += size
        if len(rows)%100 == 0:
            receipt.write_text(json.dumps(dict(files=rows, complete=False), indent=2))
            print('Moved and verified', len(rows), 'files;', round(total/2**30,2), 'GiB this run', flush=True)
    for path in links:
        dest = target/path.relative_to(source)
        if not dest.exists():
            subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(dest),str(path.resolve())],check=True)
        if dest.resolve()!=path.resolve():
            raise ValueError('Nested link mismatch')
        os.rmdir(path)  # Remove the link itself; never recurse into its target.
    for path in sorted((p for p in files if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
        path.rmdir()
    source.rmdir()
    # Paths are fixed, verified literals; mklink only creates the empty junction.
    subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(source),str(target)], check=True)
    if source.resolve() != target.resolve():
        raise ValueError('Junction verification failed')
    receipt.write_text(json.dumps(dict(files=rows, complete=True, source=str(source), target=str(target),
                                      verified_bytes=sum(r['bytes'] for r in rows)), indent=2))
    print('Relocation complete:',sum(r['bytes'] for r in rows),'bytes',flush=True)


def deduplicate(apply=False):
    roots = [STORE/'output', ROOT/'northstar']
    groups = {}
    for root in roots:
        for path in root.rglob('*'):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in BINARY and path.stat().st_size >= 1024*1024:
                groups.setdefault((path.drive.lower(),path.stat().st_size),[]).append(path)
    changed, saved = [], 0
    for (_,size), paths in groups.items():
        if len(paths)<2:
            continue
        hashes = {}
        for path in paths:
            sha = digest(path)
            canonical = hashes.setdefault(sha,path)
            if canonical == path or os.path.samefile(canonical,path):
                continue
            if apply:
                temp = path.with_name(path.name+'.deduplicating')
                if temp.exists():
                    raise ValueError('Unfinished deduplication: '+str(temp))
                os.link(canonical,temp)
                if digest(temp)!=sha:
                    temp.unlink()
                    raise ValueError('Hardlink verification failed')
                os.replace(temp,path)
            changed.append(dict(path=str(path),canonical=str(canonical),bytes=size,sha256=sha))
            saved += size
    report=dict(applied=apply,logical_duplicate_bytes=saved,files=changed,
                policy='Generated binary assets only, same volume; builders must replace files atomically before mutation')
    STORE.mkdir(parents=True,exist_ok=True)
    (STORE/('deduplication.json' if apply else 'deduplication-plan.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(applied=apply,duplicate_files=len(changed),duplicate_GiB=round(saved/2**30,2))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['relocate','deduplicate'])
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    relocate() if a.action=='relocate' else deduplicate(a.apply)
