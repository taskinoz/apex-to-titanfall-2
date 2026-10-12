"""Merge adjacent coplanar collision polygons without filling gaps or concavities."""
from pathlib import Path
from build_preview_source import cross, subtract, TRANSLATION
import math, json

def polygons(path):
    points=[]
    for line in Path(path).open():
        if line.startswith('g '): points=[]
        elif line.startswith('v '): points.append(subtract(tuple(map(float,line.split()[1:])),TRANSLATION))
        elif line.startswith('f '):
            # Merging can leave nearly collinear vertices along a long edge.
            # Start at the strongest corner so the prism's first plane is stable.
            start=max(range(len(points)),key=lambda i:sum(v*v for v in cross(
                subtract(points[(i+1)%len(points)],points[i]),
                subtract(points[(i+2)%len(points)],points[i]))))
            yield points[start:]+points[:start]

def merge(path):
    polys={}; edges={}; normals={}; next_id=0; merged=0
    def key(p): return tuple(round(v,3) for v in p)
    def edge(a,b): return tuple(sorted((key(a),key(b))))
    def remove(i):
        p=polys.pop(i)
        for a,b in zip(p,p[1:]+p[:1]):
            k=edge(a,b); edges[k].discard(i)
            if not edges[k]: del edges[k]
        normals.pop(i)
    def add(p,n):
        nonlocal next_id
        i=next_id; next_id+=1; polys[i]=p; normals[i]=n
        for a,b in zip(p,p[1:]+p[:1]): edges.setdefault(edge(a,b),set()).add(i)
        return i
    def combine(a,b,n):
        # Cancel shared undirected edges, then walk the remaining boundary.
        links={}; both={}
        for p in (a,b):
            for u,v in zip(p,p[1:]+p[:1]):
                k=edge(u,v)
                if k in both: del both[k]
                else: both[k]=(u,v)
        if len(both)>16 or len(both)<3: return None
        for u,v in both.values():
            links.setdefault(key(u),[]).append(v); links.setdefault(key(v),[]).append(u)
        if any(len(v)!=2 for v in links.values()): return None
        start=next(iter(both.values()))[0]; out=[start]; prev=None; cur=start
        while True:
            options=links[key(cur)]; nxt=options[0] if prev is None or key(options[0])!=key(prev) else options[1]
            if key(nxt)==key(start): break
            out.append(nxt); prev,cur=cur,nxt
            if len(out)>len(both): return None
        if len(out)!=len(both): return None
        signs=[]
        for i,p in enumerate(out):
            c=cross(subtract(out[(i+1)%len(out)],p),subtract(out[(i+2)%len(out)],out[(i+1)%len(out)]))
            v=sum(c[k]*n[k] for k in range(3))
            if abs(v)>0.001: signs.append(v>0)
        if not signs or any(v!=signs[0] for v in signs): return None
        # Drop collinear vertices so subsequent prisms have few side planes.
        result=[p for i,p in enumerate(out) if sum(v*v for v in cross(subtract(p,out[i-1]),subtract(out[(i+1)%len(out)],p)))>1e-6]
        def area(poly):
            origin=poly[0]; vector=[0.,0.,0.]
            for u,v in zip(poly,poly[1:]+poly[:1]):
                c=cross(subtract(u,origin),subtract(v,origin))
                for k in range(3): vector[k]+=c[k]
            return math.sqrt(sum(v*v for v in vector))*.5
        expected=area(a)+area(b)
        if abs(area(result)-expected)>max(.001,expected*1e-8): return None
        return result
    for p in polygons(path):
        if any(abs(v)>32000 for point in p for v in point): continue
        n=cross(subtract(p[1],p[0]),subtract(p[2],p[0])); mag=math.sqrt(sum(v*v for v in n))
        if mag<.01: continue
        n=tuple(v/mag for v in n)
        changed=True
        while changed:
            changed=False
            candidates=set()
            for a,b in zip(p,p[1:]+p[:1]): candidates.update(edges.get(edge(a,b),()))
            for i in sorted(candidates):
                nn=normals[i]
                if abs(sum(n[k]*nn[k] for k in range(3)))<.999999: continue
                if any(abs(sum(n[k]*(q[k]-p[0][k]) for k in range(3)))>.01 for q in polys[i]): continue
                union=combine(p,polys[i],n)
                if union:
                    remove(i); p=union; merged+=1; changed=True; break
        add(p,n)
    return list(polys.values()), merged
if __name__=='__main__':
    import sys
    p,m=merge(sys.argv[1]); out=Path(sys.argv[2]); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w') as f:
        index=1
        for face in p:
            f.write('g contents_1\n')
            for v in face: f.write('v '+' '.join(str(v[k]+TRANSLATION[k]) for k in range(3))+'\n')
            f.write('f '+' '.join(str(index+i) for i in range(len(face)))+'\n'); index+=len(face)
    print(json.dumps(dict(polygons=len(p),merged=m,output=str(out))))
