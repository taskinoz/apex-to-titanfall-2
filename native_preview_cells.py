"""Generate conservative TF2 cells and open portals, independently of Apex VIS.

Record layouts and the roots-first AABB forest follow native Homestead/Colony.
Outdoor partitions are connected across their whole shared face. They are not
occluders, and do not pretend that decorative pipes are visibility blockers.
"""
import json, math, shutil, struct
from pathlib import Path
from preview_visibility import build_visibility
from compact_preview_bsp import compact

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT/'output/phase-runner'

def make_cells(bounds, planes, limit=32760.):
    meshes = list(struct.iter_unpack('<8f', bounds))
    boxes = [(tuple(r[k]-r[k+4]-1 for k in range(3)),
              tuple(r[k]+r[k+4]+1 for k in range(3))) for r in meshes]
    # Cell order: SW, SE, NW, NE. Boundaries extend beyond the playable map.
    domains = [((-limit if not c%2 else 0., -limit if c<2 else 0., -limit),
                (0. if not c%2 else limit, 0. if c<2 else limit, limit)) for c in range(4)]
    nodes = [None]*4; refs=[]; objects=bytearray(); memberships=[]
    for cell, (low, high) in enumerate(domains):
        ids = [i for i,(lo,hi) in enumerate(boxes)
               if (hi[0]>=0 if cell%2 else lo[0]<=0)
               and (hi[1]>=0 if cell>=2 else lo[1]<=0)]
        # Geometry crossing a partition is referenced in both cells. Bounds
        # stay geometric, including distant backdrop geometry beyond domains.
        memberships.append(ids)
        local = b''.join(bounds[i*32:i*32+32] for i in ids)
        tree, localrefs, obs = build_visibility(local, leaf_size=16)
        entries = list(struct.iter_unpack('<3f2BH3f2H', tree))
        first_node=len(nodes); first_ref=len(refs)
        for i,n in enumerate(entries):
            n=list(n)
            if n[3]: n[9]=first_node+n[9]-1
            n[10]+=first_ref
            packed=struct.pack('<3f2BH3f2H',*n)
            if i==0:nodes[cell]=packed
            else:nodes.append(packed)
        refs.extend(ids[i[0]] for i in struct.iter_unpack('<H',localrefs));objects.extend(obs)
    if len(refs)>65535 or len(nodes)>65535:raise ValueError('Native visibility capacity exceeded')
    plane_buffer=bytearray(planes)
    def add_plane(axis,distance):
        n=[0.,0.,0.];n[axis]=1.;at=len(plane_buffer)//16
        plane_buffer.extend(struct.pack('<4f',*n,distance));return at
    px=add_plane(0,0.);py=add_plane(1,0.)
    # Front child precedes back child, with consecutive siblings, as in R2.
    bsp=struct.pack('<iI',px,1)+struct.pack('<iI',py,3)+struct.pack('<iI',py,5)
    bsp+=b''.join(struct.pack('<iI',-1,c) for c in (3,1,2,0))
    vertices=[(0.,0.,0.)];edges=[];vrefs=[];erefs=[];portals=[];bycell=[[] for _ in range(4)]
    def face(axis,distance,lo,hi):
        other=[k for k in range(3) if k!=axis];start=len(vertices)
        pts=[]
        for u,v in ((0,0),(1,0),(1,1),(0,1)):
            p=[0.,0.,0.];p[axis]=distance;p[other[0]]=(lo,hi)[u][other[0]];p[other[1]]=(lo,hi)[v][other[1]];pts.append(tuple(p))
        # Positive geometric normal along the plane axis.
        from build_preview_source import cross,subtract
        if cross(subtract(pts[1],pts[0]),subtract(pts[2],pts[0]))[axis]<0:pts.reverse()
        vertices.extend(pts);first=len(vrefs)
        for i in range(4):
            ei=len(edges);edges.append((start+i,start+(i+1)%4));vrefs.append(start+i);erefs.append(ei*2)
        return first
    for a,b,axis,pl in ((0,1,0,px),(2,3,0,px),(0,2,1,py),(1,3,1,py)):
        lo=tuple(max(domains[a][0][k],domains[b][0][k]) for k in range(3))
        hi=tuple(min(domains[a][1][k],domains[b][1][k]) for k in range(3))
        first=face(axis,0.,lo,hi)
        bycell[a].append((0,0,4,0,first,b,pl));bycell[b].append((1,0,4,0,first,a,pl))
    cells=bytearray()
    for cell,(lo,hi) in enumerate(domains):
        # Native sky portals on outside faces. No opaque portal masks/occluders.
        for axis in range(3):
            for distance in (lo[axis],hi[axis]):
                if distance==0.:continue
                first=face(axis,distance,lo,hi);pl=add_plane(axis,distance)
                bycell[cell].append((int(distance<0),1,4,0,first,5,pl))
        cells.extend(struct.pack('<2H2h',len(bycell[cell]),len(portals),1,-1));portals.extend(bycell[cell])
    vertex_edges=bytearray(b'\xff'*4*len(vertices))
    for i,(a,b) in enumerate(edges):
        for v in (a,b):
            at=v*4;slot=0 if struct.unpack_from('<H',vertex_edges,at)[0]==65535 else 2
            struct.pack_into('<H',vertex_edges,at+slot,i)
    result={1:plane_buffer,0x6a:bsp,0x6b:cells,0x6c:b''.join(struct.pack('<4B2HI',*p) for p in portals),
        0x6d:b''.join(struct.pack('<3f',*p) for p in vertices),0x6e:b''.join(struct.pack('<2H',*e) for e in edges),
        0x6f:vertex_edges,0x70:struct.pack('<'+'H'*len(vrefs),*vrefs),0x71:struct.pack('<'+'H'*len(erefs),*erefs),
        0x72:b'',0x73:b'',0x74:bytes(8*len(edges)),0x75:b'',0x76:b'',
        0x77:b''.join(nodes),0x78:struct.pack('<'+'H'*len(refs),*refs),0x79:objects}
    proof=validate_cells(result,bounds)
    return result,proof

