"""Identify exact source shapes touching a reported player-hull position."""
import json,struct
import numpy as np
from audit_user_coordinates import P
from repair_preview_index_padding import read_lumps
from triangle_capsule_reference import intersects,point_triangle,segments

def inspect(point):
 path=P/'preview-full-collision/mp_phase_runner_preview.bsp';l=read_lumps(path,(1,3,0x45,0x5c));report=json.loads(path.with_name('collision-ownership.json').read_text());h=list(struct.iter_unpack('<6h4i4f',l[0x45]));v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);p=np.array(point);a=p+[0,0,16];b=p+[0,0,56];contacts=[];starts=np.array([r[7] for r in h]);owners={i:o for o in report['owners'] for i in range(o['first_header'],o['first_header']+o['headers'])}
 tri=v[h[0][6]:h[-1][6]+h[-1][3]].reshape(-1,3,3);near=np.flatnonzero(np.all(tri.min(1)<=p+[16,16,72],axis=1)&np.all(tri.max(1)>=p+[-16,-16,0],axis=1))
 for i in near:
  t=tri[i].astype(float);dist=0 if intersects(a,b,t) else min(point_triangle(a,t),point_triangle(b,t),*[segments(a,b,x,y) for x,y in zip(t,np.roll(t,-1,axis=0))])**.5
  if dist<=16.05:
   header=int(np.searchsorted(starts,i,side='right')-1);o=owners.get(header,{});contacts.append(dict(triangle=int(i),distance=dist,source_prop=o.get('index','world'),model=o.get('model','world'),vertices=t.tolist()))
 planes=np.frombuffer(l[1],dtype='<f4').reshape(-1,4);brush_owners={i:o for o in report['owners'] for i in range(o['first_brush'],o['first_brush']+o['brushes'])};brush=[]
 for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
  lo=np.array(r[:3])-r[6:9];hi=np.array(r[:3])+r[6:9]
  if np.any(p>hi+[16,16,0]) or np.any(p<lo-[16,16,72]):continue
  q=planes[1+r[9]:1+r[9]+r[4]];expanded=q[:,3]-np.minimum(q[:,:3]*[-16,-16,0],q[:,:3]*[16,16,72]).sum(1)
  if np.all(q[:,:3]@p<=expanded+.05):brush.append(dict(brush=i,source_prop=brush_owners[i]['index'],model=brush_owners[i]['model']))
 return dict(point=point,triangles=contacts,brushes=brush)
if __name__=='__main__':
 points=[[-3671.530363108447,189.42321388811703,-1244.3403685503463],[4484,474,-1112.375571231088]];print(json.dumps([inspect(p) for p in points],indent=2))
