"""Native open TF2 cells with camera-safe local geometry and conservative portals.

No Apex occlusion, draw geometry, lights or collider data are reused or edited.
Each cell protects its own references from projected access-path clipping when
the camera is inside the playable part of that cell. Other cells still receive
their full shared-face portal window, never an invented door/pipe occluder.
"""
import bisect, collections, hashlib, json, math, shutil, struct
from pathlib import Path
from compact_preview_bsp import compact
from repair_preview_index_padding import read_lumps, validate_index_padding
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'output/phase-runner/preview-interior-lighting/mp_phase_runner_preview.bsp'
TARGET = ROOT/'output/phase-runner/preview-local-visibility/mp_phase_runner_preview.bsp'
CUTS = (-3200., 0., 3200.)
LIMIT = 32760.
CAMERA_MIN = (-12288., -12288., -4096.)
CAMERA_MAX = (12288., 12288., 4096.)


def make_tree(boxes, leaf_size=64):
    nodes = []
    refs = []
    objects = bytearray()
    def emit(index, ids):
        lo = tuple(min(boxes[i][0][k] for i in ids) for k in range(3))
        hi = tuple(max(boxes[i][1][k] for i in ids) for k in range(3))
        first = len(refs)
        if len(ids) <= leaf_size:
            refs.extend(ids)
            for i in ids:
                objects.extend(struct.pack('<3fI3fI', *boxes[i][0], 0, *boxes[i][1], 0))
            nodes[index] = struct.pack('<3f2BH3f2H', *lo, 0, len(ids), len(ids), *hi, 0, first)
        else:
            axis = max(range(3), key=lambda k: max(sum(boxes[i][j][k] for j in (0,1)) for i in ids)
                       - min(sum(boxes[i][j][k] for j in (0,1)) for i in ids))
            ids.sort(key=lambda i: sum(boxes[i][j][axis] for j in (0,1)))
            child = len(nodes)
            nodes.extend([None, None])
            nodes[index] = struct.pack('<3f2BH3f2H', *lo, 2, 0, len(ids), *hi, child, first)
            middle = len(ids)//2
            emit(child, ids[:middle]); emit(child+1, ids[middle:])
    nodes.append(None)
    emit(0, list(range(len(boxes))))
    return nodes, refs, objects


