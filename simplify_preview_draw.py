"""Topology-aware render-only simplification; full source collision stays intact."""
import ctypes, json, math, struct, time, os
from pathlib import Path
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility
from spatial_preview_meshes import partition
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'


def simplifier():
    with os.add_dll_directory('C:/ProgramData/mingw64/mingw64/bin'):
        dll=ctypes.CDLL(str(ROOT/'tools/meshoptimizer/meshoptimizer.dll'))
    fn=dll.meshopt_simplifyWithAttributes
    vp=ctypes.c_void_p;sz=ctypes.c_size_t
    fn.argtypes=[vp,vp,sz,vp,sz,sz,vp,sz,vp,sz,vp,sz,ctypes.c_float,ctypes.c_uint,vp]
    fn.restype=sz
    return fn


def simplify(fn,indices,positions,attributes,ratio,error,locks=None,options=37):
    indices=np.ascontiguousarray(indices,dtype='<u4').reshape(-1)
    positions=np.ascontiguousarray(positions,dtype='<f4')
    attributes=np.ascontiguousarray(attributes,dtype='<f4')
    weights=np.array([.01,.01,.01,.005,.005,.001,.001,.001,.001],dtype='<f4')
    output=np.empty_like(indices);actual=ctypes.c_float()
    count=fn(output.ctypes.data,indices.ctypes.data,len(indices),positions.ctypes.data,
        len(positions),12,attributes.ctypes.data,36,weights.ctypes.data,9,
        locks.ctypes.data if locks is not None else None,max(3,int(len(indices)*ratio)//3*3),
        error,options,ctypes.byref(actual)) # LockBorder | ErrorAbsolute | Permissive
    if count%3 or count>len(indices) or actual.value>error+.01:
        raise ValueError('Simplifier exceeded index/error constraints')
    return output[:count].reshape(-1,3),float(actual.value)


def prepare(ratio=.06,error=4.):
    source=P/'preview-full-collision/mp_phase_runner_preview.bsp'
    l=read_lumps(source,(3,0x1e,0x49,0x4f,0x50,0x51,0x52,0x0e,0x7b))
    positions=np.frombuffer(l[3],dtype='<f4').reshape(-1,3)
    normals=np.frombuffer(l[0x1e],dtype='<f4').reshape(-1,3)
    vd=np.dtype([('pi','<u4'),('ni','<u4'),('uv','<f4',2),('color','u1',4),('rest','V24')])
    vertices=np.frombuffer(l[0x49],dtype=vd)
    ids=np.frombuffer(l[0x4f],dtype='<u2')
    groups={};rows=list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))
    for i,r in enumerate(rows):groups.setdefault(r[-2],[]).append(i)
    fn=simplifier();report=[];new={};start=time.monotonic()
    for si,meshes in groups.items():
        sort=struct.unpack_from('<4hI',l[0x52],si*12)
        base=sort[4];span=(sort[3]&65535)+1
        tris=np.concatenate([ids[rows[i][0]:rows[i][0]+rows[i][1]*3] for i in meshes]).astype('<u4').reshape(-1,3)
        if si<94:
            out=tris;actual=0.
        else:
            # Deduplicate the original full vertex records. No new interpolated
            # vertices or texture samples are created by this non-destructive API.
            source_vertices=vertices[base:base+span]
            attrs=np.column_stack((normals[source_vertices['ni']],source_vertices['uv'],
                                   source_vertices['color'].astype(float)/255)).astype('<f4')
            points=positions[source_vertices['pi']]
            _,first,inverse=np.unique(np.column_stack((points,attrs)),axis=0,return_index=True,return_inverse=True)
            out,actual=simplify(fn,inverse[tris],points[first],attrs[first],ratio,error)
            out=first[out].astype('<u4')
        new[si]=out
        report.append(dict(material_sort=si,before=len(tris),after=len(out),error=actual,original_world_preserved=si<94))
        if len(report)%100==0:print(f'Simplified {len(report)}/{len(groups)} material batches',flush=True)
    result=dict(before=sum(r['before'] for r in report),after=sum(r['after'] for r in report),
                maximum_error=max(r['error'] for r in report),ratio=ratio,error_limit=error,
                elapsed_seconds=time.monotonic()-start,batches=report)
    print(json.dumps({k:v for k,v in result.items() if k!='batches'},indent=2),flush=True)
    (ROOT/'logs/render-simplification-plan.json').write_text(json.dumps(result,indent=2))
    return l,rows,new,result


if __name__=='__main__':prepare()
