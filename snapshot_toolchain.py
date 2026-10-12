"""Record pinned upstream tools and preserve local source patches, without assets."""
import json, subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'docs/toolchain'

def git(path,*args):
    return subprocess.check_output(['git','-C',str(path),*args])

def snapshot():
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for path in sorted((ROOT/'tools').iterdir()):
        if not (path/'.git').exists():continue
        remote=git(path,'remote','get-url','origin').decode().strip()
        if '://' in remote:
            u=urlsplit(remote)
            remote=urlunsplit((u.scheme,u.hostname or '',u.path,'',''))
        record={'directory':path.relative_to(ROOT).as_posix(),'url':remote,
                'commit':git(path,'rev-parse','HEAD').decode().strip()}
        changed=git(path,'diff','--name-only','HEAD','-z').decode().split('\0')
        allowed={'.cpp','.c','.h','.hpp','.py','.nut','.gnut','.cmake','.txt','.md','.json','.js','.html','.css','.hlsl','.glsl','.yml','.yaml'}
        names=[n for n in changed if n and (Path(n).suffix.lower() in allowed or Path(n).name=='.gitignore')]
        if names:
            patch=git(path,'diff','--binary','HEAD','--',*names)
            if len(patch)>10*1024*1024:raise ValueError('Source patch needs explicit review: '+path.name)
            dest=OUT/'patches'/f'{path.name}.patch';dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(patch)
            record['patch']=dest.relative_to(ROOT).as_posix()
            record['patched_files']=names
        record['excluded_changed_non_source_files']=[n for n in changed if n and n not in names]
        licenses=[]
        for license in path.iterdir():
            if license.is_file() and license.name.lower().startswith(('license','copying','notice')):
                dest=OUT/'licenses'/path.name/license.name;dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(license.read_bytes());licenses.append(dest.relative_to(ROOT).as_posix())
        record['licenses']=licenses
        records.append(record)
    (OUT/'upstreams.json').write_text(json.dumps({'upstreams':records,'excluded':'Downloaded binaries, game inputs, build directories and untracked runtime files remain local.'},indent=2))
    print(json.dumps({'upstreams':len(records),'source_patches':sum('patch' in r for r in records)}))

if __name__=='__main__':snapshot()
