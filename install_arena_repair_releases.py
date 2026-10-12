"""Install the two verified runtime packages; retain replaced mods for rollback."""
import datetime,json,os,shutil
from pathlib import Path
from package_player_mods import ROOT,RELEASES,runtime_files,digest

def install(names=('PhaseRunner','ArenaComposite')):
    profile=Path('D:/Games/Titanfall2/R2Northstar').resolve()
    if not (profile/'Northstar.dll').is_file():raise ValueError('Unexpected game profile')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    stage=profile/'.arena-release-staging'/stamp
    backup=profile/'.arena-release-backups'/stamp
    for p in (stage,backup):
        if not p.resolve().is_relative_to(profile):raise ValueError('Profile path escaped')
        p.mkdir(parents=True,exist_ok=False)
    records={}
    for name,folder in [('PhaseRunner','PhaseRunner.Preview'),('ArenaComposite','ArenaComposite')]:
        if name not in names:continue
        source=ROOT/'northstar'/name
        identity=json.loads((source/'mod.json').read_text())
        if identity['Name']!=name or identity['Version']!=RELEASES[name]['version']:raise ValueError('Wrong release identity')
        target=stage/folder;target.mkdir()
        hashes={}
        for p in runtime_files(source):
            rel=p.relative_to(source);dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest);wanted=digest(p)
            if digest(dest)!=wanted:raise ValueError('Staged runtime hash mismatch')
            hashes[rel.as_posix()]=wanted
        installed=profile/'mods'/folder
        if installed.resolve().parent != (profile/'mods').resolve():raise ValueError('Unexpected installed path')
        if installed.exists():os.replace(installed,backup/folder)
        try:os.replace(target,installed)
        except Exception:
            if (backup/folder).exists():os.replace(backup/folder,installed)
            raise
        records[name]=dict(version=identity['Version'],installed=str(installed),backup=str(backup/folder),runtime_sha256=hashes)
    enabled_path=profile/'enabledmods.json';shutil.copy2(enabled_path,backup/'enabledmods.json')
    enabled=json.loads(enabled_path.read_text())
    changed=[*records]
    if 'PhaseRunner' in records:changed.append('PhaseRunner.Preview')
    for name in changed:
        if name in enabled:
            enabled[name]={version:False for version in enabled[name]}
    for name,r in records.items():enabled.setdefault(name,{})[r['version']]=True
    temp=enabled_path.with_suffix('.repair.json');temp.write_text(json.dumps(enabled,indent=2));os.replace(temp,enabled_path)
    receipt=ROOT/'output/arena-repair-installation.json'
    previous=json.loads(receipt.read_text()) if receipt.exists() else {}
    previous.update(records);receipt.write_text(json.dumps(previous,indent=2))
    print('Installed',', '.join(records),'replaced mods retained at',backup,flush=True)

if __name__=='__main__':install()
