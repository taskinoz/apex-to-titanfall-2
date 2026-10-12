"""Create collision-only native triangle fixtures without replacing the user map."""
import json,shutil,struct
import numpy as np
from audit_user_coordinates import ROOT,P
from compact_preview_bsp import compact
from repair_preview_index_padding import read_lumps
from native_triangle_collision import encode,collision_grid
def build():
 src=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp';out=P/'collision-lab/mp_phase_runner_preview.bsp';l=read_lumps(src,(3,));groups=[];probes=[];flags=[]
 directions=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,1),(-1,1,1),(1,-1,1),(1,1,-1)]
 for flag in (0,16,32,64,80,96):
  for direction in directions:
   normal=np.array(direction,dtype=float);normal/=np.linalg.norm(normal);u=np.cross(normal,[0,0,1] if abs(normal[2])<.9 else [0,1,0]);u/=np.linalg.norm(u);v=np.cross(normal,u)
   center=np.array([-14000+len(groups)*450,4000,4096]);face=[center-u*64-v*64,center+u*64-v*64,center+v*64];groups.append([face]);flags.append(flag)
   start=(center+normal*160).tolist();end=(center-normal*160).tolist()
   probes.extend([dict(kind='lab',start=start,end=end,prop_probe=True,flag=flag,direction=direction),dict(kind='lab',start=end,end=start,prop_probe=True,flag=flag,direction=direction)])
 for count in (2,3,4,6,12,24,96,300):
  faces=[];center=[-14000+len(groups)*450,-4000,4096]
  for j in range(count):
   x=center[0]+j%10*6;y=center[1]+j//10*6;faces.append([[x-2,y-2,4096],[x+2,y-2,4096],[x,y+2,4096]])
   probes.append(dict(kind='lab',start=[x,y,4224],end=[x,y,3968],prop_probe=True))
  groups.append(faces)
 return finish(src,out,l,groups,probes)
 for axis in range(3):
  for sign in (-1,1):
   center=[axis*700+sign*180,0,4096];other=[k for k in range(3) if k!=axis];a=center.copy();b=center.copy();c=center.copy();a[other[0]]-=128;a[other[1]]-=128;b[other[0]]+=128;b[other[1]]-=128;c[other[1]]+=128
   face=[a,b,c] if sign>0 else [c,b,a];groups.append([face]);start=center.copy();end=center.copy();start[axis]+=128;end[axis]-=128;probes.extend([dict(kind='lab',start=start,end=end,prop_probe=True),dict(kind='lab',start=end,end=start,prop_probe=True)])
 for count in (2,3,4,6,12,24):
  faces=[];center=[3500+count*25,1000,4096]
  for j in range(count):
   x=center[0]+j*100;faces.append([[x-30,970,4096],[x+30,970,4096],[x,1030,4096]])
   probes.append(dict(kind='lab',start=[x,990,4224],end=[x,990,3968],prop_probe=True))
  groups.append(faces)
def finish(src,out,l,groups,probes,flags=None):
 additions,tri_bounds=encode(groups,len(l[3])//12,flags);additions[3]=l[3]+additions[3]
 box=([-10001,-10001,-10001],[-9999,-9999,-9999]);additions.update({1:struct.pack('<4f',0,0,1,0),0x5c:struct.pack('<3f2BH3fI',-10000,-10000,-10000,0,0,0,1,1,1,0),0x5d:b'',0x5e:bytes(12),0x5f:bytes(192),0x5b:struct.pack('<I',1),**collision_grid([box],tri_bounds)})
 compact(src,out,additions)
 status=json.loads(src.with_name('source-build.json').read_text());status['collision_probes']=probes;status['hull_clearance_probes']=[];status['collision_sample_brushes']=1;status['triangle_collision_lab']=True
 out.with_name('source-build.json').write_text(json.dumps(status,indent=2));shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
 for f in src.parent.glob(src.stem+'_*.ent'):shutil.copy2(f,out.parent/f.name)
 print('Lab triangle fixtures',len(groups),'probes',len(probes))
if __name__=='__main__':build()