def validate_cells(lumps,bounds):
    cells=list(struct.iter_unpack('<2H2h',lumps[0x6b]));ns=list(struct.iter_unpack('<3f2BH3f2H',lumps[0x77]));rs=list(struct.iter_unpack('<H',lumps[0x78]));obs=list(struct.iter_unpack('<3fI3fI',lumps[0x79]));ms=list(struct.iter_unpack('<8f',bounds));ps=list(struct.iter_unpack('<4B2HI',lumps[0x6c]));planes=list(struct.iter_unpack('<4f',lumps[1]));bsp=list(struct.iter_unpack('<iI',lumps[0x6a]));vertices=list(struct.iter_unpack('<3f',lumps[0x6d]));vr=list(struct.iter_unpack('<H',lumps[0x70]));er=list(struct.iter_unpack('<H',lumps[0x71]));edges=list(struct.iter_unpack('<2H',lumps[0x6e]));seen=set();covered=set();cursor=0
    def walk(i):
        if i in seen or not 0<=i<len(ns):raise ValueError('Invalid cell AABB graph')
        seen.add(i);n=ns[i];count=n[4];end=n[10]+count
        if n[10]+n[5]>len(rs):raise ValueError('Cell object range overflow')
        for at in range(n[10],end):
            mi=rs[at][0]
            if mi>=len(ms):raise ValueError('Cell mesh reference overflow')
            m=ms[mi];ob=obs[at];covered.add(mi)
            if any(ob[k]>m[k]-m[k+4]+.05 or ob[k+4]<m[k]+m[k+4]-.05 for k in range(3)):raise ValueError('Object excludes mesh')
            if any(n[k]>ob[k]+.05 or n[k+6]<ob[k+4]-.05 for k in range(3)):raise ValueError('Node excludes object')
        for ci in range(n[9],n[9]+n[3]):
            if ns[ci][10]!=end:raise ValueError('Noncontiguous cell subtree')
            child=ns[ci]
            if any(n[k]>child[k]+.05 or n[k+6]<child[k+6]-.05 for k in range(3)):raise ValueError('Node excludes child')
            end+=walk(ci)
        if end!=n[10]+n[5]:raise ValueError('Cell subtree count differs')
        return n[5]
    links=set()
    for ci,c in enumerate(cells):
        if ns[ci][10]!=cursor:raise ValueError('Cell root reference order differs')
        cursor+=walk(ci)
        for p in ps[c[1]:c[1]+c[0]]:
            if p[4]+p[2]>len(vr) or p[4]+p[2]>len(er) or p[6]>=len(planes):raise ValueError('Portal references invalid')
            q=planes[p[6]]
            for j in range(p[4],p[4]+p[2]):
                v=vertices[vr[j][0]]
                if abs(sum(q[k]*v[k] for k in range(3))-q[3])>.1:raise ValueError('Portal off its plane')
                e=er[j][0]>>1
                if e>=len(edges) or any(vi>=len(vertices) for vi in edges[e]):raise ValueError('Portal edge invalid')
            if p[1]==0:
                if p[5]>=len(cells):raise ValueError('Portal destination invalid')
                links.add((ci,p[5]))
            elif p[1]!=1 or p[5]!=len(cells)+1:raise ValueError('Sky portal invalid')
    if len(seen)!=len(ns) or cursor!=len(rs) or len(covered)!=len(ms):raise ValueError('Unreachable visibility geometry')
    if any((b,a) not in links for a,b in links):raise ValueError('One-way cell connection')
    def locate(point):
        at=0;visited=set()
        while bsp[at][0]!=-1:
            if at in visited:raise ValueError('Cell BSP cycle')
            visited.add(at);pl,first=bsp[at];q=planes[pl];at=first+int(sum(q[k]*point[k] for k in range(3))<q[3])
        return bsp[at][1]
    for c,p in enumerate(((-100,-100,0),(100,-100,0),(-100,100,0),(100,100,0))):
        if locate(p)!=c:raise ValueError('Cell lookup differs')
    return dict(cells=len(cells),directed_open_portals=len(links),sky_portals=sum(p[1]==1 for p in ps),
        nodes=len(ns),object_references=len(rs),all_meshes_reachable=True,reciprocal_connections_verified=True,
        original_apex_visibility_used=False,occlusion_meshes=0,client_rendering_verified=False)

