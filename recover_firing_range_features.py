"""Restore authored supply bins and the stripless 3D-sky water section."""
import json,sys
from pathlib import Path
from new_arena_ports import CONFIG,ROOT,WORK,folder
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
import recover_composite_details as recovery

def clipped(vertices,low,high):
 polygon=list(vertices)
 for axis in range(3):
  for plane,sign in ((low[axis],1),(high[axis],-1)):
   old=polygon;polygon=[]
   if not old:break
   for a,b in zip(old,old[1:]+old[:1]):
    da=(a[axis]-plane)*sign;db=(b[axis]-plane)*sign
    if da>=0:polygon.append(a)
    if (da>=0)!=(db>=0):polygon.append(a+(b-a)*(da/(da-db)))
 return [[polygon[0],polygon[i],polygon[i+1]] for i in range(1,len(polygon)-1)]

def build():
 out=folder('firing-range');work=out/'source-feature-recovery';work.mkdir(exist_ok=True)
 if (work/'result.json').exists():raise ValueError('Already recovered')
 scene=json.loads((out/'scene.json').read_text());inventory=json.loads((out/'source-inventory.json').read_text())
 ix=asset_index('firing-range');sections=[];placements=[];collision=[]
 source=[(i,e) for i,e in enumerate(scene['source_entities']) if e.get('model','').endswith('/loot_bin_01_static.rmdl')]
 # Weapon-lane bins retain author LOD2; remote supply bins use author LOD3.
 for i,e in source:
  pos=np.asarray(list(map(float,e['origin'].split())))+CONFIG['firing-range']['offset']
  lod=2 if -1300<=pos[0]<=-1000 and -1500<=pos[1]<=1500 else 3
  raw,slots,skins=load(ix['loot_bin_01_static'],lod,True);raw=[np.asarray(s,'f4').reshape(-1,3,12) for s in raw]
  angles=list(map(float,e.get('angles','0 0 0').split()));matrix=np.asarray(rotation(angles));count=0
  for sec,slot in zip(raw,slots):
   name=skins[0][slot]
   if 'shimmer' in name:continue # interactive loot highlighting is not a physical crate surface
   t=sec.copy();t[:,:,:3]=sec[:,:,:3]@matrix.T+pos;t[:,:,3:6]=sec[:,:,3:6]@matrix.T;t[:,:,7]=1-sec[:,:,7];t[:,:,11]=255
   sections.append((name,t));count+=len(t)
  row=dict(index=100000+i,source_entity=i,source_entity_kind='dynamic-supply-bin',model=e['model'],origin=pos.tolist(),
      original_apex_origin=list(map(float,e['origin'].split())),angles=angles,scale=1,skin=0,solid=6,folder=str(ix['loot_bin_01_static']),lod=lod,triangles=count)
  col,method=recovery.collision(row,raw);collision.append(col);row.update(collision_triangles=len(col),collision_recovery=method);placements.append(row)
 vista=next(p for p in inventory['props'] if p['model'].endswith('/canyonlands_hu_se.rmdl'))
 raw,slots,skins=load(ix['canyonlands_hu_se'],0,True);matrix=np.asarray(rotation(vista['angles']));water=[]
 for sec,slot in zip(raw,slots):
  if skins[0][slot]!='canyonlands_river_water_03_skybox':continue
  t=np.asarray(sec,'f4').copy();t[:,:,:3]=t[:,:,:3]@matrix.T*1000;t[:,:,3:6]=t[:,:,3:6]@matrix.T;t[:,:,7]=1-t[:,:,7];t[:,:,11]=255
  # Reanchor the separate sky vista in the recentered native viewing domain.
  # Its water is visual background, not a solid ocean platform.
  # Cover the photographic sky sphere's horizon. A smaller rectangle ends
  # before the sphere and exposes a visible square edge in the ocean.
  for tri in t:water.extend(clipped(tri,[-26000,-26000,-5000],[26000,26000,1000]))
 water=np.asarray(water,'f4')
 # The separate sky pass has no gameplay collision height. Keep its native
 # proxy below the weapon-lane floors rather than flooding the recentered map.
 water[:,:,2]-=water[:,:,2].max()+1600
 sections.append(('d_skybox_water_01',water))
 placements.append(dict(vista,index=5368,source_entity_kind='sky-water-backdrop',folder=str(ix['canyonlands_hu_se']),lod=0,
   triangles=len(water),solid=0,collision_triangles=0,collision_recovery='Non-solid 3D-sky water',
   recovery='Source water topology, sky scale 1000 and yaw; reanchored/clipped backdrop with adapted source sky-water material'))
 names=list(dict.fromkeys(n for n,t in sections));triangles=np.concatenate([t for n,t in sections]);mi=np.concatenate([np.full(len(t),names.index(n),'i4') for n,t in sections])
 np.savez(work/'addition.npz',triangles=triangles,material=mi,names=names,collision=np.concatenate(collision))
 plan=dict(version='0.2.0',added_props=len(placements),added_triangles=len(triangles),placements=placements,
    water_triangles=len(water),supply_bins=len(source),water_adaptation='Separate 3D sky reanchored; static native water surface, no original wave shader')
 (work/'plan.json').write_text(json.dumps(plan,indent=2))
 for n in names:scene['materials'][n]=scene['materials'].get(n,0)+int((mi==names.index(n)).sum())
 (out/'scene.json').write_text(json.dumps(scene,indent=2))
 from build_new_arena_ports import materials
 from finish_new_arena_materials import build as finish
 materials('firing-range');finish('firing-range')
 recovery.OUT=out;recovery.WORK=work;recovery.MAP=out/(CONFIG['firing-range']['target']+'.bsp');recovery.BACKUP=out/'before-0.2.0'
 direction=-np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
 recovery.append(out,.95,str(WORK/'tools/bake_arena_environment.exe'),direction.tolist())
 from light_new_arena_ports import glow
 mapping=out/'materials/mapping.json';m=json.loads(mapping.read_text());m['materials']['d_skybox_water_01']['static_glow_ambient']=[.28,.47,.8];mapping.write_text(json.dumps(m,indent=2));glow('firing-range')
 from build_preview_stbsp import build as stbsp
 stbsp(out,out/'materials',CONFIG['firing-range']['target'],'firing_range_world')
 print('Recovered supply bins',len(source),'water triangles',len(water),flush=True)

if __name__=='__main__':build()
