"""Recover source-positioned advertisements and low-cost light fixtures."""
import collections,json,struct
from pathlib import Path
from new_arena_ports import ROOT,WORK,folder,CONFIG
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
from recover_composite_details import collision
import recover_composite_details as recovery
import numpy as np


def build():
    out=folder('party-crasher');work=out/'signage-recovery';work.mkdir(exist_ok=True)
    if (work/'result.json').exists():raise ValueError('Signage already recovered')
    scene=json.loads((out/'scene.json').read_text());index=asset_index('party-crasher')
    wanted=('arenas_big_screen_01','citymodern_sign_a','party_crashers_pillar_signage','olympus_highrise_sign_',
            'ac_genki_market_sign_big_01','citymodern_light_on_01','olympus_can_light_short','interior_can_light_on')
    candidates=[p for p in scene['omitted'] if any(s in p['model'] for s in wanted)]
    candidates.sort(key=lambda p:(not any(s in p['model'] for s in ('sign','screen')),p['index']))
    parts=[];cols=[];selected=[];skipped=[];used=0
    for p in candidates:
        try:
            path=index[Path(p['model']).stem.lower()]
            levels=struct.unpack_from('<18Q',(path/(path.name+'.vg')).read_bytes(),16)[13]
            lod=min(3,levels-1);raw,slots,skins=load(path,lod,True)
            raw=[np.asarray(s,'f4').reshape(-1,3,12) for s in raw];skin=skins[min(p['skin'],len(skins)-1)]
            local=[];matrix=np.asarray(rotation(p['angles']))
            for sec,slot in zip(raw,slots):
                name=skin[slot]
                if not len(sec) or any(s in name.lower() for s in ('godray','ambient_occlusion','atmosphere','start_barrier')):continue
                if not (out/'legion/exported_files/materials'/name/(name+'_albedoTexture.dds')).exists():
                    raise ValueError('Source texture unavailable: '+name)
                t=sec.copy();t[:,:,:3]=sec[:,:,:3]@matrix.T*p['scale']+p['origin'];t[:,:,3:6]=sec[:,:,3:6]@matrix.T
                t[:,:,7]=1-sec[:,:,7];t[:,:,11]=255;local.append((name,t))
            n=sum(len(t) for name,t in local)
            if not n:raise ValueError('No supported source surface')
            if used+n>30000:raise ValueError('30,000 triangle recovery allowance')
            row=dict(p,folder=str(path),lod=lod,triangles=n,recovery='Original advertisement/fixture, authored LOD and exact source transform')
            col,method=collision(row,raw)
            row.update(collision_triangles=len(col),collision_recovery=method)
            selected.append(row);parts.extend(local);cols.append(col);used+=n
        except (ValueError,KeyError,OSError,struct.error) as e:
            skipped.append(dict(index=p['index'],model=p['model'],reason=str(e)))
    if not selected:raise ValueError('No recovered signage')
    names=list(dict.fromkeys(n for n,t in parts));tri=np.concatenate([t for n,t in parts]);mi=np.concatenate([np.full(len(t),names.index(n),'i4') for n,t in parts])
    np.savez(work/'addition.npz',triangles=tri,material=mi,names=names,collision=np.concatenate(cols))
    plan=dict(version='0.3.0',added_props=len(selected),added_triangles=used,placements=selected,skipped=skipped,
        policy='Source signs first, then small fixtures; <=30,000 triangles, no dynamic entities or guessed colliders')
    (work/'plan.json').write_text(json.dumps(plan,indent=2))
    for i,n in enumerate(names):scene['materials'][n]=scene['materials'].get(n,0)+int((mi==i).sum())
    (out/'scene.json').write_text(json.dumps(scene,indent=2))
    from build_new_arena_ports import materials
    from finish_new_arena_materials import build as finish
    materials('party-crasher');finish('party-crasher')
    recovery.OUT=out;recovery.WORK=work;recovery.MAP=out/'mp_party_crasher.bsp';recovery.BACKUP=out/'before-0.3.0'
    direction=-np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
    recovery.append(out,.95,str(WORK/'tools/bake_arena_environment.exe'),direction.tolist())
    print('Recovered',len(selected),'placements',used,'triangles',dict(collections.Counter(Path(p['model']).stem for p in selected)),flush=True)


if __name__=='__main__':build()
