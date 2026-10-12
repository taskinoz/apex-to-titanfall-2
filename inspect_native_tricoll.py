"""Inspect native triangle-tree layouts and per-triangle orientation flags."""
import collections,json,struct
import numpy as np
from audit_user_coordinates import ROOT,P
from repair_preview_index_padding import read_lumps
def inspect():
 l=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',(3,0x42,0x44,0x45,0x60,0x61));h=list(struct.iter_unpack('<6h4i4f',l[0x45]));v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);words=np.frombuffer(l[0x42],dtype='<u4');report=[]
 for count in (3,4,5,6,8,10,12,16,24):
  found=[(i,r) for i,r in enumerate(h) if r[4]==count]
  if not found:continue
  i,r=found[0];w=words[r[7]:r[7]+r[4]];a=w&1023;b=a+((w>>10)&127);c=a+((w>>17)&127);tri=v[r[6]+np.stack((a,b,c),axis=1)];n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);nc=2*(count-(count+3)%6+3)//3;nodes=list(struct.iter_unpack('<8h',l[0x44][r[8]*16:(r[8]+nc)*16]));row=dict(index=i,header=r,geometry_bounds=[tri.min(axis=(0,1)).tolist(),tri.max(axis=(0,1)).tolist()],nodes=nodes,triangle_flags=(w>>24).tolist(),face_normals=n.tolist(),bevel_starts=list(struct.unpack_from('<'+'H'*count,l[0x60],r[7]*2)));report.append(row);print(json.dumps(row,indent=2))
 (P/'native-tricoll-layout.json').write_text(json.dumps(report,indent=2))
 # Catalog high bits against face normal major axis; low nibble bevel count.
 catalog=collections.Counter()
 for r in h:
  w=words[r[7]:r[7]+r[4]];a=w&1023;b=a+((w>>10)&127);c=a+((w>>17)&127);tri=v[r[6]+np.stack((a,b,c),axis=1)];normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);axis=np.argmax(abs(normal),axis=1);sign=normal[np.arange(len(w)),axis]>=0
  catalog.update(zip((w>>28).tolist(),axis.tolist(),sign.tolist()))
 print('ORIENTATION CATALOG',catalog)
if __name__=='__main__':inspect()
