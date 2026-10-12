"""Inspect native directional metadata and rendered mesh bounds."""
import collections,json,struct
from pathlib import Path
import numpy as np
from repair_preview_index_padding import read_lumps
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'
def audit():
 out={}
 for label,path in [('preview',P/'preview-aligned/mp_phase_runner_preview.bsp'),('homestead',ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp'),('colony',ROOT/'inputs/titanfall2-colony/maps/mp_colony02.bsp')]:
  l=read_lumps(path,(2,3,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52));pts=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);pi=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('rest','V40')]))['pi'];indices=np.frombuffer(l[0x4f],dtype='<u2');samples=[];bad=[];misc=collections.Counter()
  for mi in range(len(l[0x50])//28):
   m=l[0x50][mi*28:(mi+1)*28];flags=struct.unpack_from('<I',m,24)[0]
   if flags&0x600!=0x200:continue
   first,count=struct.unpack_from('<IH',m);si=struct.unpack_from('<H',m,22)[0];base=struct.unpack_from('<i',l[0x52],si*12+8)[0];ix=indices[first:first+3*count].astype('int64')+base;p=pts[pi[ix]].reshape(-1,3,3);b=np.array(struct.unpack_from('<8f',l[0x51],mi*32));lo=p.reshape(-1,3).min(axis=0);hi=p.reshape(-1,3).max(axis=0)
   err=max(float(np.max(b[:3]-b[4:7]-lo)),float(np.max(hi-b[:3]-b[4:7])))
   if err>.05:bad.append({'mesh':mi,'error':err})
   normal=-np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);length=np.linalg.norm(normal,axis=1);valid=length>.001;normal=normal[valid]/length[valid,None];area=length[valid];avg=np.sum(normal*area[:,None],axis=0)/sum(area) if len(area) else np.zeros(3)
   tex=struct.unpack_from('<h',l[0x52],si*12)[0];ti=struct.unpack_from('<I',l[2],tex*36+12)[0];no=struct.unpack_from('<I',l[0x2c],ti*4)[0];name=l[0x2b][no:l[0x2b].index(0,no)].decode()
   misc[(m[10:16].hex(),hex(flags))]+=1
   if len(samples)<30 or (label=='preview' and 'rock_sharp_lava' in name and len(samples)<70):samples.append({'mesh':mi,'material':name,'bytes10_22':m[10:22].hex(),'flags':hex(flags),'bounds':b.tolist(),'mean_geometric_normal':avg.tolist()})
  out[label]={'bad_bounds':bad[:30],'bad_bounds_count':len(bad),'metadata_histogram':[(str(k),v) for k,v in misc.most_common(10)],'samples':samples}
 (P/'draw-metadata-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:{n:v for n,v in r.items() if n!='samples'} for k,r in out.items()},indent=2));print(json.dumps({k:r['samples'][:5] for k,r in out.items()},indent=2))
if __name__=='__main__':audit()
