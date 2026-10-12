"""Trace the five reported art problems to source placements and draw surfaces."""
import json,struct,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from read_vg_static import load,compiled_materials
from build_phase_runner_catwalks import mesh_faces
from repair_preview_index_padding import read_lumps
from optimize_portalfree_render import material_name
P=ROOT/'output/phase-runner'
def main():
    props=json.loads((P/'static-props.json').read_text());selected=[p for p in props if p['index'] in (8449,8450,8451,8452,8453,8454,8459,8460,8461,8462,8463,8464,8465,8466,13008,13009,13010,13011,13012,13013,13014,13015,8483,8484)]
    report=[];cache={}
    for prop in selected:
        name=Path(prop['model']).stem;folder=ROOT/'tools/legion/exported_files/models'/name
        if name not in cache:
            vg=(folder/(name+'.vg')).read_bytes();h=struct.unpack_from('<18Q',vg,16);lods=h[13];sections,slots,skins=load(folder,lods-1)
            cache[name]=dict(model=name,lods=lods,lod_triangles=[sum(len(s) for s in load(folder,i)[0]) for i in range(lods)],materials=skins,slots=slots)
        report.append(dict(**prop,asset=cache[name]))
    for v in cache.values():print(json.dumps(v))
    l=read_lumps(P/'glass-console/mp_phase_runner.bsp',(2,3,0x2b,0x2c,0x49,0x4f,0x50,0x52));points=[(817.4,-2325.7,-1280),(-546.7,-2404.7,-1280),(-74.7,-2681.6,-1280)];near=[collections.Counter() for _ in points];rows=[]
    for mi,r,raw,ids,tri in mesh_faces(l):
        sort=struct.unpack_from('<h',l[0x52],r[-2]*12)[0];name=material_name(l,sort)
        for i,pt in enumerate(points):
            low=tri.min(1);high=tri.max(1);mask=(low[:,0]<pt[0]+350)&(high[:,0]>pt[0]-350)&(low[:,1]<pt[1]+350)&(high[:,1]>pt[1]-350)&(low[:,2]<pt[2]+160)&(high[:,2]>pt[2]-50)
            if mask.any():near[i][name]+=int(mask.sum())
            if i==2:
                # Vertical intersections identify stacked coplanar ground layers.
                a=tri[:,0,:2];b=tri[:,1,:2]-a;c=tri[:,2,:2]-a;d=np.array(pt[:2])-a;den=b[:,0]*c[:,1]-b[:,1]*c[:,0];ok=abs(den)>1e-8
                u=np.divide(d[:,0]*c[:,1]-d[:,1]*c[:,0],den,out=np.zeros_like(den),where=ok);v=np.divide(b[:,0]*d[:,1]-b[:,1]*d[:,0],den,out=np.zeros_like(den),where=ok)
                take=ok&(u>=-1e-5)&(v>=-1e-5)&(u+v<=1.00001)
                for j in np.flatnonzero(take):
                    z=float(tri[j,0,2]+u[j]*(tri[j,1,2]-tri[j,0,2])+v[j]*(tri[j,2,2]-tri[j,0,2]))
                    if abs(z-pt[2])<30:rows.append(dict(mesh=mi,triangle=int(j),material=name,z=z,corners=tri[j].tolist()))
    out=dict(placements=report,nearby_material_counts=[dict(point=pt,counts=dict(c)) for pt,c in zip(points,near)],ground_intersections=rows)
    (ROOT/'logs/reported-art-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='placements'},indent=2))
if __name__=='__main__':main()
