"""Measure original model LODs with component-preserving local simplification."""
import ctypes,collections,json,os
from pathlib import Path
import numpy as np
from read_vg_static import load
from simplify_preview_draw import simplifier,simplify,ROOT,P
from stage_prop_geometry import load_mesh
from repair_portal_surfaces import OVERLAYS

def component_locks(tris,points):
    with os.add_dll_directory('C:/ProgramData/mingw64/mingw64/bin'):
        dll=ctypes.CDLL(str(ROOT/'tools/meshoptimizer/component_render_locks.dll'))
    fn=dll.component_render_locks
    fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p];fn.restype=ctypes.c_size_t
    _,weld=np.unique(points,axis=0,return_inverse=True)
    weld=np.ascontiguousarray(weld,dtype='<u4');tris=np.ascontiguousarray(tris,dtype='<u4');points=np.ascontiguousarray(points,dtype='<f4')
    locks=np.zeros(len(points),dtype='u1')
    count=fn(locks.ctypes.data,tris.ctypes.data,tris.size,points.ctypes.data,len(points),weld.ctypes.data)
    return locks,int(count)

def model_sections(prop,lod_index,fn,ratio=.25,error=2.):
    name=Path(prop['model']).stem;folder=ROOT/'tools/legion/exported_files/models'/name
    if (folder/(name+'.vg')).is_file():
        sections,slots,skins=load(folder,lod_index)
    else:
        mesh,skins=load_mesh(prop['source_qc']);sections=[];slots=[]
        grouped=collections.defaultdict(list)
        for mat,tri in mesh:grouped[mat].append(tri)
        for mat,tris in grouped.items():
            sections.append(tris);slots.append(0 if mat=='default_material' else skins[0].index(mat))
    output=[];proof=[]
    for section,slot in zip(sections,slots):
        if not section:output.append(np.empty((0,3,8),dtype='<f4'));continue
        data=np.asarray(section,dtype='<f4').reshape(-1,8)
        data,inv=np.unique(data,axis=0,return_inverse=True)
        tris=inv.astype('<u4').reshape(-1,3)
        locks,components=component_locks(tris,data[:,:3])
        attrs=np.column_stack((data[:,3:8],np.ones((len(data),4)))).astype('<f4')
        if ratio>=1.:reduced=tris;actual=0.
        else:reduced,actual=simplify(fn,tris,data[:,:3],attrs,ratio,error,locks=locks)
        # Seam-equivalent indices can be merged even when their geometric
        # position is locked. Verify the actual anchored positions instead.
        retained={tuple(p) for p in data[np.unique(reduced),:3]}
        fallback=not all(tuple(p) in retained for p in data[locks.astype(bool),:3])
        if fallback:reduced=tris;actual=0.
        before=data[tris].reshape(-1,8);after=data[reduced].reshape(-1,8)
        if not np.array_equal(before[:,:3].min(axis=0),after[:,:3].min(axis=0)) or not np.array_equal(before[:,:3].max(axis=0),after[:,:3].max(axis=0)):raise ValueError('Model section bounds changed')
        output.append(data[reduced]);proof.append(dict(slot=slot,before=len(tris),after=len(reduced),components=components,locked_vertices=int(locks.sum()),error=actual,unsimplified_anchor_fallback=fallback))
    return output,slots,skins,proof

def prepare(tunnel_detail=False):
    selected=set()
    for f in ('prop-geometry','phase-structure-geometry','support-geometry','area-detail-geometry','broad-geometry','portal-geometry','landscape-geometry'):
        selected.update(p['index'] for p in json.loads((P/f/'report.json').read_text())['restored'])
    props=[p for p in json.loads((P/'static-props.json').read_text()) if p['index'] in selected]
    lods={p['model']:p['lods'] for p in json.loads((ROOT/'logs/available-vg-lods.json').read_text())}
    cache={};report=[];total=0;fn=simplifier()
    for p in props:
        n=Path(p['model']).stem
        if n not in cache:
            level=max(0,len(lods.get(n,[]))-1)
            ratio=.25;error=2.
            if tunnel_detail and n in ('phase_runner_tunnel','phase_runner_tunnel_02'):
                level=0;ratio=1.;error=0.
            if tunnel_detail and n=='wraith_tt_portal_large':
                level=min(1,len(lods[n])-1);ratio=1.;error=0.
            cache[n]=model_sections(p,level,fn,ratio=ratio,error=error)
            report.append(dict(model=n,lod_index=level,ratio=ratio,sections=cache[n][3]))
            if len(cache)%20==0:print(f'Prepared {len(cache)} source models',flush=True)
        sections,slots,skins,_=cache[n];skin=skins[p['skin'] if p['skin']<len(skins) else 0]
        total+=sum(len(s) for s,slot in zip(sections,slots) if skin[slot] not in OVERLAYS)
    result=dict(placements=len(props),models=len(cache),prop_triangles=total,models_detail=report,ratio=.25,error=2.,all_component_anchors_retained=True,local_bounds_preserved=True)
    result['full_detail_tunnels']=tunnel_detail
    (ROOT/('logs/tunnel-detail-model-plan.json' if tunnel_detail else 'logs/budget-model-geometry-plan.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='models_detail'},indent=2),flush=True)
    return props,cache,result

if __name__=='__main__':prepare()
