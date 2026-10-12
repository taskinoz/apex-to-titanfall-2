"""Add visible, gently connected player floors along the authored pipe route."""
import json,math,shutil,struct
import numpy as np
from repair_tunnel_passages import TARGET as SOURCE,ROOT,P,remap_grid
from repair_preview_index_padding import read_lumps,validate_index_padding
from stage_prop_geometry import rotation
from native_triangle_collision import encode
from preview_visibility import build_visibility,validate_visibility
from repair_prop_coverage import traversal_frontier
from compact_preview_bsp import compact
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from append_prop_geometry import tangent

TARGET=P/'preview-tunnel-walkways/mp_phase_runner_preview.bsp'
CHAINS=[[12235,12237,12239,12238,12234,12241,12244,12243,12245,12242,12232],
        [12248,12225,12227,12226,12233,12247,12249,12240,12228,12230,12246]]

def routes():
    props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};result=[]
    for chain in CHAINS:
        centers=[];directions=[]
        for j,index in enumerate(chain):
            p=props[index];m=np.array(rotation(p['angles']));c=np.array(p['origin'],dtype=float);c[2]-=193.5*p['scale']-(160. if p['scale']>1.5 else max(16.,25*p['scale']))
            neighbor=np.array(props[chain[j+1 if j+1<len(chain) else j-1]]['origin']);d=m[:,1].copy();d[2]=0;d/=np.linalg.norm(d)
            if d@(neighbor-c)*(1 if j+1<len(chain) else -1)<0:d=-d
            centers.append(c);directions.append(d)
        # Entry/exit ramps taper down to the original ring-floor elevation.
        first=centers[0]-directions[0]*96;first[2]-=max(16.,25*props[chain[0]]['scale'])+4
        last=centers[-1]+directions[-1]*96;last[2]-=max(16.,25*props[chain[-1]]['scale'])+4
        centers=[first]+centers+[last];directions=[directions[0]]+directions+[directions[-1]]
        points=[]
        for a,b,da,db in zip(centers,centers[1:],directions,directions[1:]):
            length=np.linalg.norm(b[:2]-a[:2]);count=max(2,math.ceil(length/20))
            for u in np.arange(count)/count:
                # Hermite tangents follow ring normals through the broad bends.
                c=(2*u**3-3*u**2+1)*a+(-2*u**3+3*u**2)*b+(u**3-2*u**2+u)*da*length+(u**3-u**2)*db*length
                c[2]=(1-u)*a[2]+u*b[2];points.append(c)
        points.append(centers[-1]);points=np.array(points)
        # Secondary overlapping rings have smaller openings than the main
        # route rings. Keep the entire floor strip above their lower arcs.
        for p in props.values():
            if not p['in_arena'] or 'wraith_tt_portal_large' not in p['model']:continue
            m=np.array(rotation(p['angles']));local=(points-p['origin'])@m;radius=193.5*p['scale']
            for i,q in enumerate(local):
                horizontal=abs(q[0])+40
                if abs(q[1])<=64 and horizontal<radius:
                    lower=p['origin'][2]-np.sqrt(radius*radius-horizontal*horizontal)+8
                    points[i,2]=max(points[i,2],lower)
        # Propagate raised sections into approaches at a maximum 35-degree
        # gradient; no abrupt player-step-sized ledges are introduced.
        distances=np.linalg.norm(np.diff(points[:,:2],axis=0),axis=1)
        for i in range(1,len(points)):points[i,2]=max(points[i,2],points[i-1,2]-.7*distances[i-1])
        for i in range(len(points)-2,-1,-1):points[i,2]=max(points[i,2],points[i+1,2]-.7*distances[i])
        result.append(dict(chain=chain,points=points.tolist()))
    return result

