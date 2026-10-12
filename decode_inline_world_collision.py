"""Recover the eight inline world convex leaves using the published RSX layout."""
import struct
from pathlib import Path
from build_preview_source import TRANSLATION

def decode(path,report_path=None):
 def lump(i):return Path(str(path)+f'.{i:04x}.bsp_lump').read_bytes()
 nodes=list(struct.iter_unpack('<24h4I',lump(18)));leaf=lump(19);masks=[x[0] for x in struct.iter_unpack('<I',lump(16))];todo=[(0,0,0)];seen=set();faces=[];leaves=0;details=[]
 while todo:
  typ,index,mask=todo.pop()
  if typ==0:
   if index in seen:continue
   seen.add(index);n=nodes[index];m=masks[n[24]&255]
   todo.extend((t,n[24+j]>>8,m) for j,t in enumerate((n[26]&15,n[26]>>4&15,n[27]&15,n[27]>>4&15)))
  elif typ==3:
   num=struct.unpack_from('<I',leaf,index*4)[0];cursor=index+1+num
   for j in range(num):
    m,t,length=struct.unpack_from('<BBH',leaf,(index+1+j)*4);todo.append((t,cursor,masks[m]));cursor+=length
  elif typ==8:
   leaves+=1;at=index*4;vn,fn,tn,qn,*decode=struct.unpack_from('<4B4f',leaf,at);verts=at+20;cursor=verts+((6*vn+3*fn+3)//4)*4;details.append(dict(index=index,contents_mask=hex(mask),player_blocking=bool(mask&0x1000b),vertices=vn,faces=fn,triangle_groups=tn,quad_groups=qn))
   for quad,num in ((False,tn),(True,qn)):
    for group in range(num):
     h=struct.unpack_from('<I',leaf,cursor)[0];count=(h>>12&15)+1;base=(h>>16)<<10;cursor+=4
     def vert(i):
      if not 0<=i<vn:raise ValueError('Inline vertex outside leaf')
      raw=struct.unpack_from('<3H',leaf,verts+i*6)
      return tuple(raw[k]*65535*decode[3]+decode[k]-TRANSLATION[k] for k in range(3))
     for i in range(count):
      w=struct.unpack_from('<I',leaf,cursor)[0];cursor+=4;bits=10 if quad else 11;base+=w&((1<<bits)-1);a,b,c=vert(base),vert(base+1+(w>>bits&511)),vert(base+1+(w>>(bits+9)&511))
      face=[a,b,tuple(b[k]+c[k]-a[k] for k in range(3)),c] if quad else [a,b,c]
      if mask&0x1000b:faces.append(face)
 if report_path:
  import json
  Path(report_path).write_text(json.dumps(dict(inline_leaves=details,blocking_polygons=len(faces)),indent=2))
 return faces,leaves
