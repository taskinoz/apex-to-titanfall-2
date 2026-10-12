"""Inspect nearby upward-facing lightmap receivers at reported gameplay locations."""
import json
from repair_environment_lighting import ROOT,OUT,BAKE,np
dt=np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')])
jobs=np.memmap(OUT/'jobs.bin',dt,'r');center=jobs['p'].mean(1);normal=jobs['n'].mean(1)
caster=np.fromfile(OUT/'environment-caster-mask.bin',np.uint8).astype(bool)
data=np.memmap(BAKE,'<f4','r',shape=(2,4096,4096,5));old=np.memmap(OUT/'lighting.bin','<f4','r',shape=data.shape)
result=[]
for point in ([-761,-4444,-991],[-2163,3016,-974],[1839,-782,-1201],[186,-5211,-955],[-1716,-3994,-963]):
    sel=caster&(normal[:,2]>.7)&(np.linalg.norm(center-np.array(point),axis=1)<500)
    picked=jobs[sel];uv=picked['uv'].mean(1).astype(int);page=picked['page']
    v=data[page,uv[:,1],uv[:,0]];o=old[page,uv[:,1],uv[:,0]];valid=v[:,1]>=0
    result.append(dict(point=point,nearby_upward_faces=len(v),valid_samples=int(valid.sum()),sun_unoccluded_mean=float(v[valid,0].mean()),
        prior_sun_mean=float(o[valid,0].mean()),sky_visibility_mean=float(v[valid,1].mean()),prior_sky_mean=float(o[valid,1].mean()),
        limitation='Triangle-center nearest texel samples; not a client rendering check or a trace at the exact point.'))
(ROOT/'logs/environment-ground-lighting.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
