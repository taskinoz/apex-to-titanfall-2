"""Stage the original five immutable beta downloads for anniversary validation."""
import hashlib
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output/anniversary-2026'
BASE=('PhaseRunner','ArenaComposite','ApexFiringRange','ArenaPartyCrasher','ArenaOverflow')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.writing')
    temporary.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def stage():
    from package_player_mods import RELEASES
    manifest=json.loads((ROOT/'output/releases/maps-beta-2026-10-25/release-manifest.json').read_text())
    rows={r['checks']['mod']:r for r in manifest['packages']}
    results={}
    for name in (*BASE,'ApexMaps.UI'):
        row=rows[name]
        source=ROOT/'output/releases/maps-beta-2026-10-25'/row['name']
        if digest(source)!=row['sha256']:raise ValueError('Accepted ZIP changed: '+name)
        target=OUT/'baseline'/name
        receipt=target/'anniversary-stage.json'
        if not receipt.exists():
            if target.exists():raise ValueError('Incomplete candidate needs review: '+name)
            target.mkdir(parents=True)
            with zipfile.ZipFile(source) as z:
                for item in z.infolist():
                    path=PurePosixPath(item.filename)
                    if path.parts[0]!=name or '..' in path.parts or '\\' in item.filename or ':' in item.filename:
                        raise ValueError('Unsafe archive member')
                    if item.is_dir():continue
                    dest=target.joinpath(*path.parts[1:])
                    if not dest.resolve().is_relative_to(target.resolve()):raise ValueError('Archive escaped candidate')
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(item) as src,dest.open('xb') as dst:
                        for b in iter(lambda:src.read(8*1024*1024),b''):dst.write(b)
            write(receipt,{'archive_sha256':row['sha256'],'version':row['checks']['version']})
        elif json.loads(receipt.read_text())['archive_sha256']!=row['sha256']:
            raise ValueError('Wrong staged provenance')
        payloads={}
        with zipfile.ZipFile(source) as z:
            for item in z.infolist():
                rel=PurePosixPath(item.filename).relative_to(name).as_posix()
                if item.is_dir() or not (rel=='mod.json' or rel.startswith(('mod/','paks/'))):continue
                h=hashlib.sha256()
                with z.open(item) as stream:
                    for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
                sha=h.hexdigest()
                if digest(target/rel)!=sha:raise ValueError('Staged bytes differ from immutable ZIP: '+name+'/'+rel)
                payloads[rel]=sha
        results[name]={'version':row['checks']['version'],'accepted_zip_sha256':row['sha256'],
                       'map':RELEASES[name]['map'] if name in RELEASES else None,'payloads':payloads}
        print('Staged accepted package:',name,row['checks']['version'],flush=True)
    write(OUT/'baseline-manifest.json',results)


def audit():
    import struct
    from audit_world_draw_budget import enforce_camera_bypass_budget
    from repair_preview_index_padding import read_lumps,validate_index_padding
    from preview_visibility import validate_visibility
    from map_pack_lifetime import audit as audit_paks
    from extract_native_material import NativePak
    manifest=json.loads((OUT/'baseline-manifest.json').read_text())
    results={}
    for name in BASE:
        source=OUT/'baseline'/name
        cfg=manifest[name]
        for rel,sha in cfg['payloads'].items():
            if digest(source/rel)!=sha:raise ValueError('Staged runtime changed: '+name+'/'+rel)
        bsp=source/'mod/maps'/(cfg['map']+'.bsp')
        with bsp.open('rb') as f:
            if f.read(8)!=b'rBSP'+struct.pack('<I',37):raise ValueError('Unexpected BSP version')
        lumps=read_lumps(bsp,(0x4f,0x50,0x51,0x52,0x77,0x78,0x79))
        padding=validate_index_padding(lumps[0x50],lumps[0x4f],lumps[0x52])
        visibility=validate_visibility(lumps[0x77],lumps[0x78],lumps[0x79],lumps[0x51])
        budget=enforce_camera_bypass_budget(bsp)
        budget.pop('path',None)
        results[name]={'version':cfg['version'],'map':cfg['map'],'runtime_hashes_match':True,
                       'index_padding':padding,'visibility':visibility,'budget':budget,
                       'pak_ordering':audit_paks(source/'paks',cfg['map'])}
        print('Staged structure passed:',name,flush=True)
    shared=OUT/'baseline/ApexMaps.UI'
    for rel,sha in manifest['ApexMaps.UI']['payloads'].items():
        if digest(shared/rel)!=sha:raise ValueError('Shared runtime changed')
    config=json.loads((shared/'paks/rpak.json').read_text())
    if config!={'Postload':{'apex_maps_ui.rpak':'common.rpak'}}:raise ValueError('Shared atlas ordering changed')
    assets=NativePak(shared/'paks/apex_maps_ui.rpak').assets
    if sorted(a['type'] for a in assets)!=['txtr','uimg']:raise ValueError('Shared UI must own exactly one atlas')
    write(OUT/'structural-validation.json',{'passed':True,'maps':results,'custom_ui_atlases':1,
                                         'shared_ui_version':manifest['ApexMaps.UI']['version']})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['stage','audit'],nargs='?',default='stage')
    args=parser.parse_args()
    stage() if args.action=='stage' else audit()
