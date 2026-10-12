"""Read Season 3 model physics using the checked RSX IRPS/BVH layouts."""
import math,struct,collections
from pathlib import Path
from build_preview_source import cross,subtract

def checked(data,fmt,at):
 size=struct.calcsize(fmt)
 if at<0 or at+size>len(data):raise ValueError('Physics pointer outside model')
 return struct.unpack_from(fmt,data,at)

def read_phy(path,checksum=None):
 d=Path(path).read_bytes();size,kind,count,check,properties=checked(d,'<5I',0)
 if size!=20 or kind!=1 or count>4096:raise ValueError('Unsupported IRPS header')
 if checksum is not None and check!=checksum:raise ValueError('Physics/model checksum mismatch')
 offset,n,_,_=checked(d,'<4q',20)
 if count!=n:raise ValueError('Physics group count mismatch')
 out=[]
 for group in range(count):
  so,sn=checked(d,'<2q',20+offset+144*group)
  if not 0<sn<4096:raise ValueError('Invalid convex piece count')
  for solid in range(sn):
   vo,vn,fo,fn,eo,en=checked(d,'<6q',20+so+64*solid+16)
   if not 4<=vn<=127 or not 4<=fn<=255:raise ValueError('Invalid convex topology count')
   verts=[checked(d,'<3f',20+vo+12*i) for i in range(vn)];faces=[]
   for i in range(fn):
    ids=[]
    for v in checked(d,'<32b',20+fo+32*i):
     if v==-1:break
     if not 0<=v<vn:raise ValueError('Convex vertex index outside piece')
     ids.append(v)
    if len(ids)<3:raise ValueError('Invalid convex face')
    faces.append([verts[v] for v in ids])
   out.append(faces)
 return out

def plane(face):
 # First three points can be collinear on original polygon loops.
 best=max((cross(subtract(face[i],face[0]),subtract(face[i+1],face[0])) for i in range(1,len(face)-1)),key=lambda v:sum(x*x for x in v))
 mag=math.sqrt(sum(v*v for v in best))
 if mag<1e-6:return None
 n=tuple(v/mag for v in best);return (*n,sum(n[k]*face[0][k] for k in range(3)))

def convex_planes(faces,tolerance=.08):
 points=list({tuple(p) for f in faces for p in f})
 if len(points)<4:return None
 center=tuple(sum(p[k] for p in points)/len(points) for k in range(3));planes=[]
 for face in faces:
  q=plane(face)
  if q is None:continue
  if sum(q[k]*center[k] for k in range(3))>q[3]:q=tuple(-v for v in q)
  if any(sum(q[k]*p[k] for k in range(3))>q[3]+tolerance for p in points):return None
  if not any(sum((q[k]-v[k])**2 for k in range(3))<1e-10 and abs(q[3]-v[3])<.02 for v in planes):planes.append(q)
 if len(planes)<4:return None
 return points,planes

def read_bvh(path):
 d=Path(path).read_bytes();root=checked(d,'<I',532)[0]
 if not root:return [],{}
 mask_at,_,_,count=checked(d,'<4i',root)
 if not 0<count<4096:raise ValueError('Invalid BVH header count')
 pieces=[];stats=collections.Counter()
 for hi in range(count):
  header_flags,nodeoff,vertoff,leafoff,*decode=checked(d,'<4i4f',root+16+32*hi)
  if header_flags not in (0,1):raise ValueError('Unsupported packed BVH header flags')
  nodeoff+=root;vertoff+=root;leafoff+=root;origin=decode[:3];scale=decode[3];visited=set();active=set()
  def mask(i):return checked(d,'<I',root+mask_at+4*i)[0]
  def polys(at,packed,quad,vertices=vertoff,org=origin,sc=scale,signed=bool(header_flags&1)):
   h=checked(d,'<I',at)[0];num=(h>>12&15)+1;base=(h>>16)<<10;result=[]
   def vert(i):
    # Global signed packed vertices are centered on header.origin. Inline
    # type-8 vertices instead use their own unsigned local decode frame.
    raw=checked(d,('<3h' if signed else '<3H') if packed else '<3f',vertices+i*(6 if packed else 12))
    return tuple(raw[k]*65535*sc+org[k] for k in range(3)) if packed else raw
   for i in range(num):
    w=checked(d,'<I',at+4+i*4)[0]
    if quad:base+=w&1023;b=w>>10&511;c=w>>19&511
    else:base+=w&2047;b=w>>11&511;c=w>>20&511
    a,b,c=vert(base),vert(base+1+b),vert(base+1+c)
    result.append([a,b,tuple(b[k]+c[k]-a[k] for k in range(3)),c] if quad else [a,b,c])
   return result,at+4+4*num
  def visit(typ,index,contents,depth=0):
   if depth>128:raise ValueError('BVH recursion overflow')
   stats['type_'+str(typ)]+=1
   if typ==1:return
   if typ==0:
    if index in active:raise ValueError('BVH cycle')
    if index in visited:return
    visited.add(index);active.add(index);a,b,c,e=checked(d,'<4I',nodeoff+64*index+48);m=mask(a&255)
    for t,j in ((c&15,a>>8),(c>>4&15,b>>8),(e&15,c>>8),(e>>4&15,e>>8)):visit(t,j,m,depth+1)
    active.remove(index);return
   at=leafoff+4*index
   if typ==3:
    num=checked(d,'<I',at)[0]
    if num>256:raise ValueError('Invalid compound leaf count')
    cursor=index+1+num
    for i in range(num):
     m,t,length=checked(d,'<BBH',at+4+4*i);visit(t,cursor,mask(m),depth+1);cursor+=length
    return
   if not contents&1:return
   if typ in (4,5,6,7):
    fs,_=polys(at,typ in (5,7),typ in (6,7));pieces.extend([[f] for f in fs]);return
   if typ==8:
    vn,fn,tn,qn,*v=checked(d,'<4B4f',at);vertices=at+20;cursor=vertices+((6*vn+3*fn+3)//4)*4;fs=[]
    for quad,num in ((False,tn),(True,qn)):
     for i in range(num):
      f,cursor=polys(cursor,True,quad,vertices,v[:3],v[3],False);fs.extend(f)
    if fs:pieces.append(fs)
    return
   raise ValueError('Unsupported solid model BVH leaf '+str(typ))
  visit(0,0,0)
 return pieces,dict(stats)

if __name__=='__main__':
 import json
 for name in ('phase_runner_tunnel','phase_runner_tunnel_02','rock_sharp_lava_moss_desertlands_06','rock_lava_small_moss_desertlands_02','hollow_pipe_modular_painted_red_corner'):
  base=Path('tools/legion/exported_files/models')/name/name
  if base.with_suffix('.phy').exists():pieces=read_phy(base.with_suffix('.phy'));s={}
  else:pieces,s=read_bvh(base.with_suffix('.rmdl'))
  print(name,json.dumps(dict(pieces=len(pieces),faces=sum(len(p) for p in pieces),convex=sum(convex_planes(p) is not None for p in pieces),stats=s)))

