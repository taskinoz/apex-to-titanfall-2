"""Independent Euclidean reference for Titanfall's upright rounded player hull."""
import numpy as np

def point_triangle(p,t):
 a,b,c=t;ab=b-a;ac=c-a;ap=p-a;d1=ab@ap;d2=ac@ap
 if d1<=0 and d2<=0:return float(ap@ap)
 bp=p-b;d3=ab@bp;d4=ac@bp
 if d3>=0 and d4<=d3:return float(bp@bp)
 vc=d1*d4-d3*d2
 if vc<=0 and d1>=0 and d3<=0:q=a+ab*d1/(d1-d3);return float((p-q)@(p-q))
 cp=p-c;d5=ab@cp;d6=ac@cp
 if d6>=0 and d5<=d6:return float(cp@cp)
 vb=d5*d2-d1*d6
 if vb<=0 and d2>=0 and d6<=0:q=a+ac*d2/(d2-d6);return float((p-q)@(p-q))
 va=d3*d6-d5*d4
 if va<=0 and d4-d3>=0 and d5-d6>=0:q=b+(c-b)*(d4-d3)/((d4-d3)+(d5-d6));return float((p-q)@(p-q))
 n=np.cross(ab,ac);return float((ap@n)**2/(n@n))

def segments(p,q,a,b):
 u=q-p;v=b-a;w=p-a;aa=u@u;bb=u@v;cc=v@v;dd=u@w;ee=v@w;den=aa*cc-bb*bb
 if aa<1e-12:s=0.;t=np.clip(ee/cc,0,1) if cc else 0.
 else:
  s=np.clip((bb*ee-cc*dd)/den,0,1) if den>1e-12 else 0.;t=(bb*s+ee)/cc if cc>1e-12 else 0.
  if t<0:t=0.;s=np.clip(-dd/aa,0,1)
  elif t>1:t=1.;s=np.clip((bb-dd)/aa,0,1)
 delta=w+s*u-t*v;return float(delta@delta)

def intersects(p,q,t):
 direction=q-p;e1=t[1]-t[0];e2=t[2]-t[0];h=np.cross(direction,e2);det=e1@h
 if abs(det)<1e-9:return False
 s=p-t[0];u=(s@h)/det;cross=np.cross(s,e1);v=(direction@cross)/det;at=(e2@cross)/det
 return 0<=u<=1 and 0<=v and u+v<=1 and 0<=at<=1

def tri_distance(a,b):
 edges_a=list(zip(a,np.roll(a,-1,axis=0)));edges_b=list(zip(b,np.roll(b,-1,axis=0)))
 if any(intersects(p,q,b) for p,q in edges_a) or any(intersects(p,q,a) for p,q in edges_b):return 0.
 return min(*[point_triangle(p,b) for p in a],*[point_triangle(p,a) for p in b],*[segments(p,q,r,s) for p,q in edges_a for r,s in edges_b])

def swept_capsule_distance(face,start,end):
 a=start+[0,0,16];b=start+[0,0,56];c=end+[0,0,56];d=end+[0,0,16]
 return min(tri_distance(face,np.array([a,b,c])),tri_distance(face,np.array([a,c,d])))**.5