def build(source=None):
    source=Path(source or PROJECT/'preview-structure-physics/mp_phase_runner_preview.bsp')
    out=PROJECT/'preview-native-cells/mp_phase_runner_preview.bsp'
    with source.open('rb') as f:
        h=f.read(2064)
        def lump(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
        bounds,planes,meshes,indices=lump(0x51),lump(1),bytearray(lump(0x50)),lump(0x4f)
    # Each spatial section must describe its actual local index range.
    corrected=0
    for at in range(0,len(meshes),28):
        first,count,lo,span=struct.unpack_from('<I3H',meshes,at)
        actual=struct.unpack_from('<'+'H'*(count*3),indices,first*2)
        a,b=min(actual),max(actual)
        # Native R2 stores minimum local vertex and (maximum - minimum),
        # verified for every mesh in Homestead and Colony, not an absolute max.
        if (lo,span)!=(a,b-a):corrected+=1;struct.pack_into('<2H',meshes,at+6,a,b-a)
    replacements,proof=make_cells(bounds,planes);replacements[0x50]=meshes
    report=compact(source,out,replacements);status=json.loads(source.with_name('source-build.json').read_text())
    status['native_cell_rebuild']=dict(proof,local_vertex_ranges_corrected=corrected,
        geometry_materials_lighting_and_collision_preserved=True,
        limitation='Conservative outdoor cells with full-face open connections; GPU behavior needs a client check. This is not occlusion optimization.')
    status['final_compaction']=report;out.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,out.parent/p.name)
    shutil.copy2(source.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
    print(json.dumps(status['native_cell_rebuild'],indent=2))

if __name__=='__main__':build()
