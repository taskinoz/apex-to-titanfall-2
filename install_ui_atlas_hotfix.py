"""Update existing current-version installs; preserve rollback and user enablement."""
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS, audit_shared, scope, audit
from release_ui_atlas_hotfix import VERSIONS
from package_player_mods import digest


def install():
    if not json.loads((ROOT/'docs/conversion/ui-atlas-lifetime-validation.json').read_text())['passed']:
        raise ValueError('Combined-install native validation missing')
    audit_shared()
    check=subprocess.run(['powershell','-NoProfile','-Command',
        "if (Get-Process NorthstarLauncher -ErrorAction SilentlyContinue) { Write-Output 'active' }"],
        capture_output=True,text=True,check=True)
    if check.stdout.strip():raise RuntimeError('Close Northstar before installing the hotfix')
    profile=Path('D:/Games/Titanfall2/R2Northstar').resolve()
    if not (profile/'Northstar.dll').is_file():raise ValueError('Unexpected native profile')
    mods=profile/'mods';plans=[]
    for manifest in mods.glob('*/mod.json'):
        meta=json.loads(manifest.read_text(encoding='utf-8-sig'));name=meta.get('Name')
        if name not in MAPS:continue
        old,new=VERSIONS[name]
        if meta['Version'] not in (old,new):raise ValueError('Unexpected installed version: '+name)
        source=ROOT/'northstar'/name
        presentation=next((source/'paks').glob('*_presentation.rpak'))
        current=manifest.parent/'paks'/presentation.name
        baseline=Path('D:/Games/ApexToTitanfallWork/new-arena-ports/shared-map-ui/before')/name/presentation.name
        if digest(current) not in (digest(presentation),digest(baseline)):
            raise ValueError('Unknown installed loading pack: '+name)
        if manifest.parent.resolve().parent != mods.resolve():raise ValueError('Installed folder escaped profile')
        if any(n==name for n,_,_,_ in plans):raise ValueError('Duplicate installed map: '+name)
        plans.append((name,manifest.parent,meta,presentation))
    backup=profile/'.ui-atlas-hotfix-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    if not backup.resolve().is_relative_to(profile):raise ValueError('Backup escaped profile')
    backup.mkdir(parents=True,exist_ok=False)
    enabled_path=profile/'enabledmods.json';shutil.copy2(enabled_path,backup/'enabledmods.json')
    enabled=json.loads(enabled_path.read_text())
    shared=mods/'ApexMaps.UI'
    if shared.exists():
        if json.loads((shared/'mod.json').read_text())['Name']!='ApexMaps.UI':raise ValueError('Unowned UI folder')
        os.replace(shared,backup/'ApexMaps.UI')
    shutil.copytree(ROOT/'northstar/ApexMaps.UI',shared)
    enabled.setdefault('ApexMaps.UI',{})['0.1.0']=True
    records={}
    for name,target,meta,presentation in plans:
        kept=backup/target.name
        (kept/'paks').mkdir(parents=True)
        shutil.copy2(target/'mod.json',kept/'mod.json')
        shutil.copy2(target/'paks/rpak.json',kept/'paks/rpak.json')
        shutil.copy2(target/'paks'/presentation.name,kept/'paks'/presentation.name)
        temp=target/'paks'/(presentation.name+'.hotfix')
        shutil.copy2(presentation,temp)
        if digest(temp)!=digest(presentation):raise ValueError('Loading pack copy mismatch')
        os.replace(temp,target/'paks'/presentation.name)
        removed=[]
        for obsolete in (target/'paks').glob('*_minimap.rpak'):
            if obsolete.resolve().parent!=(target/'paks').resolve():raise ValueError('Obsolete pack escaped map folder')
            os.replace(obsolete,kept/'paks'/obsolete.name);removed.append(obsolete.name)
        scope(target/'paks',MAPS[name]);audit(target/'paks',MAPS[name])
        old,new=VERSIONS[name];meta['Version']=new
        temp=target/'mod.json.hotfix';temp.write_text(json.dumps(meta,indent=2)+'\n');os.replace(temp,target/'mod.json')
        preferences=enabled.get(name,{})
        active=preferences.get(old,preferences.get(new,True))
        enabled[name]={**{k:False for k in preferences},new:active}
        records[name]=dict(version=new,folder=target.name,removed_standalone_atlases=removed,
                           retained_backup=str(kept),enabled=active)
    temp=enabled_path.with_suffix('.hotfix.json');temp.write_text(json.dumps(enabled,indent=2)+'\n');os.replace(temp,enabled_path)
    (ROOT/'output/atlas-lifetime/installation.json').write_text(json.dumps(dict(maps=records,shared='ApexMaps.UI 0.1.0',
        backup=str(backup),geometry_collision_world_textures_untouched=True),indent=2))
    print('Updated existing map installs:',', '.join(records),'; shared UI enabled; backups retained',flush=True)


if __name__=='__main__':install()