def build_cells(bounds, original_planes, cuts=CUTS, protect_local=True):
    if not cuts or tuple(sorted(set(cuts))) != tuple(cuts):
        raise ValueError('Cuts must be strictly increasing')
    if cuts[0] <= CAMERA_MIN[0] or cuts[-1] >= CAMERA_MAX[0]:
        raise ValueError('Partitions outside protected camera domain')
    ms = list(struct.iter_unpack('<8f', bounds))
    if not ms or len(ms) > 65535: raise ValueError('Native mesh-reference capacity exceeded')
    boxes = [(tuple(m[k]-m[k+4]-1 for k in range(3)),
              tuple(m[k]+m[k+4]+1 for k in range(3))) for m in ms]
    if any(not all(math.isfinite(v) for v in lo+hi) or any(lo[k]>hi[k] for k in range(3)) for lo,hi in boxes):
        raise ValueError('Invalid mesh bounds')
    n = len(cuts)+1; count = n*n; edges = (-LIMIT, *cuts, LIMIT)
    domains = [((edges[x],edges[y],-LIMIT),(edges[x+1],edges[y+1],LIMIT))
               for y in range(n) for x in range(n)]
    nodes = [None]*count; refs=[]; objects=bytearray(); memberships=[]; camera_boxes=[]
    for cell,(low,high) in enumerate(domains):
        x,y = cell%n,cell//n
        # Infinite outer partition membership retains the entire backdrop.
        ids = [i for i,(lo,hi) in enumerate(boxes)
               if (x==0 or hi[0]>=low[0]) and (x==n-1 or lo[0]<=high[0])
               and (y==0 or hi[1]>=low[1]) and (y==n-1 or lo[1]<=high[1])]
        if not ids: raise ValueError('Empty visibility cell: choose fewer partitions')
        memberships.append(ids)
        clo = tuple(max(low[k],CAMERA_MIN[k]) for k in range(3))
        chi = tuple(min(high[k],CAMERA_MAX[k]) for k in range(3))
        camera_boxes.append((clo,chi))
        local = [(tuple(min(boxes[i][0][k],clo[k]) for k in range(3)),
                  tuple(max(boxes[i][1][k],chi[k]) for k in range(3)))
                 if protect_local else boxes[i] for i in ids]
        tree,localrefs,obs = make_tree(local)
        start_node=len(nodes); start_ref=len(refs)
        for i,row in enumerate(tree):
            row=list(struct.unpack('<3f2BH3f2H',row))
            if row[3]: row[9] += start_node-1
            row[10] += start_ref
            packed=struct.pack('<3f2BH3f2H',*row)
            if i==0: nodes[cell]=packed
            else: nodes.append(packed)
        refs.extend(ids[i] for i in localrefs); objects.extend(obs)
    if max(len(refs),len(nodes))>65535: raise ValueError('Native cell forest capacity exceeded')
    planes = bytearray(original_planes); plane_ids={}
    def plane(axis,distance):
        key=(axis,distance)
        if key not in plane_ids:
            normal=[0.,0.,0.];normal[axis]=1.;plane_ids[key]=len(planes)//16
            planes.extend(struct.pack('<4f',*normal,distance))
        return plane_ids[key]
    # Native front/back children are consecutive, front child first.
    bsp=[None]
    def split(at,xlo,xhi,ylo,yhi):
        if xhi-xlo==1 and yhi-ylo==1:
            bsp[at]=(-1,ylo*n+xlo);return
        axis=0 if xhi-xlo>=yhi-ylo else 1
        middle=((xlo+xhi)//2 if axis==0 else (ylo+yhi)//2)
        first=len(bsp);bsp.extend([None,None]);bsp[at]=(plane(axis,cuts[middle-1]),first)
        if axis==0:
            split(first,middle,xhi,ylo,yhi);split(first+1,xlo,middle,ylo,yhi)
        else:
            split(first,xlo,xhi,middle,yhi);split(first+1,xlo,xhi,ylo,middle)
    split(0,0,n,0,n)
    vertices=[(0.,0.,0.)];pedges=[];vrefs=[];erefs=[];bycell=[[] for _ in domains]
    def face(axis,distance,lo,hi):
        other=[k for k in range(3) if k!=axis];start=len(vertices);pts=[]
        for u,v in ((0,0),(1,0),(1,1),(0,1)):
            p=[0.,0.,0.];p[axis]=distance
            p[other[0]]=(lo,hi)[u][other[0]];p[other[1]]=(lo,hi)[v][other[1]];pts.append(tuple(p))
        from build_preview_source import cross,subtract
        if cross(subtract(pts[1],pts[0]),subtract(pts[2],pts[0]))[axis]<0:pts.reverse()
        vertices.extend(pts);first=len(vrefs)
        for i in range(4):
            ei=len(pedges);pedges.append((start+i,start+(i+1)%4));vrefs.append(start+i);erefs.append(ei*2)
        return first
    for cell,(lo,hi) in enumerate(domains):
        x,y=cell%n,cell//n
        for axis,valid,other in ((0,x+1<n,cell+1),(1,y+1<n,cell+n)):
            if not valid:continue
            low=tuple(max(lo[k],domains[other][0][k]) for k in range(3))
            high=tuple(min(hi[k],domains[other][1][k]) for k in range(3))
            first=face(axis,hi[axis],low,high);pl=plane(axis,hi[axis])
            bycell[cell].append((0,0,4,0,first,other,pl))
            bycell[other].append((1,0,4,0,first,cell,pl))
        for axis in range(3):
            for distance in (lo[axis],hi[axis]):
                if abs(distance)!=LIMIT:continue
                first=face(axis,distance,lo,hi);pl=plane(axis,distance)
                bycell[cell].append((int(distance<0),1,4,0,first,count+1,pl))
    cells=bytearray();portals=[]
    for ps in bycell:
        cells.extend(struct.pack('<2H2h',len(ps),len(portals),1,-1));portals.extend(ps)
    vedges=bytearray(b'\xff'*4*len(vertices))
    for i,(a,b) in enumerate(pedges):
        for v in (a,b):
            offset=v*4;slot=0 if struct.unpack_from('<H',vedges,offset)[0]==65535 else 2
            struct.pack_into('<H',vedges,offset+slot,i)
    changes={1:planes,0x6a:b''.join(struct.pack('<iI',*r) for r in bsp),0x6b:cells,
        0x6c:b''.join(struct.pack('<4B2HI',*p) for p in portals),
        0x6d:b''.join(struct.pack('<3f',*v) for v in vertices),0x6e:b''.join(struct.pack('<2H',*e) for e in pedges),
        0x6f:vedges,0x70:struct.pack('<'+'H'*len(vrefs),*vrefs),0x71:struct.pack('<'+'H'*len(erefs),*erefs),
        0x72:b'',0x73:b'',0x74:bytes(8*len(pedges)),0x75:b'',0x76:b'',
        0x77:b''.join(nodes),0x78:struct.pack('<'+'H'*len(refs),*refs),0x79:objects}
    proof=validate(changes,bounds,cuts,protect_local)
    proof.update(camera_min=CAMERA_MIN,camera_max=CAMERA_MAX,cuts=cuts,
                 local_geometry_protected=protect_local,membership_counts=[len(ids) for ids in memberships],
                 original_apex_occlusion_used=False,opaque_occluders=0)
    return changes,proof


def locate(lumps,point):
    planes=list(struct.iter_unpack('<4f',lumps[1]));bsp=list(struct.iter_unpack('<iI',lumps[0x6a]))
    at=0;seen=set()
    while True:
        if at in seen or not 0<=at<len(bsp):raise ValueError('Cell BSP graph invalid')
        seen.add(at);pl,first=bsp[at]
        if pl==-1:return first
        q=planes[pl];at=first+int(sum(q[k]*point[k] for k in range(3))<q[3])


def validate(l,bounds,cuts=CUTS,protect_local=True):
    cells=list(struct.iter_unpack('<2H2h',l[0x6b]));ns=list(struct.iter_unpack('<3f2BH3f2H',l[0x77]))
    refs=list(struct.unpack('<'+'H'*(len(l[0x78])//2),l[0x78]));obs=list(struct.iter_unpack('<3fI3fI',l[0x79]))
    ms=list(struct.iter_unpack('<8f',bounds));ps=list(struct.iter_unpack('<4B2HI',l[0x6c]))
    planes=list(struct.iter_unpack('<4f',l[1]));vr=list(struct.unpack('<'+'H'*(len(l[0x70])//2),l[0x70]))
    er=list(struct.unpack('<'+'H'*(len(l[0x71])//2),l[0x71]));verts=list(struct.iter_unpack('<3f',l[0x6d]))
    edges=list(struct.iter_unpack('<2H',l[0x6e]));n=len(cuts)+1;seen=set();covered=set();links={};cursor=0
    if len(cells)!=n*n or len(refs)!=len(obs):raise ValueError('Native visibility counts disagree')
    def enclosed(lo,hi,blo,bhi):return all(lo[k]<=blo[k]+.05 and hi[k]>=bhi[k]-.05 for k in range(3))
    def walk(at,owner):
        if at in seen or not 0<=at<len(ns):raise ValueError('Visibility forest graph invalid')
        seen.add(at);r=ns[at];lo,hi=r[:3],r[6:9];end=r[10]+r[4]
        if r[10]+r[5]>len(refs):raise ValueError('Reference overflow')
        for j in range(r[10],end):
            mi=refs[j]
            if mi>=len(ms):raise ValueError('Mesh reference overflow')
            covered.add(mi);ob=obs[j];m=ms[mi]
            if not enclosed(ob[:3],ob[4:7],tuple(m[k]-m[k+4] for k in range(3)),tuple(m[k]+m[k+4] for k in range(3))):
                raise ValueError('Object excludes draw geometry')
            if not enclosed(lo,hi,ob[:3],ob[4:7]):raise ValueError('Node excludes object')
            if protect_local:
                limits=(-LIMIT,*cuts,LIMIT);x,y=owner%n,owner//n
                clo=(max(limits[x],CAMERA_MIN[0]),max(limits[y],CAMERA_MIN[1]),CAMERA_MIN[2])
                chi=(min(limits[x+1],CAMERA_MAX[0]),min(limits[y+1],CAMERA_MAX[1]),CAMERA_MAX[2])
                if not enclosed(ob[:3],ob[4:7],clo,chi):raise ValueError('Local camera coverage missing')
        for ci in range(r[9],r[9]+r[3]):
            if ns[ci][10]!=end:raise ValueError('Noncontiguous subtree range')
            if not enclosed(lo,hi,ns[ci][:3],ns[ci][6:9]):raise ValueError('Node excludes child')
            end+=walk(ci,owner)
        if end!=r[10]+r[5]:raise ValueError('Subtree count mismatch')
        return r[5]
    portal_cursor=0
    for cell,c in enumerate(cells):
        if ns[cell][10]!=cursor:raise ValueError('Root reference order mismatch')
        cursor+=walk(cell,cell)
        if c[1]!=portal_cursor or c[1]+c[0]>len(ps):raise ValueError('Portal range mismatch')
        portal_cursor+=c[0]
        for p in ps[c[1]:c[1]+c[0]]:
            if p[2]!=4 or p[3] or p[4]+p[2]>len(vr) or p[4]+p[2]>len(er) or p[6]>=len(planes):raise ValueError('Invalid portal record')
            q=planes[p[6]];pv=[]
            for j in range(p[4],p[4]+p[2]):
                v=verts[vr[j]];pv.append(v)
                if abs(sum(q[k]*v[k] for k in range(3))-q[3])>.05:raise ValueError('Portal off plane')
                if er[j]&1 or edges[er[j]>>1][0]!=vr[j]:raise ValueError('Portal edge/vertex winding mismatch')
                if edges[er[j]>>1][1]!=vr[p[4]+(j-p[4]+1)%p[2]]:raise ValueError('Portal edge not connected')
            from build_preview_source import cross,subtract
            normal=cross(subtract(pv[1],pv[0]),subtract(pv[2],pv[0]))
            if sum(normal[k]*q[k] for k in range(3))<=0:raise ValueError('Portal winding differs from plane')
            if p[1]==0:
                if p[5]>=len(cells):raise ValueError('Portal destination invalid')
                links[(cell,p[5])]=p
            elif p[1]!=1 or p[5]!=len(cells)+1:raise ValueError('Sky destination invalid')
    for (a,b),p in links.items():
        other=links.get((b,a))
        if not other or other[0]==p[0] or other[4:]!=(p[4],a,p[6]):raise ValueError('Reciprocal portal mismatch')
    if len(seen)!=len(ns) or cursor!=len(refs) or portal_cursor!=len(ps) or len(covered)!=len(ms):raise ValueError('Unreachable visibility data')
    # Exhaustive grid lookup, including far-outside camera positions and boundaries.
    samples=(-100000.,*tuple(x+d for x in cuts for d in (-.1,0.,.1)),100000.)
    for x in samples:
        for y in samples:
            expected=bisect.bisect_right(cuts,y)*n+bisect.bisect_right(cuts,x)
            if locate(l,(x,y,-1200))!=expected:raise ValueError('Cell camera lookup differs')
    queue=collections.deque(range(len(cells)));peak=len(queue)
    while queue:
        r=ns[queue.popleft()];queue.extend(range(r[9],r[9]+r[3]));peak=max(peak,len(queue))
    if peak>=1024 or len(links)+len(cells)>=8192:raise ValueError('Native visibility queue capacity exceeded')
    return dict(cells=len(cells),directed_open_portals=len(links),sky_portals=sum(p[1]==1 for p in ps),
        nodes=len(ns),object_references=len(refs),unique_meshes=len(ms),maximum_pending_nodes=peak,
        all_meshes_reachable=True,reciprocal_portals_verified=True,portal_winding_verified=True,
        boundary_camera_lookup_verified=True,contiguous_subtree_ranges_verified=True)


def build():
    l=read_lumps(SOURCE,(1,0x50,0x51,0x4f,0x52))
    padding=validate_index_padding(l[0x50],l[0x4f],l[0x52]);budget=audit(SOURCE)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Insufficient renderer headroom')
    changes,proof=build_cells(l[0x51],l[1]);compaction=compact(SOURCE,TARGET,changes)
    status=json.loads(SOURCE.with_name('source-build.json').read_text())
    status['local_visibility_rebuild']=dict(version='0.1.35',**proof,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        index_padding=padding,draw_budget=budget,compaction=compaction,
        collision_plane_prefix_byte_preserved=True,draw_geometry_materials_lighting_walkways_byte_preserved=True,
        prior_client_lighting_confirmed='0.1.34',client_rendering_verified=False,
        limitation='Open spatial portals with conservative local camera bounds. They avoid opaque blockers; '
          'client testing must establish rendering and performance. Cell visibility is independent of resident texture mip loading.')
    status['visibility_rebuild']=proof;status['final_compaction']=compaction
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    TARGET.with_name('local-visibility-audit.json').write_text(json.dumps(status['local_visibility_rebuild'],indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    print(json.dumps(status['local_visibility_rebuild'],indent=2),flush=True)

if __name__=='__main__':build()
