"""Recover per-triangle source contents and identify falsely solid tunnel volumes."""
import collections,json,struct
from pathlib import Path
import numpy as np
from build_preview_source import TRANSLATION,cross,subtract
from rebuild_complete_collision import clip_polygon,triangles
from decode_inline_world_collision import decode
from repair_preview_index_padding import read_lumps
from audit_reported_tunnel_barriers import POINTS
from triangle_capsule_reference import intersects,point_triangle,segments
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'
PLAYER_MASK=0x1000b

def key(t):return b''.join(sorted(np.asarray(p,dtype='<f4').tobytes() for p in t))

def source_masks():
    mapping={};stats=collections.Counter();contents=0;points=[]
    for line in (P/'collision/world-collision-regular.obj').open():
        if line.startswith('g '):contents=int(line.strip().split('contents_')[1],16);points=[]
        elif line.startswith('v '):points.append(subtract(tuple(map(float,line.split()[1:])),TRANSLATION))
        elif line.startswith('f '):
            start=max(range(len(points)),key=lambda i:sum(v*v for v in cross(subtract(points[(i+1)%len(points)],points[i]),subtract(points[(i+2)%len(points)],points[i]))))
            face=clip_polygon(points[start:]+points[:start])
            for t in triangles([face]) if face else []:
                k=key(t);mapping[k]=mapping.get(k,0)|contents;stats[contents]+=1
    inline,_=decode(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp')
    for face in inline:
        face=clip_polygon(face)
        for t in triangles([face]) if face else []:
            k=key(t);mapping[k]=mapping.get(k,0)|1;stats[1]+=1
    return mapping,stats

def load_world():
    path=P/'preview-full-collision/mp_phase_runner_preview.bsp'
    l=read_lumps(path,(3,0x45));headers=list(struct.iter_unpack('<6h4i4f',l[0x45]))
    ownership=json.loads(path.with_name('collision-ownership.json').read_text());count=min(o['first_header'] for o in ownership['owners'])
    world_count=sum(h[4] for h in headers[:count]);v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3)
    tris=v[headers[0][6]:headers[0][6]+world_count*3].reshape(-1,3,3)
    return tris,count

def main():
    mapping,stats=source_masks();world,header_count=load_world();missing=[];masks=[]
    for i,t in enumerate(world):
        mask=mapping.get(key(t))
        if mask is None:missing.append(i);mask=0
        masks.append(mask)
    masks=np.array(masks,dtype='<u4');np.save(ROOT/'logs/world-source-contents.npy',masks)
    detail=[];lo=world.min(1);hi=world.max(1)
    for site,p in enumerate(POINTS):
        p=np.array(p);near=np.flatnonzero(np.all(lo<=p+[96,96,200],axis=1)&np.all(hi>=p- [96,96,64],axis=1));rows=[]
        for i in near:
            t=world[i].astype(float);n=np.cross(t[1]-t[0],t[2]-t[0]);n/=np.linalg.norm(n)
            if abs(n[2])>.8:continue
            rows.append(dict(triangle=int(i),contents=hex(int(masks[i])),player_blocking=bool(masks[i]&PLAYER_MASK),normal=n.tolist(),vertices=t.tolist()))
        detail.append(dict(site=site,point=p.tolist(),nearby_vertical_surfaces=rows))
    result=dict(world_triangles=len(world),world_headers=header_count,source_mask_count=len(stats),missing_triangle_masks=missing,
        masks=[dict(contents=hex(k),triangles=v,player_blocking=bool(k&PLAYER_MASK)) for k,v in stats.most_common()],
        stored_player_blocking_triangles=int(np.count_nonzero(masks&PLAYER_MASK)),
        stored_other_contents_triangles=int(np.count_nonzero((masks&PLAYER_MASK)==0)),reported_sites=detail)
    (ROOT/'logs/world-source-contents-audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='reported_sites'},indent=2),flush=True)
    for r in detail:
        print('Site',r['site'],'vertical triangles',len(r['nearby_vertical_surfaces']),'flags',dict(collections.Counter(q['contents'] for q in r['nearby_vertical_surfaces'])),flush=True)

if __name__=='__main__':main()
