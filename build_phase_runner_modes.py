"""Add native gameplay entities without rebuilding the tested world/collision lumps."""
import json, os, shutil, struct, sys, collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'northstar/PhaseRunner'
if json.loads((BASE/'mod.json').read_text())['Version']!='1.0.0':
    BASE=ROOT/'output/installed-backups/PhaseRunner-1.0.0-before-gameplay'
STAGE=ROOT/'northstar/PhaseRunner.GameModes'
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.branches.shared import Entities
from audit_tree_grounding import vertical_surface, np
from repair_preview_index_padding import read_lumps
from build_phase_runner_catwalks import mesh_faces

def clone():
    for src in BASE.rglob('*'):
        if not src.is_file():continue
        dst=STAGE/src.relative_to(BASE);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():continue
        # Editable scripts/reports and the BSP must never share an inode with baseline.
        if src.suffix.lower() in ('.bsp','.nut','.json','.md','.txt'):shutil.copy2(src,dst)
        else:os.link(src,dst)

def build():
    clone()
    source=BASE/'mod/maps/mp_phase_runner.bsp'
    lumps=read_lumps(source,(3,0x49,0x4f,0x50,0x52))
    scene=np.concatenate([t for _,_,_,_,t in mesh_faces(lumps)])
    bounds=(scene[:,:,:2].min(1),scene[:,:,:2].max(1))
    def ground(x,y,ceiling=-700):
        z=vertical_surface(scene,(x,y),ceiling,bounds)
        if z is None:raise ValueError('No floor at '+str((x,y)))
        return [x,y,round(z+4,3)]
    def xyz(v):return ' '.join(str(x) for x in v)
    flags={'gamemode_'+m:'1' for m in ('tdm','at','ctf','cp','ffa','lts','fw','fd','lh')}
    rows=[];plan=[]
    native_path=ROOT/'logs/gameplay-spawn-probes.json'
    probes=json.loads(native_path.read_text()) if native_path.exists() else []
    used_starts=[]
    def safe_start(p):
        if not probes:return p
        candidates=[v['origin'] for v in probes if v['floor'] and v['pilot'] and abs(v['origin'][0]-p[0])<350 and abs(v['origin'][1]-p[1])<350
                    and all((v['origin'][0]-q[0])**2+(v['origin'][1]-q[1])**2>=96**2 for q in used_starts)]
        if not candidates:raise ValueError('No clear start candidate '+str(p))
        chosen=min(candidates,key=lambda v:(v[0]-p[0])**2+(v[1]-p[1])**2)
        used_starts.append(chosen);return chosen
    def entity(cls,pos,team=0,yaw=0,**extra):
        row=dict(classname=cls,origin=xyz(pos),angles=f'0 {yaw} 0',teamnumber=str(team),**flags)
        row.update(extra)
        row['targetname']=extra.get('targetname',f'phase_runner_{cls}_{len(rows)}')
        rows.append(row);plan.append(dict(classname=cls,origin=pos,team=team,yaw=yaw,targetname=row['targetname']))
    for team,sign in ((2,-1),(3,1)):
        yaw=0 if sign<0 else 180
        # Both rooms have an open central aisle; rows leave 96+ units between pilots.
        for x in (5900,6040,6180):
            for y in (-1200,-1360,-1520,-1680):
                entity('info_spawnpoint_human_start',safe_start(ground(110+sign*x,y,-750)),team,yaw)
        for x,y in ((5500,-1700),(5200,-2000),(4700,-2600),(4000,-3200),(3100,-4100),
                    (2100,-4500),(1100,-4500),(4400,-800),(3500,200),(2800,900),
                    (1800,1900),(800,2000),(5800,-900),(5100,-1200),(3900,-1800),
                    (2900,-2700),(1900,-3400),(800,-3200)):
            # Regular spawns are neutral: native frontline/enemy-visibility ratings
            # choose safe positions; start spawns and flags define team bases.
            entity('info_spawnpoint_human',ground(110+sign*x,y),0,yaw)
        for x,y in ((5200,-2200),(5200,-1944),(5200,-2456),(5328,-2200),(1200,-3600),(1200,-3472)):
            p=ground(110+sign*x,y)
            if probes:
                candidates=[v['origin'] for v in probes if v['floor'] and v['titan'] and abs(v['origin'][0]-p[0])<350 and abs(v['origin'][1]-p[1])<350]
                if not candidates:raise ValueError('No clear Titan candidate '+str(p))
                p=min(candidates,key=lambda v:(v[0]-p[0])**2+(v[1]-p[1])**2)
            entity('info_spawnpoint_titan',p,0,yaw)
            if x==5200:entity('info_spawnpoint_titan_start',p,team,yaw)
        entity('info_spawnpoint_flag',ground(110+sign*5980,-1420,-750),team,yaw)
    for x,y in ((110,-3200),(-650,-4000),(870,-4000),(-650,600),(870,600),(110,1800)):
        entity('info_spawnpoint_human',ground(x,y),0,90)
    objectives=[]
    for group,x,y in (('A',-4450,-1700),('B',110,-2700),('C',4670,-1700)):
        p=ground(x,y);trigger=f'phase_runner_capture_{group.lower()}'
        entity('info_hardpoint',p,0,90,hardpointGroup=group,triggerTarget=trigger,
               model='models/robots/mobile_hardpoint/mobile_hardpoint.mdl',hardpointFrontlineYaw='0',
               hardpointFrontlineOverride='1',gamemode_at='0',gamemode_lh='0',targetname=f'phase_runner_hardpoint_{group.lower()}')
        row=dict(classname='trigger_capture_point',origin=xyz([p[0],p[1],p[2]+96]),targetname=trigger,
                 spawnflags='3',StartDisabled='0',triggerFilterUseNew='1',triggerFilterPlayer='all',
                 triggerFilterTeamIMC='1',triggerFilterTeamMilitia='1',triggerFilterTeamNeutral='0',
                 triggerFilterTeamOther='0',triggerFilterPhaseShift='nonphaseshift',triggerFilterNonCharacter='0',
                 triggerFilterNpc='all',triggerFilterNpcOwnedByPlayer='any',triggerFilterNpcFlip='0',
                 triggerFilterTeamBeast='0',triggerNearbyRadius='0')
        for i,(n,d) in enumerate((('-1 0 0',320),('1 0 0',320),('0 -1 0',320),('0 1 0',320),('0 0 -1',112),('0 0 1',112))):
            row[f'*trigger_brush_0_plane_{i}']=f'{n} {d}'
        row['*trigger_bounds_mins']='-320 -320 -112';row['*trigger_bounds_maxs']='320 320 112'
        rows.append(row);objectives.append(dict(group=group,origin=p,trigger=trigger))
    with source.open('rb') as f:
        header=f.read(2064);offset,length,version,fourcc=struct.unpack_from('<4I',header,16)
        f.seek(offset);original=Entities.from_bytes(f.read(length))
    for e in original:
        if e.get('classname')=='info_player_start':e['origin']=xyz(plan[0]['origin']);e['angles']='0 0 0'
    payload=Entities([*original,*rows]).as_bytes()
    dst=STAGE/'mod/maps/mp_phase_runner.bsp'
    shutil.copyfile(source,dst)
    with dst.open('r+b') as f:
        f.seek(0,2);end=f.tell();pad=(-end)%16;f.write(b'\0'*pad);new_offset=f.tell();f.write(payload)
        f.seek(16);f.write(struct.pack('<4I',new_offset,len(payload),version,fourcc))
    report=dict(version='1.1.0',map='mp_phase_runner',teams={'2':'IMC west building','3':'Militia east building'},
                added_entity_counts=dict(collections.Counter(r['classname'] for r in rows)),spawns=plan,objectives=objectives,
                fastball_buddies=[dict(team=2,origin=ground(-5090,-2200),yaw=0),dict(team=3,origin=ground(5310,-2200),yaw=180)],
                fastball_panels=[dict(origin=[p['origin'][0],p['origin'][1]+220,p['origin'][2]],yaw=90) for p in objectives],
                geometry_changed=False,collision_changed=False,entity_lump_append_bytes=len(payload),
                limitations=['Attrition AI requires a separately authored valid AIN/navigation graph.','Multiplayer balance requires matches with multiple human players.'])
    (STAGE/'gameplay-layout.json').write_text(json.dumps(report,indent=2))
    mod=json.loads((BASE/'mod.json').read_text());mod['Version']='1.1.0'
    mod['Description']='Phase Runner: opposing building bases, native multi-mode spawns, CTF flags, hardpoints and Fastball.'
    mod['Scripts'].append(dict(Path='_phase_runner_modes.nut',RunOn='SERVER && MP'))
    (STAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    script=STAGE/'mod/scripts/vscripts/_phase_runner_preview.nut'
    s=(BASE/'mod/scripts/vscripts/_phase_runner_preview.nut').read_text();a=s.index('\tforeach ( int team in [ TEAM_IMC, TEAM_MILITIA ] )');b=s.index('\tif ( GetConVarBool',a)
    s=s[:a]+'\tPhaseRunnerModes_Init()\n'+s[b:]
    s=s.replace('SetTeam( player, TEAM_IMC )','SetTeam( player, GetPlayerArrayOfTeam( TEAM_IMC ).len() <= GetPlayerArrayOfTeam( TEAM_MILITIA ).len() ? TEAM_IMC : TEAM_MILITIA )')
    script.write_text(s)
    template=(ROOT/'phase_runner_modes.nut').read_text()
    vec=lambda p:'< '+', '.join(str(v) for v in p)+' >'
    panels=', '.join(vec(p['origin'])+', < 0, 90, 0 >' for p in report['fastball_panels'])
    for i,p in enumerate(report['fastball_buddies']):template=template.replace(f'BUDDY_{i}',vec(p['origin']))
    template=template.replace('PANEL_POSITIONS',panels)
    (STAGE/'mod/scripts/vscripts/_phase_runner_modes.nut').write_text(template)
    print(json.dumps({k:v for k,v in report.items() if k not in ('spawns','objectives')},indent=2))
if __name__=='__main__':build()
