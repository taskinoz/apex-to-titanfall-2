"""Native views and floor/hull-verified spawns for the approved candidates."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from new_arena_ports import CONFIG, ROOT, WORK, folder

sys.path.insert(0,str(ROOT/'tools/lighting-python'))
sys.path.insert(0,str(ROOT/'test-harness'))
import numpy as np
from harness import Controller
from compact_preview_bsp import compact
from repair_environment_lighting import entities, text_entities


def mounted_bsp(c,ident):
    name=CONFIG[ident]['target']+'.bsp'
    root=Path(c.session['game'])/c.session['profile']/'mods'
    paths=list(root.glob('*/mod/maps/'+name))
    if len(paths)!=1:raise RuntimeError('Expected exactly one mounted candidate BSP')
    actual=hashlib.sha256(paths[0].read_bytes()).hexdigest()
    wanted=hashlib.sha256((folder(ident)/name).read_bytes()).hexdigest()
    if actual!=wanted:raise RuntimeError('Mounted candidate differs from build; restage before validation')
    return actual


def mounted_material_pack(c,ident):
    name=ident.replace('-','_')+'_world.rpak';root=Path(c.session['game'])/c.session['profile']/'mods'
    paths=list(root.glob('*/paks/'+name))
    if len(paths)!=1:raise RuntimeError('Expected one mounted material pack')
    actual=hashlib.sha256(paths[0].read_bytes()).hexdigest()
    wanted=hashlib.sha256((folder(ident)/'materials/build'/name).read_bytes()).hexdigest()
    if actual!=wanted:raise RuntimeError('Mounted material pack differs from build')
    return actual


def refine_spawns(ident):
    c=Controller();name=CONFIG[ident]['target'];state=c.request('/status')
    if state.get('contexts',{}).get('client',{}).get('level')!=name:
        c.load(name,'ps',300);time.sleep(20)
    c.wait_map(name,60)
    scene=json.loads((folder(ident)/'scene.json').read_text());offset=np.asarray(CONFIG[ident]['offset'])
    screens=[np.asarray([float(v) for v in e['origin'].split()])+offset for e in scene['source_entities']
             if e.get('classname')=='info_target' and e.get('script_name')=='apex_screen']
    if screens and ident!='firing-range':
        screens=np.asarray(screens)
        start=next((e for e in scene['source_entities'] if e.get('classname')=='info_player_start'),None)
        reference=float(start['origin'].split()[2])+offset[2]+200 if start else float(np.median(screens[:,2]))
        height=screens[int(np.abs(screens[:,2]-reference).argmin()),2]
        screens=screens[np.abs(screens[:,2]-height)<128]
        mid=float(np.median(screens[:,0]));groups=[screens[screens[:,0]<=mid],screens[screens[:,0]>mid]]
        centers=[g.mean(0)-[0,0,170] for g in groups if len(g)]
    else:
        defaults={'overflow':[[-3300,-4200,400],[4650,-4200,400]],
                  'party-crasher':[[-3800,-1500,800],[3400,3000,800]],
                  'firing-range':[[-1500,-2500,-440],[2500,-2500,-520]]}
        centers=[np.asarray(p) for p in defaults[ident]]
    if len(centers)!=2:raise ValueError('Two opposing spawn regions must be identified')
    tests=[];selected=[]
    for center in sorted(centers,key=lambda p:p[0]):
        choices=[(center+[x,y,z]).tolist() for x,y,z in
                 ((x,y,z) for z in (0,-128,128) for x in (-320,-160,0,160,320) for y in (-320,-160,0,160,320))]
        results=c.command('server','spawn_probe',points=choices,timeout=50)['data']
        accepted=[r for r in results if r['floor'] and r['pilot']]
        unique={tuple(round(v,2) for v in r['origin']):r for r in accepted}
        accepted=sorted(unique.values(),key=lambda r:float(np.linalg.norm(np.asarray(r['origin'])-center)))
        group=[]
        for r in accepted:
            if all(np.linalg.norm(np.asarray(r['origin'])-q['origin'])>110 for q in group):group.append(r)
            if len(group)==6:break
        tests.append(dict(center=center.tolist(),probes=results,accepted=group))
        if len(group)<3:raise RuntimeError('Too few supported/clear native spawn candidates near '+str(center))
        selected.append(group)
    out=folder(ident);source=out/(name+'.bsp');rows=[e for e in entities(source)
        if not e.get('classname','').startswith('info_spawnpoint') and e.get('classname')!='info_player_start']
    for team,group in zip((2,3),selected):
        for r in group:
            angle='0 0 0' if team==2 else '0 180 0';origin=' '.join(map(str,r['origin']))
            for cls,number in (('info_spawnpoint_human_start',team),('info_spawnpoint_human',0)):
                rows.append(dict(classname=cls,origin=origin,angles=angle,teamnumber=str(number),
                                 gamemode_tdm='1',gamemode_ps='1',gamemode_ffa='1'))
    rows.append(dict(classname='info_player_start',origin=' '.join(map(str,selected[0][0]['origin'])),angles='0 0 0'))
    target=source.with_suffix('.spawns.bsp');compact(source,target,{0:text_entities(rows)});os.replace(target,source)
    (out/'native-spawn-candidates.json').write_text(json.dumps(dict(map=name,regions=tests,
        policy='Six clear supported pilot starts per team, neutral respawns; native live-marker recheck pending'),indent=2))
    print(ident,'supported starts',[len(g) for g in selected],flush=True)


def capture(ident):
    c=Controller();cfg=CONFIG[ident];state=c.wait_map(cfg['target'],60);time.sleep(10)
    sha=mounted_bsp(c,ident)
    out=folder(ident)/'runtime';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'docs/candidates'/ident
    route=source/('training-captures.json' if ident=='firing-range' else 'captures.json')
    receipts=json.loads(route.read_text());records=[]
    for i,r in enumerate(receipts):
        camera=r['camera'];position=(np.asarray(camera['origin'])+cfg['offset']).tolist()
        c.camera(position,camera['angles'],camera['fov'],3)
        shot=c.capture(ident+'-native-'+str(i));shutil.copy2(shot['path'],out/('view-'+str(i)+'.png'))
        records.append(dict(source=r,northstar=shot))
        print(ident,'native view',i,shot['path'],flush=True)
    c.command('client','camera_clear');mode=c.command('server','mode_check')['data']
    if {p['team'] for p in mode['liveSpawns'] if p['classname']=='info_spawnpoint_human_start'}!={2,3}:
        raise RuntimeError('Both native team start sets must be present')
    if not all(p['clear'] and p['supported'] for p in mode['liveSpawns']):
        raise RuntimeError('Native live spawn marker is obstructed or unsupported')
    teams=[c.command('server','respawn',team=team) for team in (2,3)]
    logs=c.export_logs()
    if logs['script_errors'] or logs['native_crashes']:raise RuntimeError('Native log errors during candidate capture')
    (out/'captures.json').write_text(json.dumps(dict(map=cfg['target'],views=records,mode=mode,teams=teams,logs=logs,
        bsp_sha256=sha,material_pack_sha256=mounted_material_pack(c,ident),mounted_payload_verified=True),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['spawns','capture']);p.add_argument('map',choices=CONFIG)
    a=p.parse_args();dict(spawns=refine_spawns,capture=capture)[a.action](a.map)
