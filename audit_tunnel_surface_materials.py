"""Associate recovered Apex surface properties with the native world triangles."""
import collections,json
import numpy as np
from audit_world_collision_contents import ROOT,P,key,load_world
from build_preview_source import TRANSLATION,cross,subtract
from rebuild_complete_collision import clip_polygon,triangles
from audit_reported_tunnel_barriers import POINTS

def source_labels():
    mapping={};points=[];label=None
    for line in (P/'collision-labelled/world-collision-regular.obj').open():
        if line.startswith('g '):
            label=line.strip().split(' material_',1)[1];points=[]
        elif line.startswith('v '):points.append(subtract(tuple(map(float,line.split()[1:])),TRANSLATION))
        elif line.startswith('f '):
            start=max(range(len(points)),key=lambda i:sum(v*v for v in cross(subtract(points[(i+1)%len(points)],points[i]),subtract(points[(i+2)%len(points)],points[i]))))
            face=clip_polygon(points[start:]+points[:start])
            for t in triangles([face]) if face else []:mapping.setdefault(key(t),set()).add(label)
    return mapping

def main():
    mapping=source_labels();world,_=load_world();labels=[sorted(mapping.get(key(t),{'inline_world'})) for t in world]
    (ROOT/'logs/world-source-materials.json').write_text(json.dumps(labels))
    contacts=json.loads((ROOT/'logs/native-tunnel-contact-ownership.json').read_text());lo=world.min(1);hi=world.max(1);output=[]
    from triangle_capsule_reference import swept_capsule_distance
    for row in contacts:
        p=np.array(row['contact_position']);near=np.flatnonzero(np.all(lo<=p+[17,17,73],axis=1)&np.all(hi>=p-[17,17,1],axis=1));found=[]
        for i in near:
            t=world[i].astype(float);n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
            if abs(n[2])>.8:continue
            if swept_capsule_distance(t,p,p)<16.1:found.append(dict(triangle=int(i),materials=labels[i],normal=n.tolist(),vertices=t.tolist()))
        output.append(dict(site=row['site'],lift=row['lift'],contact_position=p.tolist(),surfaces=found))
        print(row['site'],row['lift'],json.dumps(found),flush=True)
    (ROOT/'logs/tunnel-contact-materials.json').write_text(json.dumps(output,indent=2))
    print('Material counts',collections.Counter(x for row in labels for x in row).most_common(15),flush=True)

if __name__=='__main__':main()
