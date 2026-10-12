"""Build and validate a native TF2 visibility tree with spatially bounded leaves."""
import math,struct

def build_visibility(bounds,leaf_size=32):
    mesh_bounds=list(struct.iter_unpack('<8f',bounds))
    boxes=[(tuple(r[k]-r[k+4]-1 for k in range(3)),tuple(r[k]+r[k+4]+1 for k in range(3))) for r in mesh_bounds]
    refs=[];nodes=[];objects=bytearray()
    def reserve(ids):
        idx=len(nodes);nodes.append(None);return idx,ids
    def emit(idx,ids):
        low=tuple(min(boxes[i][0][k] for i in ids) for k in range(3));high=tuple(max(boxes[i][1][k] for i in ids) for k in range(3))
        if len(ids)<=leaf_size:
            first=len(refs);refs.extend(ids)
            for i in ids:objects.extend(struct.pack('<3fI3fI',*boxes[i][0],0,*boxes[i][1],0))
            nodes[idx]=struct.pack('<3f2BH3f2H',*low,0,len(ids),len(ids),*high,0,first)
        else:
            axis=max(range(3),key=lambda k:max(mesh_bounds[i][k] for i in ids)-min(mesh_bounds[i][k] for i in ids))
            ids.sort(key=lambda i:mesh_bounds[i][axis]);mid=len(ids)//2
            left=reserve(ids[:mid]);right=reserve(ids[mid:])
            # Native Homestead/Colony branches point to the beginning of their
            # entire contiguous subtree, including when they own no references.
            first=len(refs)
            nodes[idx]=struct.pack('<3f2BH3f2H',*low,2,0,len(ids),*high,left[0],first)
            emit(*left);emit(*right)
    if not boxes:raise ValueError('No visibility objects')
    if len(boxes)>65535:raise ValueError('Native reference count exceeded')
    emit(*reserve(list(range(len(boxes)))))
    result=(b''.join(nodes),struct.pack('<'+'H'*len(refs),*refs),bytes(objects))
    validate_visibility(*result,bounds)
    return result

def validate_visibility(nodes,refs,objects,bounds):
    ns=list(struct.iter_unpack('<3f2BH3f2H',nodes));rs=list(struct.unpack('<'+'H'*(len(refs)//2),refs));obs=list(struct.iter_unpack('<3fI3fI',objects));ms=list(struct.iter_unpack('<8f',bounds))
    if len(obs)!=len(rs):raise ValueError('Object bounds count differs')
    seen=set();seen_refs=[]
    def encloses(lo,hi,blo,bhi):return all(lo[k]<=blo[k]+.05 and hi[k]>=bhi[k]-.05 for k in range(3))
    def walk(i,parent=None):
        if i in seen or not 0<=i<len(ns):raise ValueError('Invalid visibility child graph')
        seen.add(i);n=ns[i];lo,hi=n[:3],n[6:9];children,count,total,first,ref=n[3],n[4],n[5],n[9],n[10]
        if not all(math.isfinite(x) for x in lo+hi) or any(lo[k]>hi[k] for k in range(3)):raise ValueError('Invalid node bounds')
        if parent and not encloses(*parent,lo,hi):raise ValueError('Parent excludes child bounds')
        if ref+total>len(rs):raise ValueError('Subtree exceeds object references')
        own=rs[ref:ref+count];seen_refs.extend(range(ref,ref+count))
        for at,mesh in zip(range(ref,ref+count),own):
            if not 0<=mesh<len(ms):raise ValueError('Invalid visibility mesh')
            ob=obs[at];m=ms[mesh];mlo=tuple(m[k]-m[k+4] for k in range(3));mhi=tuple(m[k]+m[k+4] for k in range(3))
            if not encloses(lo,hi,ob[:3],ob[4:7]) or not encloses(ob[:3],ob[4:7],mlo,mhi):raise ValueError('Visibility bounds exclude geometry')
        actual=count
        cursor=ref+count
        for c in range(first,first+children):
            if not 0<=c<len(ns):raise ValueError('Invalid visibility child graph')
            if ns[c][10]!=cursor:raise ValueError('Subtree object references are not contiguous')
            child_count=walk(c,(lo,hi))
            actual+=child_count;cursor+=child_count
        if actual!=total:raise ValueError('Subtree count differs')
        return actual
    walk(0)
    if len(seen)!=len(ns) or sorted(seen_refs)!=list(range(len(rs))) or sorted(rs)!=list(range(len(ms))):raise ValueError('Visibility omits or duplicates meshes')
    return dict(nodes=len(ns),references=len(rs),reachable_meshes=len(ms),all_parent_and_object_bounds_verified=True,contiguous_subtree_ranges_verified=True)
