"""Compare native player sweeps with independent triangle/AABB SAT at edges."""
import json
import numpy as np
from audit_user_coordinates import P
from repair_preview_index_padding import read_lumps
from build_triangle_collision_lab import finish
from triangle_capsule_reference import swept_capsule_distance

def sat(face,start,end):
 edges=np.roll(face,-1,axis=0)-face;axes=[np.cross(edges[0],edges[1]),*np.eye(3),*[np.cross(e,a) for e in edges for a in np.eye(3)]];mn=np.array([-16,-16,0]);mx=np.array([16,16,72]);begin=0.;finish=1.
 for axis in axes:
  mag=np.linalg.norm(axis)
  if mag<1e-8:continue
  axis=axis/mag;vals=face@axis;lo=vals.min()-np.maximum(axis*mn,axis*mx).sum();hi=vals.max()-np.minimum(axis*mn,axis*mx).sum();a=float(axis@start);b=float(axis@(end-start))
  if abs(b)<1e-9:
   if not lo<=a<=hi:return False
  else:
   t=sorted(((lo-a)/b,(hi-a)/b));begin=max(begin,t[0]);finish=min(finish,t[1])
 return begin<=finish

def build():
 src=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp';out=P/'collision-lab/mp_phase_runner_preview.bsp';l=read_lumps(src,(3,));groups=[];point=[];contacts=[];clear=[];rng=np.random.default_rng(271027)
 for i in range(20):
  n=rng.normal(size=3);n/=np.linalg.norm(n);u=np.cross(n,[0,0,1]);u/=np.linalg.norm(u);v=np.cross(n,u);center=np.array([-10000+i*700,-10000,4096]);face=np.array([center-u*64-v*64,center+u*64-v*64,center+v*64]);groups.append([face]);point.append(dict(kind='lab',start=(center+n*128).tolist(),end=(center-n*128).tolist(),prop_probe=False))
  for j in range(24):
   target=center+u*rng.uniform(-140,140)+v*rng.uniform(-140,140)-[0,0,36];start=target+n*180;end=target-n*180;p=dict(kind='edge-SAT',start=start.tolist(),end=end.tolist(),prop_probe=True)
   # Native triangle sweeps use a rounded upright player shape rather than
   # the enclosing XY square. Compare definite contacts and definite gaps;
   # leave marginal native edge tolerances out of pass/fail assertions.
   distance=swept_capsule_distance(face,start,end)
   if distance<=15.8:contacts.append(p)
   elif distance>=20.5:clear.append(p)
 finish(src,out,l,groups,point);s=json.loads(out.with_name('source-build.json').read_text());s['pilot_hull_contact_probes']=contacts;s['hull_clearance_probes']=clear;out.with_name('source-build.json').write_text(json.dumps(s,indent=2));print('Independent rounded-hull contact',len(contacts),'clearance',len(clear))
if __name__=='__main__':build()
