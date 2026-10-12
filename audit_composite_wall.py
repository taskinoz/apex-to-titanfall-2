"""Ray-probe the reported wall for coincident surfaces and lighting seams."""
import json,math
import recover_composite_details as r
np=r.np;OUT=r.OUT;WORK=OUT/'local-repair'
a=np.load(OUT/'scene.npz');t=a['triangles'];mi=a['material'];names=a['names'];a.close();p=np.array([-1917.1,631.305,252.031]);near=np.linalg.norm(t[:,:,:3].mean(1)-p,axis=1)<1600;ti=np.flatnonzero(near);s=t[near,:,:3];e1=s[:,1]-s[:,0];e2=s[:,2]-s[:,0];diff=p-s[:,0];q=np.cross(diff,e1);records=[]
for pitch,yaw in [(-25,130),(-20,135),(-40,135),(-30,115),(-20,110),(-15,150),(-10,135),(-50,130)]:
 y=math.radians(yaw);b=math.radians(pitch);d=np.array([math.cos(b)*math.cos(y),math.cos(b)*math.sin(y),-math.sin(b)]);h=np.cross(d,e2);det=(e1*h).sum(1);inv=np.divide(1,det,out=np.zeros_like(det),where=abs(det)>1e-8);u=(diff*h).sum(1)*inv;v=(q*d).sum(1)*inv;distance=(e2*q).sum(1)*inv;valid=(u>=0)&(v>=0)&(u+v<=1)&(distance>0)&(abs(det)>1e-8);ids=np.flatnonzero(valid);ids=ids[np.argsort(distance[ids])][:8];hits=[]
 for i in ids:
  index=int(ti[i]);hits.append(dict(index=index,distance=float(distance[i]),position=(p+d*distance[i]).tolist(),material=str(names[mi[index]]),normal=t[index,:,3:6].tolist(),triangle=t[index].tolist()))
 records.append(dict(pitch=pitch,yaw=yaw,hits=hits));print(pitch,yaw,[(x['index'],round(x['distance'],5),x['material']) for x in hits])
(WORK/'wall-rays.json').write_text(json.dumps(records,indent=2))
