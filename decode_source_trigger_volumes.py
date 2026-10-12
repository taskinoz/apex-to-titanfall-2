"""Translate Apex inline signed BVH convex trigger pieces to native R2 planes.

The entity's collision stream has a 56-byte descriptor followed by a surface
name, inline convex leaves and a BVH. Coordinates in this entity variant are
signed int16, unlike the unsigned type-8 leaves in a world BVH.
"""
import base64, json, math, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from scipy.spatial import ConvexHull, HalfspaceIntersection
from scipy.optimize import linprog

def pieces(entity):
    keys=sorted((k for k in entity if k.startswith('*coll')),key=lambda k:int(k[5:]))
    raw=base64.b64decode(''.join(entity[k] for k in keys),validate=True)
    if len(raw)<80 or struct.unpack_from('<I',raw)[0]!=56:
        raise ValueError('Unsupported entity collision descriptor')
    start=struct.unpack_from('<I',raw,28)[0]
    end=56+struct.unpack_from('<I',raw,20)[0]
    if not 56<=start<end<=len(raw):raise ValueError('Invalid leaf range')
    out=[];cursor=start
    while cursor<end:
        vn,fn,tn,qn,*decode=struct.unpack_from('<4B4f',raw,cursor)
        if not(4<=vn<=127 and 4<=fn<=255 and 0<tn+qn<64 and 1e-9<decode[3]<.01):
            break # Remaining bytes are the BVH nodes, not convex leaves.
        p=np.array(struct.unpack_from('<'+'h'*vn*3,raw,cursor+20),float).reshape(vn,3)*65535*decode[3]+decode[:3]
        if not np.isfinite(p).all() or np.max(abs(p))>131072:raise ValueError('Invalid trigger vertices')
        hull=ConvexHull(p)
        if hull.volume<=1e-4:raise ValueError('Empty convex trigger')
        planes=[]
        for eq in hull.equations:
            q=np.r_[eq[:3],-eq[3]]
            if not any(np.linalg.norm(q[:3]-v[:3])<1e-6 and abs(q[3]-v[3])<.01 for v in planes):planes.append(q)
        out.append(dict(points=p.tolist(),planes=[q.tolist() for q in planes]))
        at=cursor+((20+6*vn+3*fn+3)//4)*4
        for n in (tn,qn):
            for _ in range(n):
                count=(struct.unpack_from('<I',raw,at)[0]>>12&15)+1
                at+=4+count*4
        cursor=at
    if not out:raise ValueError('No convex trigger pieces decoded')
    return out

def native(entity,translation=(0,0,0),name='converted_trigger'):
    shapes=pieces(entity)
    row={k:v for k,v in entity.items() if not(k.startswith('*') or k.startswith('gamemode_') or k.startswith('link_')) and k!='model'}
    origin=np.array(list(map(float,row['origin'].split())))-translation
    # Native map coordinates are bounded. Intersect oversized Apex exclusion
    # volumes with this safe world domain; retain the exact sloping planes.
    clipped=[]
    for shape in shapes:
        q=np.asarray(shape['planes'])
        limits=[]
        for axis in range(3):
            for sign in (-1,1):
                n=np.zeros(3);n[axis]=sign
                limits.append([*n,16000-sign*origin[axis]])
        q=np.concatenate((q,limits))
        fit=linprog([0,0,0,-1],A_ub=np.c_[q[:,:3],np.ones(len(q))],b_ub=q[:,3],bounds=[(None,None)]*3+[(0,None)],method='highs')
        if not fit.success or fit.x[3]<1e-4:continue
        points=HalfspaceIntersection(np.c_[q[:,:3],-q[:,3]],fit.x[:3]).intersections
        hull=ConvexHull(points);planes=[]
        for eq in hull.equations:
            value=np.r_[eq[:3],-eq[3]]
            if not any(np.linalg.norm(value[:3]-v[:3])<1e-6 and abs(value[3]-v[3])<.01 for v in planes):planes.append(value)
        clipped.append(dict(points=points,planes=planes))
    shapes=clipped
    if not shapes:return None
    row['origin']=' '.join(f'{v:.6g}' for v in origin)
    row['targetname']=name
    points=np.concatenate([s['points'] for s in shapes])
    row['*trigger_bounds_mins']=' '.join(f'{v:.8g}' for v in points.min(0))
    row['*trigger_bounds_maxs']=' '.join(f'{v:.8g}' for v in points.max(0))
    for bi,shape in enumerate(shapes):
        for pi,q in enumerate(shape['planes']):row[f'*trigger_brush_{bi}_plane_{pi}']=' '.join(f'{v:.9g}' for v in q)
    return row

if __name__=='__main__':
    source=json.loads((ROOT/'output/composite/source-gameplay-volumes.json').read_text())
    report={}
    for name,rows in source.items():
        converted=[v for i,e in enumerate(rows) if e['classname'].startswith('trigger') for v in [native(e,(26000,19000,0) if name=='phase' else (0,0,0),f'{name}_source_boundary_{i}')] if v is not None]
        report[name]=converted
        print(name,len(converted),'pieces',sum(sum(k.endswith('_plane_0') for k in e) for e in converted))
        for e in converted[:2]:print(e['classname'],e['origin'],e['*trigger_bounds_mins'],e['*trigger_bounds_maxs'])
    (ROOT/'output/composite/native-gameplay-volumes.json').write_text(json.dumps(report,indent=2))
