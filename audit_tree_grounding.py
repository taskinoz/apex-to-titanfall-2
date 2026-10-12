"""Audit fir roots against rendered terrain without mistaking their own collider for ground."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps
from build_phase_runner_catwalks import mesh_faces

def vertical_surface(tri,xy,ceiling,bounds=None):
    """Highest triangle intersection below ceiling; no hull or origin AABB shortcut."""
    p=np.asarray(xy)
    lo,hi=bounds if bounds is not None else (tri[:,:,:2].min(1),tri[:,:,:2].max(1))
    t=tri[np.all((lo<=p+1e-4)&(hi>=p-1e-4),axis=1)].astype(float)
    if not len(t):return None
    a=t[:,0];u=t[:,1]-a;v=t[:,2]-a;det=u[:,0]*v[:,1]-u[:,1]*v[:,0]
    good=np.abs(det)>1e-8;a,u,v,det=a[good],u[good],v[good],det[good]
    d=p-a[:,:2];s=(d[:,0]*v[:,1]-d[:,1]*v[:,0])/det;b=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/det
    z=a[:,2]+s*u[:,2]+b*v[:,2]
    good=(s>=-1e-5)&(b>=-1e-5)&(s+b<=1+1e-5)&(z<=ceiling)&(z>=-4096)
    return float(z[good].max()) if np.any(good) else None

def audit(bsp=None,report=None):
    package=ROOT/'northstar/PhaseRunner.Preview'
    bsp=Path(bsp or package/'mod/maps/mp_phase_runner.bsp')
    report=report or json.loads((package/'trees.json').read_text())
    lumps=read_lumps(bsp,(3,0x49,0x4f,0x50,0x52));excluded=set(report['new_meshes'])
    scene=np.concatenate([t for i,r,raw,vi,t in mesh_faces(lumps) if i not in excluded])
    bounds=(scene[:,:,:2].min(1),scene[:,:,:2].max(1))
    source=np.load(ROOT/'output/phase-runner/firs/source-geometry.npz')['data']
    result=[]
    for p in report['source_placements']:
        bark=source[p['first_triangle']:p['first_triangle']+62,:,:3]
        base=float(bark[:,:,2].min())+p.get('grounding_delta_z',0.);xy=np.asarray(p['origin'][:2]);samples=[]
        for dx,dy in ((0,0),(-8,0),(8,0),(0,-8),(0,8),(-8,-8),(-8,8),(8,-8),(8,8)):
            q=xy+[dx,dy];z=vertical_surface(scene,q,base+512,bounds)
            samples.append(dict(xy=q.tolist(),surface_z=z))
        heights=[s['surface_z'] for s in samples if s['surface_z'] is not None]
        if len(heights)!=len(samples):raise ValueError('Missing rendered root support '+str(p['index']))
        # Embed the bottom root ring below the lowest surrounding surface.
        # This also closes a gap on sloping terrain without adding box geometry.
        target=min(heights)-8;delta=min(0.,target-base)
        result.append(dict(index=p['index'],source_origin=p['origin'],rendered_root_z=base,
                           surface_min_z=min(heights),surface_max_z=max(heights),
                           visible_gap_units=max(0.,base-max(heights)),delta_z=delta,
                           target_root_z=base+delta,samples=samples))
    return dict(source_bsp=str(bsp),trees=len(result),floating_trees=sum(r['visible_gap_units']>1 for r in result),
                trees_needing_embedding=sum(r['delta_z']<-.01 for r in result),root_embed_units=8,placements=result,
                method='Vertical ray/triangle intersections against existing rendered geometry; trees excluded; nine root-footprint samples.')

if __name__=='__main__':
    r=audit();(ROOT/'logs/tree-grounding-before.json').write_text(json.dumps(r,indent=2))
    print(json.dumps({k:v for k,v in r.items() if k!='placements'},indent=2))
    for p in r['placements']:print(p['index'],'root',round(p['rendered_root_z'],2),'ground',round(p['surface_min_z'],2),'gap',round(p['visible_gap_units'],2),'move',round(p['delta_z'],2))
