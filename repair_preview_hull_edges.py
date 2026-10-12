"""Add native AABB sweep bevels to existing convex collision, keeping its volume."""
import itertools,json,math,struct,time
from pathlib import Path
from repair_preview_index_padding import read_lumps

ROOT=Path(__file__).resolve().parent

def vertices_and_bevels(lo,hi,cuts,source_vertices=None):
    import numpy as np
    axial=[]
    for k in range(3):
        n=[0.,0.,0.];n[k]=1.;axial.append((*n,hi[k]));n[k]=-1.;axial.append((*n,-lo[k]))
    p=np.array(axial+list(cuts),dtype=float);n=p[:,:3];d=p[:,3]
    # Closed half-space intersections, including the brush's implicit six sides.
    if source_vertices is None:
        triples=np.array(list(itertools.combinations(range(len(p)),3)))
        a,b,c=n[triples[:,0]],n[triples[:,1]],n[triples[:,2]]
        bc=np.cross(b,c);ca=np.cross(c,a);ab=np.cross(a,b)
        det=np.einsum('ij,ij->i',a,bc);ok=np.abs(det)>1e-8
        t=triples[ok];v=(bc[ok]*d[t[:,0],None]+ca[ok]*d[t[:,1],None]+ab[ok]*d[t[:,2],None])/det[ok,None]
        v=v[np.all(v@n.T<=d+.003,axis=1)]
    else:
        v=np.array(source_vertices,dtype=float)
        if not np.isfinite(v).all() or np.any(v@n.T>d+.08):
            raise ValueError('Source vertices lie outside their convex piece')
    if len(v)<4:raise ValueError('Cannot reconstruct a closed collision brush')
    # Deduplicate only effectively identical intersections, never weld an edge.
    _,unique=np.unique(np.round(v,5),axis=0,return_index=True);v=v[unique]
    active=np.abs(v@n.T-d)<.008
    additions=[];normals=list(n)
    for i,j in itertools.combinations(range(len(p)),2):
        edge_points=v[active[:,i]&active[:,j]]
        if len(edge_points)<2:continue
        edge=edge_points[-1]-edge_points[0]
        if np.linalg.norm(edge)<.005:continue
        for axis in np.eye(3):
            q=np.cross(edge,axis);length=np.linalg.norm(q)
            if length<1e-8:continue
            q/=length
            values=v@q;at=float(edge_points[0]@q)
            if values.max()>at+.01:
                if values.min()<at-.01:continue
                q=-q;values=-values
            if any(np.dot(q,old)>1-1e-8 for old in normals):continue
            # Round outward: extra planes must never remove existing point volume.
            distance=float(values.max())+.012
            fq=np.array(q,dtype='<f4').astype(float)
            distance=max(distance,float((v@fq).max())+.012)
            additions.append((*map(float,fq),float(np.float32(distance))))
            normals.append(fq)
    if len(cuts)+len(additions)>255:raise ValueError('Native bevel plane capacity exceeded')
    if additions and np.any(v@np.array(additions)[:,:3].T>np.array(additions)[:,3]+1e-5):
        raise ValueError('A bevel removes an original collision vertex')
    return v,additions