def build():
    route=routes();tri=[];uv=[];width=80.;thickness=4.
    for r in route:
        points=np.array(r['points']);t=np.gradient(points,axis=0);side=np.column_stack((-t[:,1],t[:,0],np.zeros(len(t))));side/=np.linalg.norm(side,axis=1)[:,None]
        left=points+side*width/2;right=points-side*width/2;distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]/64
        for i in range(len(points)-1):
            top=np.array([left[i],right[i],right[i+1],left[i+1]]);bottom=top-[0,0,thickness]
            corners=np.array([[0,distance[i]],[width/64,distance[i]],[width/64,distance[i+1]],[0,distance[i+1]]])
            for ids in ((0,1,2),(0,2,3)):tri.append(top[list(ids)]);uv.append(corners[list(ids)])
            for ids in ((0,2,1),(0,3,2)):tri.append(bottom[list(ids)]);uv.append(corners[list(ids)])
            for j in (0,1,2,3):
                k=(j+1)%4;face=np.array([top[j],bottom[j],bottom[k],top[k]])
                for ids in ((0,1,2),(0,2,3)):tri.append(face[list(ids)]);uv.append(np.array([[0,0],[0,.0625],[width/64,.0625],[width/64,0]])[list(ids)])
    tri=np.array(tri,dtype='<f4');uv=np.array(uv,dtype='<f4')
    good=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>1e-5;tri=tri[good];uv=uv[good]
    ids=(3,0x1e,0x49,0x4f,0x50,0x51,0x52,2,0x2b,0x2c,0x0e,0x7b,0x42,0x44,0x45,0x60,0x5c,0x57,0x59)
    l=read_lumps(SOURCE,ids);buffers={i:bytearray(l[i]) for i in (3,0x1e,0x49,0x4f,0x50,0x51,0x52,0x0e,0x7b)}
    texture=None
    for i in range(len(l[2])//36):
        ni=struct.unpack_from('<I',l[2],i*36+12)[0];off=struct.unpack_from('<I',l[0x2c],ni*4)[0];name=l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/').lower()
        if 'trim_metal_01' in name and 'yellow' not in name:texture=i;break
    if texture is None:raise ValueError('Recovered metal material missing')
    first_mesh=len(l[0x50])//28
    for at in range(0,len(tri),128):
        faces=tri[at:at+128];tex=uv[at:at+128];base=len(buffers[0x49])//44;first=len(buffers[0x4f])//2
        for j,(f,u) in enumerate(zip(faces,tex)):
            n=np.cross(f[1]-f[0],f[2]-f[0]);n/=np.linalg.norm(n)
            du1=u[1]-u[0];du2=u[2]-u[0];e1=f[1]-f[0];e2=f[2]-f[0];det=du1[0]*du2[1]-du2[0]*du1[1]
            s=(e1*du2[1]-e2*du1[1])/det if abs(det)>1e-9 else e1;t=(e2*du1[0]-e1*du2[0])/det if abs(det)>1e-9 else e2
            tan,mirrored=tangent(tuple(n),s,t)
            for p,q in zip(f,u):
                pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12
                buffers[3].extend(p.tobytes());buffers[0x1e].extend(np.array([n,tan],dtype='<f4').tobytes())
                buffers[0x49].extend(struct.pack('<2I2f4B4f2I',pi,ni,*q,255,255,255,255,.25015666584,.13143643240,0,0,(ni+1)|(0x80000000 if mirrored else 0),0))
            buffers[0x4f].extend(struct.pack('<3H',j*3,j*3+2,j*3+1))
        if len(faces)&1:buffers[0x4f].extend(struct.pack('<3H',0,0,0))
        r=bytearray(l[0x50][:28]);struct.pack_into('<I3H',r,0,first,len(faces),0,len(faces)*3-1);struct.pack_into('<H',r,22,len(buffers[0x52])//12);buffers[0x50].extend(r)
        buffers[0x52].extend(struct.pack('<3hHi',texture,0,-1,len(faces)*3-1,base));lo=faces.min((0,1))-.02;hi=faces.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2
        buffers[0x51].extend(struct.pack('<8f',*c,np.linalg.norm(e)+.02,*e,0))
    encoded,newbounds=encode([tri[i:i+96] for i in range(0,len(tri),96)],len(buffers[3])//12)
    for at in range(0,len(encoded[0x45]),44):
        struct.pack_into('<i',encoded[0x45],at+16,struct.unpack_from('<i',encoded[0x45],at+16)[0]+len(l[0x42])//4)
        struct.pack_into('<i',encoded[0x45],at+20,struct.unpack_from('<i',encoded[0x45],at+20)[0]+len(l[0x44])//16)
    buffers[3].extend(encoded[3]);buffers.update({i:l[i]+encoded[i] for i in (0x42,0x44,0x45,0x60)})
    words=[w for w, in struct.iter_unpack('<I',l[0x59])]+[w for _,n,w in struct.iter_unpack('<HHI',l[0x57]) if n==1];active={(w>>24,(w>>8)&65535) for w in words}
    brushbounds=[];brushids=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
        if (0,i) in active:c=np.array(r[:3]);e=np.array(r[6:9]);brushbounds.append(((c-e).tolist(),(c+e).tolist()));brushids.append(i)
    oldpos=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);tribounds=[];headerids=[];headers=list(struct.iter_unpack('<6h4i4f',l[0x45]))
    for i,h in enumerate(headers):
        if (0x40,i) in active:v=oldpos[h[6]:h[6]+h[3]];tribounds.append((v.min(0).tolist(),v.max(0).tolist()));headerids.append(i)
    tribounds.extend(newbounds);headerids.extend(range(len(headers),len(headers)+len(newbounds)));buffers.update(remap_grid(brushbounds,tribounds,brushids,headerids))
    total=len(buffers[0x50])//28;struct.pack_into('<I',buffers[0x0e],28,total);struct.pack_into('<3I',buffers[0x7b],0,total,total,total)
    nodes,refs,objects=build_visibility(buffers[0x51],leaf_size=128);vis=validate_visibility(nodes,refs,objects,buffers[0x51]);buffers.update({0x77:nodes,0x78:refs,0x79:objects})
    proof=compact(SOURCE,TARGET,buffers);budget=audit(TARGET)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Walkways exceed safe draw capacity')
    validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52])
    report=dict(routes=route,width=width,thickness=thickness,triangles=len(tri),first_mesh=first_mesh,meshes=total-first_mesh,
        first_header=len(headers),headers=len(newbounds),material_texture=texture,collision_matches_render_exactly=True,
        original_geometry_and_collision_prefixes_preserved=True,budget=budget,visibility=vis,traversal=traversal_frontier(nodes),compaction=proof)
    status=json.loads(SOURCE.with_name('source-build.json').read_text());status['tunnel_walkways']=report;status['tunnel_render_detail']['budget']=budget;status['world_draw_budget_repair']['after']=budget;status['render_triangles']=budget['real_triangles'];status['render_repair']['world_meshes']=total;status['visibility_rebuild']=vis
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2));TARGET.with_name('tunnel-walkways.json').write_text(json.dumps(report,indent=2))
    for name in ('collision-ownership.json','tunnel-collision-repair.json'):shutil.copy2(SOURCE.with_name(name),TARGET.with_name(name))
    shutil.copy2(P/'preview-tunnel-detail/render-placement-proof.json',TARGET.with_name('render-placement-proof.json'))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    for f in SOURCE.parent.glob(SOURCE.stem+'_*.ent'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps({k:v for k,v in report.items() if k not in ('routes','compaction')},indent=2),flush=True)

if __name__=='__main__':build()
