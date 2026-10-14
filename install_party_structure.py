"""Install only the verified existing Party Crasher mod, retaining rollback."""
import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

from new_arena_ports import ROOT, folder
from package_player_mods import digest, runtime_files
from map_pack_lifetime import audit, audit_shared


def install():
    proof=json.loads((ROOT/'docs/candidates/party-crasher/port-0.4.0/validation.json').read_text())
    if not all(proof[k] for k in ('both_teams_verified','postmatch_lobby','stock_map_reload','party_reload')):
        raise ValueError('Native validation missing')
    audit_shared()
    state=subprocess.run(['powershell','-NoProfile','-Command',
        "if(Get-Process NorthstarLauncher -ErrorAction SilentlyContinue){Write-Output 'active'}"],
        capture_output=True,text=True,check=True)
    if state.stdout.strip():raise ValueError('Close Northstar before replacing the mod')
    profile=Path('D:/Games/Titanfall2/R2Northstar').resolve()
    if not (profile/'Northstar.dll').is_file():raise ValueError('Unexpected native profile')
    mods=profile/'mods';source=ROOT/'northstar/ArenaPartyCrasher'
    paths=[p.parent for p in mods.glob('*/mod.json')
           if json.loads(p.read_text(encoding='utf-8-sig')).get('Name')=='ArenaPartyCrasher']
    if len(paths)!=1:raise ValueError('Expected exactly one existing Party Crasher installation')
    target=paths[0].resolve()
    if target.parent!=mods.resolve():raise ValueError('Installed path escaped profile')
    if json.loads((target/'mod.json').read_text())['Version']!='0.3.1':
        raise ValueError('Unexpected installed baseline')
    baseline=folder('party-crasher')/'before-0.4.0/player-mod'
    for name in ('mod/maps/mp_party_crasher.bsp','paks/party_crasher_world.rpak'):
        if digest(target/name)!=digest(baseline/name):raise ValueError('Installed baseline has unknown edits')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    stage=profile/'.party-structure-staging'/stamp/target.name
    backup=profile/'.party-structure-backups'/stamp
    for p in (stage,backup):
        if not p.resolve().is_relative_to(profile):raise ValueError('Installation path escaped profile')
        p.mkdir(parents=True,exist_ok=False)
    expected={}
    for p in runtime_files(source):
        relative=p.relative_to(source);destination=stage/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,destination);expected[relative.as_posix()]=digest(p)
        if digest(destination)!=expected[relative.as_posix()]:raise ValueError('Staged payload differs')
    audit(stage/'paks','mp_party_crasher')
    enabled_path=profile/'enabledmods.json'
    shutil.copy2(enabled_path,backup/'enabledmods.json')
    enabled=json.loads(enabled_path.read_text());preference=enabled.get('ArenaPartyCrasher',{})
    active=preference.get('0.3.1',True)
    enabled['ArenaPartyCrasher']={**{v:False for v in preference},'0.4.0':active}
    kept=backup/target.name
    os.replace(target,kept)
    try:
        os.replace(stage,target)
        temp=enabled_path.with_suffix('.party-update.json');temp.write_text(json.dumps(enabled,indent=2)+'\n')
        os.replace(temp,enabled_path)
    except Exception:
        if target.exists():os.replace(target,backup/(target.name+'-failed-candidate'))
        os.replace(kept,target);shutil.copy2(backup/'enabledmods.json',enabled_path)
        raise
    for relative,wanted in expected.items():
        if digest(target/relative)!=wanted:raise ValueError('Installed runtime differs')
    receipt=dict(version='0.4.0',installed=str(target),backup=str(kept),enabled=active,
                 runtime_sha256=expected,shared_ui_unchanged=True,other_maps_unchanged=True)
    (ROOT/'output/party-edge-roof/installation.json').write_text(json.dumps(receipt,indent=2))
    print('Installed Party Crasher 0.4.0; old mod and preferences retained at',backup,flush=True)


if __name__=='__main__':install()
