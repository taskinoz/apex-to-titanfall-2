"""Inspect only active native shapes, including appended aperture triangles."""
import json,struct
import numpy as np
from repair_tunnel_passages import TARGET,ROOT
from repair_preview_index_padding import read_lumps
from triangle_capsule_reference import intersects,point_triangle,segments

def inspect(point):
    l=read_lumps(TARGET,(1,3,0x45,0x5c,0x57,0x59));owners=json.loads(TARGET.with_name('collision-ownership.json').read_text())['owners']
    words=[w for (w,) in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1]
    active={(w>>24,(w>>8)&65535) for w in words}
    owner_h={i:o for o in owners for i in range(o['first_header'],o['first_header']+o['headers'])};owner_b={i:o for o in owners for i in range(o['first_brush'],o['first_brush']+o['brushes'])}
    headers=list(struct.iter_unpack('<6h4i4f',l[0x45]));v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);p=np.array(point);a=p+[0,0,16];b=p+[0,0,56];contacts=[]
    for i,h in enumerate(headers):
        if (0x40,i) not in active:continue
        ts=v[h[6]:h[6]+h[3]].reshape(-1,3,3)
        near=np.flatnonzero(np.all(ts.min(1)<=p+[17,17,73],axis=1)&np.all(ts.max(1)>=p+[-17,-17,-1],axis=1))
        for j in near:
            t=ts[j].astype(float);dist=0 if intersects(a,b,t) else min(point_triangle(a,t),point_triangle(b,t),*[segments(a,b,x,y) for x,y in zip(t,np.roll(t,-1,axis=0))])**.5
            if dist<=16.1:
                o=owner_h.get(i,{});n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
                contacts.append(dict(header=i,triangle=h[7]+int(j),distance=dist,source_prop=o.get('index','world'),model=o.get('model','world'),normal=n.tolist(),vertices=t.tolist()))
    planes=np.frombuffer(l[1],dtype='<f4').reshape(-1,4);brush=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
        if (0,i) not in active:continue
        lo=np.array(r[:3])-r[6:9];hi=np.array(r[:3])+r[6:9]
        if np.any(p>hi+[16,16,0]) or np.any(p<lo-[16,16,72]):continue
        q=planes[1+r[9]:1+r[9]+r[4]];expanded=q[:,3]-np.minimum(q[:,:3]*[-16,-16,0],q[:,:3]*[16,16,72]).sum(1)
        if np.all(q[:,:3]@p<=expanded+.1):brush.append(dict(brush=i,source_prop=owner_b[i]['index'],model=owner_b[i]['model']))
    return dict(point=point,triangles=contacts,brushes=brush)

if __name__=='__main__':
    probes=json.loads((ROOT/'logs/tunnel-native-sweep-probes.json').read_text());p=probes[22];point=np.array(p['start'])+(np.array(p['end'])-p['start'])*.859081
    result=[inspect(point.tolist()),inspect(probes[23]['start'])]
    (ROOT/'logs/remaining-tunnel-contact.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
