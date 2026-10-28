"""Package the validated original five without rebuilding or changing runtime bytes."""
import hashlib
import json
import os
import zipfile

from prepare_anniversary_release import ROOT,OUT,BASE,digest,write
from package_player_mods import RELEASES

TAG='anniversary-2026-rc1'
DEST=ROOT/'output/releases'/TAG


def readme(name,version):
    title=RELEASES[name]['title'] if name in RELEASES else 'Shared map UI'
    intro=f'# {title} {version} — Titanfall 2 anniversary RC1\n\n'
    install='''Requires Northstar 1.31.14 or newer (1.31.14 tested). Close the game.
Move old copies of these maps and ApexMaps.UI outside the mods directory, then
extract the mod folder into `Titanfall2/R2Northstar/mods/`. Replace old folders;
do not merge them. Enable the mods and restart. Every player and the server need
matching versions. Install ApexMaps.UI once alongside the maps you want.

This is a release candidate. The runtime files are the accepted October beta
bytes, freshly tested together on Northstar 1.31.14; their mod versions are
unchanged. RC1 updates packaging and installation guidance. The harness, game
runtime, development tools, logs and source game archives are not included.

'''
    if name=='ApexMaps.UI':
        return intro+install+'''One atlas supplies loading artwork and minimaps. Version 0.2.1 also supports
Thermal Station and Thunderdome; those two maps are outside this five-map RC.
Keep only one enabled copy of this companion.
'''
    modes=f'''Tested pilot modes: Pilots vs Pilots (`ps`) and Free For All (`ffa`).
Launch from the console, for example:

```text
mp_gamemode ps
map {RELEASES[name]['map']}
```

'''
    limits='''Validation uses one local client. Multiplayer load, balance, dedicated servers
and AI navigation are not certified. These are visual/collision adaptations,
with omitted scenery and incomplete Apex shaders, effects and gameplay systems.
'''
    if name=='PhaseRunner':
        limits+='Phase Runner has experimental objective/Titan mode markers; their presence is not full mode certification.\n'
    if name=='ApexFiringRange':
        limits+='Training targets, weapon stations, bots and interactive Apex supply bins are not implemented.\n'
    if name=='ArenaOverflow':
        limits+='Overflow had intermittent spawn/load crashes on Northstar 1.31.13. Repeated 1.31.14 checks are reported in the release notes; a passing local sample does not establish the old failure\'s root cause.\n'
    return intro+install+modes+limits+'\nOriginal map assets belong to their respective creators. `screenshot.png` is a real in-game capture.\n'


def gates():
    structural=json.loads((OUT/'structural-validation.json').read_text())
    combined=json.loads((OUT/'combined-validation.json').read_text())
    modes=json.loads((OUT/'mode-validation.json').read_text())
    stress=json.loads((OUT/'overflow-stress.json').read_text())
    visual=json.loads((OUT/'visual-validation.json').read_text())
    mounted=json.loads((OUT/'mounted-runtime-validation.json').read_text())
    if not all(r.get('passed') for r in (structural,combined,modes)):raise ValueError('Incomplete validation')
    if not mounted.get('passed') or not mounted.get('all_runtime_files_including_scripts_and_localisation'):
        raise ValueError('Full mounted-file provenance is incomplete')
    if not stress.get('complete') or stress['count']<10:raise ValueError('Incomplete repeated-load checks')
    if not all(r.get('stock_and_converted_reload_passed') for r in stress['runs']):raise ValueError('Incomplete stress reload')
    for name in BASE:
        if not any(r['package']==name and r['mode']=='ffa' for r in modes['maps']):raise ValueError('Missing FFA check')
    if not visual.get('reviewed') or {r['package'] for r in visual['captures']}!=set(BASE):
        raise ValueError('Native overview review is incomplete')
    for row in visual['captures']:
        if digest(row['capture']['path'])!=row['capture']['sha256']:raise ValueError('Reviewed screenshot changed')
    return structural,combined,modes,stress


def package():
    gates()
    manifest=json.loads((OUT/'baseline-manifest.json').read_text())
    DEST.mkdir(parents=True,exist_ok=True)
    records=[]
    for name in (*BASE,'ApexMaps.UI'):
        cfg=manifest[name];source=OUT/'baseline'/name
        target=DEST/f"{name}-{cfg['version']}-Anniversary2026-RC1-Northstar.zip"
        expected={}
        for rel,sha in cfg['payloads'].items():
            if digest(source/rel)!=sha:raise ValueError('Runtime differs from validated baseline: '+name+'/'+rel)
            expected[name+'/'+rel]=sha
        text=readme(name,cfg['version']).encode('utf-8')
        expected[name+'/README.md']=hashlib.sha256(text).hexdigest()
        photo=source/'screenshot.png'
        if name!='ApexMaps.UI':expected[name+'/screenshot.png']=digest(photo)
        temporary=target.with_suffix('.zip.packaging')
        if not target.exists():
            print('Packaging anniversary RC:',name,flush=True)
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
                for rel in cfg['payloads']:z.write(source/rel,name+'/'+rel)
                z.writestr(name+'/README.md',text)
                if name!='ApexMaps.UI':z.write(photo,name+'/screenshot.png')
            candidate=temporary
        else:candidate=target
        with zipfile.ZipFile(candidate) as z:
            if len(z.namelist())!=len(expected) or set(z.namelist())!=set(expected):raise ValueError('Unexpected archive members')
            for member,sha in expected.items():
                h=hashlib.sha256()
                with z.open(member) as stream:
                    for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
                if h.hexdigest()!=sha:raise ValueError('Archive differs: '+member)
        if candidate==temporary:os.replace(temporary,target)
        records.append({'package':name,'version':cfg['version'],'file':target.name,'bytes':target.stat().st_size,
                        'sha256':digest(target),'runtime_sha256':cfg['payloads'],
                        'accepted_beta_zip_sha256':cfg['accepted_zip_sha256'],'verified_members':len(expected)})
        print('Verified anniversary archive:',name,flush=True)
    write(DEST/'release-manifest.json',{'tag':TAG,'runtime':'Northstar 1.31.14','runtime_bytes_unchanged':True,'packages':records})
    (DEST/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in records),encoding='utf-8')
    print('Anniversary release candidate packaged and verified',flush=True)


if __name__=='__main__':package()
