"""Local source ownership and material audit for the four reported defects."""
import json,sys,struct,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps
from read_vg_static import load
from stage_prop_geometry import rotation
OUT=ROOT/'output/composite';WORK=OUT/'local-repair';WORK.mkdir(exist_ok=True)
POINTS={'lamp':[-7.97897,2272.95,65.5334],'boxes':[-437.599,132.351,129.574],
        'wall':[-1917.1,631.305,192.031],'invisible':[-19.4512,1962.31,-58.5558]}
def main():
 s=json.loads((OUT/'scene.json').read_text());src=json.loads((OUT/'source-inventory.json').read_text());p=json.loads((OUT/'physics.json').read_text())
 included={r['index']:r for r in s['placements']};omitted={r['index']:r['reason'] for r in s['omitted']}
 a=np.load(OUT/'scene.npz');tri=a['triangles'];mi=a['material'];names=a['names'];a.close()
 l=read_lumps(OUT/'mp_arena_composite.bsp',(3,0x42,0x45));pos=np.frombuffer(l[3],'<f4').reshape(-1,3);w=np.frombuffer(l[0x42],'<u4');hs=list(struct.iter_unpack('<6h4i4f',l[0x45]));owner={};first=len(hs)-sum(r['headers'] for r in p['owners'])
 for r in p['owners']:
  for i in range(r['headers']):owner[first+i]=r['index']
  first+=r['headers']
 cols=[];own=[]
 for i,h in enumerate(hs):
  words=w[h[7]:h[7]+h[4]];v=words&1023;idx=h[6]+np.stack((v,v+(words>>10&127),v+(words>>17&127)),1);cols.append(pos[idx]);own.extend([owner.get(i,'world')]*len(words))
 col=np.concatenate(cols);own=np.array(own,dtype=object);lo=tri[:,:,:3].min(1);hi=tri[:,:,:3].max(1);clo=col.min(1);chi=col.max(1)
 result={}
 for label,point in POINTS.items():
  q=np.array(point);d=np.linalg.norm(np.maximum(np.maximum(clo-q,q-chi),0),axis=1);rd=np.linalg.norm(np.maximum(np.maximum(lo-q,q-hi),0),axis=1)
  result[label]={'point':point,'render':dict(collections.Counter(str(names[i]) for i in mi[rd<80])),
    'collision':dict(collections.Counter(str(i) for i in own[d<80])),
    'collision_nearest':[dict(owner=str(own[i]),distance=float(d[i]),triangle=col[i].tolist()) for i in np.argsort(d)[:12]]}
  props=sorted(src['props'],key=lambda r:np.linalg.norm(np.array(r['origin'])-q))[:14]
  result[label]['props']=[dict(r,status='included' if r['index'] in included else omitted.get(r['index'],'filtered'),lod=included.get(r['index'],{}).get('lod')) for r in props]
  print(label,'draw',result[label]['render'],'collision',result[label]['collision'])
  print('closest collision',result[label]['collision_nearest'][:2])
 paths=json.loads((OUT/'asset-audit.json').read_text())['model_paths'];models={}
 for index in (5093,4924,6370,6377,2573,619,632,81,76,82,83,2914,5287,5288):
  r=next(x for x in src['props'] if x['index']==index);folder=paths.get(r['model'])
  if not folder:continue
  f=Path(folder);lods=struct.unpack_from('<18Q',(f/(f.name+'.vg')).read_bytes(),16)[13];cs=[]
  for lod in range(min(lods,5)):
   secs,slots,skins=load(f,lod);t=np.concatenate([np.asarray(x,'<f4').reshape(-1,3,8) for x in secs]);p=t[:,:,:3]@np.array(rotation(r['angles'])).T*r['scale']+r['origin']
   cs.append(dict(lod=lod,triangles=len(t),bounds=[p.min((0,1)).tolist(),p.max((0,1)).tolist()],materials=skins[min(r['skin'],len(skins)-1)]))
  models[index]=dict(prop=r,folder=folder,status='included' if index in included else omitted.get(index,'filtered'),lods=cs)
  print(index,Path(r['model']).stem,models[index]['status'],cs)
 result['models']=models;(WORK/'audit.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
