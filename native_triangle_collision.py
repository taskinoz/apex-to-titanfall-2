"""Experimental native TF2 triangle collision; validate in an isolated lab first."""
import math,struct
import numpy as np
from extend_prop_collision import pack_grid

def packed_box(lo,hi):
 c=np.rint((np.array(lo)+hi)/2).astype(int);e=np.ceil(np.maximum(abs(np.array(lo)-c),abs(np.array(hi)-c))).astype(int)+2
 if np.any(abs(c)>32767) or np.any(e>32767):raise ValueError('Triangle box exceeds native short coordinates')
 return struct.pack('<3hH3hH',*c,0x8000,*e,0)

def encode(groups,first_vertex=0,flags=None):
 vertices=bytearray();triangles=bytearray();nodes=bytearray();headers=bytearray();starts=bytearray();bounds=[]
 for group_index,faces in enumerate(groups):
  faces=np.array(faces,dtype='<f4');count=len(faces)
  if not 1<=count<=300:raise ValueError('Invalid triangle group count')
  lo=faces.min(axis=(0,1)).astype(float);hi=faces.max(axis=(0,1)).astype(float);first_tri=len(triangles)//4;first_node=len(nodes)//16;first_vert=first_vertex+len(vertices)//12
  vertices.extend(faces.tobytes())
  # Bits 28..29 select the lowest-Z vertex. Bit 30 selects the highest
  # from the remaining pair. Verified against all 662,080 Homestead triangles.
  for i,face in enumerate(faces):
   low=int(np.argmin(face[:,2]));high=int(np.argmax(face[:,2]));options=[(j+1)&~low for j in range(2)]
   if low==high:high=options[0]
   flag=((low|options.index(high)<<2)<<4) if flags is None else flags[group_index]
   triangles.extend(struct.pack('<I',i*3|(1<<10)|(2<<17)|(flag<<24)));starts.extend(bytes(2))
  node_count=2*(count-(count+3)%6+3)//3
  nodes.extend(packed_box(lo,hi)*node_count)
  headers.extend(struct.pack('<6h4i4f',0,0x200,0,count*3,count,0,first_vert,first_tri,first_node,0,0,0,0,1))
  bounds.append((lo.tolist(),hi.tolist()))
 return {3:vertices,0x42:triangles,0x44:nodes,0x45:headers,0x60:starts,0x61:bytes(8)},bounds

def collision_grid(brush_bounds,triangle_bounds):
 # Reuse the verified grid grouping, then mark appended shape indices as TriColl.
 l=pack_grid(brush_bounds+triangle_bounds);p=bytearray(l[0x59]);sets=bytearray(l[0x57]);offset=len(brush_bounds)
 def convert(word):
  index=(word>>8)&65535
  return word if index<offset else (0x40<<24)|((index-offset)<<8)|(word&255)
 for at in range(0,len(p),4):struct.pack_into('<I',p,at,convert(struct.unpack_from('<I',p,at)[0]))
 for at in range(0,len(sets),8):
  if struct.unpack_from('<H',sets,at+2)[0]==1:struct.pack_into('<I',sets,at+4,convert(struct.unpack_from('<I',sets,at+4)[0]))
 l[0x59]=p;l[0x57]=sets;return l
