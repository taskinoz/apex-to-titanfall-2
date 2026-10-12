"""Trace reported Drop-Off locations to source placements and collision owners."""
import collections,json,re,sys,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from repair_environment_lighting import entities
from repair_preview_index_padding import read_lumps
POINTS={
 'floating':[67.8318,2236.06,17.9144], 'north_barrier':[11.6296,5624.97,16.0313],
 'east_platform':[2320.61,6450.51,1251.18], 'west_platform':[-1898.16,6628.04,1117.08],
 'missing_props':[-1456.67,196.368,192.031], 'east_zfight':[3613.08,2529.54,129.175],
 'invisible_wall':[1614.18,2690.04,-145.855], 'east_stairs':[881.54,2884.91,131.904],
 'west_stairs':[-850.84,2899.38,117.284], 'transparent_1':[-2624.85,3336.14,287.028],
 'transparent_2':[-1564.61,3731.89,286.029], 'invisible_stairs':[-1264.16,4943.96,11.5513],
 'window':[65.5109,3634.83,416.745]}

def audit():
 out=ROOT/'output/composite';scene=json.loads((out/'scene.json').read_text());src=json.loads((out/'source-inventory.json').read_text());phys=json.loads((out/'physics.json').read_text())
 included={p['index']:p for p in scene['placements']};omitted={p['index']:p['reason'] for p in scene['omitted']}
 raw=np.load(out/'scene.npz');tri=raw['triangles'][:,:,:3];names=list(raw['names']);mi=raw['material'];lo,hi=tri.min(1),tri.max(1)
 lumps=read_lumps(out/'mp_arena_composite.bsp',(3,0x42,0x45,0x5c));pos=np.frombuffer(lumps[3],'<f4').reshape(-1,3);word=np.frombuffer(lumps[0x42],'<u4');col=[];owners=[]
 cursor=0;header_owner={}
 first=len(lumps[0x45])//48-sum(p['headers'] for p in phys['owners'])
 for owner in phys['owners']:
  for i in range(owner['headers']):header_owner[first+i]=owner['index']
  first+=owner['headers']
 for i,h in enumerate(struct.iter_unpack('<6h4i4f',lumps[0x45])):
  w=word[h[7]:h[7]+h[4]];a=w&1023;ix=h[6]+np.stack((a,a+(w>>10&127),a+(w>>17&127)),axis=1);col.append(pos[ix]);owners.extend([header_owner.get(i,'world')]*len(w))
 col=np.concatenate(col);clo,chi=col.min(1),col.max(1);owners=np.array(owners,dtype=object)
 origins=np.array([p['origin'] for p in src['props']]);records={}
 for label,point in POINTS.items():
  p=np.array(point);near=np.argsort(np.linalg.norm(origins-p,axis=1))[:18]
  placements=[dict(src['props'][i],distance=round(float(np.linalg.norm(origins[i]-p)),2),status='included' if src['props'][i]['index'] in included else omitted.get(src['props'][i]['index'],'filtered'),lod=included.get(src['props'][i]['index'],{}).get('lod')) for i in near]
  render=np.linalg.norm(np.maximum(np.maximum(lo-p,p-hi),0),axis=1)<80
  collision=np.linalg.norm(np.maximum(np.maximum(clo-p,p-chi),0),axis=1)<80
  records[label]=dict(point=point,placements=placements,render_materials=dict(collections.Counter(names[i] for i in mi[render])),collision_owners=dict(collections.Counter(str(i) for i in owners[collision])))
 (out/'reported-issues.json').write_text(json.dumps(records,indent=2))
 for label,row in records.items():
  print(label,row['point']);print(' nearest',[(p['index'],Path(p['model']).stem,p['distance'],p['status'],p['lod']) for p in row['placements'][:8]]);print(' draw',row['render_materials']);print(' collision',row['collision_owners'])
 volume={}
 from bsp_tool.branches.shared import Entities
 for name,path in [('phase',ROOT/'inputs/extracted-server/maps/mp_rr_arena_phase_runner_script.ent'),('dropoff',ROOT/'inputs/composite/server/maps/mp_rr_arena_composite_script.ent')]:
  raw=path.read_bytes();rows=Entities.from_bytes(raw[raw.index(b'{'):]);volume[name]=[e for e in rows if e.get('classname') in ('trigger_out_of_bounds','trigger_hurt','zipline','zipline_end','prop_door')]
  print(name,'entities',dict(collections.Counter(e['classname'] for e in volume[name])));print('samples',volume[name][:2])
 (out/'source-gameplay-volumes.json').write_text(json.dumps(volume,indent=2))
 logs=Path('D:/Games/Titanfall2/R2Northstar/logs')
 for log in sorted(logs.glob('*.txt'),key=lambda p:p.stat().st_mtime)[-3:]:
  text=log.read_text(encoding='utf-8-sig',errors='replace');lines=[l for l in text.splitlines() if re.search(r'crash|exception|assert|SCRIPT ERROR|COMPILE ERROR|LevelShutdown|LevelLoadingStarted',l,re.I) and 'Command line' not in l]
  print('log',log.name);print('\n'.join(lines[-25:]))

if __name__=='__main__':audit()