def clearance_probes(lumps,changed):
    import numpy as np
    from extend_structure_collision import clear_hull
    rows=list(struct.iter_unpack('<3f2BH3fI',lumps[0x5c]));planes=list(struct.iter_unpack('<4f',lumps[1]))
    records=[([r[k]-r[k+6] for k in range(3)],[r[k]+r[k+6] for k in range(3)],planes[1+r[9]:1+r[9]+r[4]]) for r in rows]
    rng=np.random.default_rng(723);probes=[]
    for change in changed:
        i=change['brush'];r=rows[i];lo,hi,allcuts=records[i];old=allcuts[:change['original_cuts']]
        # Keep diagnostic probes inside the playable arena rather than scenery.
        if any(abs(r[k])>9000 for k in range(2)) or not -1800<r[2]<2000:continue
        if max(r[6:9])>600:continue
        n=np.array(allcuts)[:,:3];d=np.array(allcuts)[:,3]
        hmin=np.array([-16,-16,0]);hmax=np.array([16,16,72])
        expanded=d-np.minimum(n*hmin,n*hmax).sum(axis=1)
        starts=rng.uniform(np.array(lo)-hmax,np.array(hi)-hmin,(128,3))
        values=starts@n.T
        good=np.all(values[:,:len(old)]<expanded[:len(old)]-.1,axis=1)&np.any(values[:,len(old):]>expanded[len(old):]+.5,axis=1)
        for point in starts[good]:
            p=point.tolist()
            if clear_hull(p,records) and clear_hull([p[0],p[1],p[2]+.1],records):
                probes.append({'brush_index':i,'start':p,'end':[p[0],p[1],p[2]+.1],
                    'old_face_only_hull_false_positive':True,'all_new_brushes_clear':True});break
        if len(probes)==8:break
    if len(probes)!=8:raise ValueError('Insufficient independent edge clearance probes')
    return probes

def repair_collision(lumps):
    original=list(struct.iter_unpack('<3f2BH3fI',lumps[0x5c]));oldplanes=list(struct.iter_unpack('<4f',lumps[1]))
    brushes=bytearray();planes=bytearray(lumps[1][:16]);offsets=bytearray();properties=bytearray();tex=bytearray()
    changed=[];deferred=[];start=time.monotonic();total=0
    for i,r in enumerate(original):
        lo=[r[k]-r[k+6] for k in range(3)];hi=[r[k]+r[k+6] for k in range(3)];cuts=oldplanes[1+r[9]:1+r[9]+r[4]]
        additions=[]
        if r[4] and r[4]<=26:
            try:
                _,additions=vertices_and_bevels(lo,hi,cuts)
            except ValueError as e:deferred.append({'brush':i,'reason':str(e)})
        elif r[4]>26:deferred.append({'brush':i,'reason':'Complex collider retained; requires a larger topology pass'})
        # Existing side properties and texture vectors are retained verbatim.
        oldside=r[5]*6+r[9];count=6+r[4]
        oldprops=lumps[0x5e][oldside*2:(oldside+count)*2]
        oldtex=lumps[0x5f][oldside*32:(oldside+count)*32]
        first=len(offsets)//2;record=bytearray(lumps[0x5c][i*32:i*32+32]);record[13]=r[4]+len(additions);struct.pack_into('<I',record,28,first)
        brushes.extend(record);properties.extend(oldprops);properties.extend(struct.pack('<'+'H'*len(additions),*([0x4001]*len(additions))))
        tex.extend(oldtex);tex.extend(bytes(32*len(additions)))
        for q in cuts+additions:planes.extend(struct.pack('<4f',*q));offsets.extend(bytes(2))
        if additions:changed.append({'brush':i,'original_cuts':r[4],'bevels':len(additions)});total+=len(additions)
        if i%4000==0:print(f'Collision edge planes {i}/{len(original)}, {total} added',flush=True)
    report={'brushes':len(original),'brushes_with_bevels_added':len(changed),'edge_planes_added':total,
        'point_collision_volume_preserved':True,'brush_origins_and_extents_byte_preserved':True,
        'discard_flag':hex(0x4000),'complex_brushes_deferred':deferred,'changed_brushes':changed,
        'elapsed_seconds':time.monotonic()-start,'client_movement_verified':False}
    return {1:planes,0x5c:brushes,0x5d:offsets,0x5e:properties,0x5f:tex},report

if __name__=='__main__':
    source=ROOT/'output/phase-runner/preview-index-repaired/mp_phase_runner_preview.bsp'
    changes,report=repair_collision(read_lumps(source,(1,0x5c,0x5d,0x5e,0x5f)))
    report['clearance_probes']=clearance_probes(changes,report['changed_brushes'])
    out=ROOT/'output/phase-runner/hull-edge-repair';out.mkdir(exist_ok=True)
    for i,p in changes.items():(out/f'{i:02x}.bin').write_bytes(p)
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('complex_brushes_deferred','changed_brushes')},indent=2))
