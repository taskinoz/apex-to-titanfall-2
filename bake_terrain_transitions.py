"""Bake a preview seam blend from recovered albedos and layer masks.

This is an opaque approximation, not a reconstruction of Apex's layer shader.
No extra geometry is drawn. Original ground positions and physics are retained.
"""
import io,json,mmap,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image
from compact_preview_bsp import compact
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT/'output/phase-runner'
TARGETS=['icelandic_moss_01_wld_desertlands_snow_04_wld_bm',
         'icelandic_moss_01_wld_moss_01_lavender_wld_bm']
NAME='terrain_transition_preview'

def dds(path):
    raw=bytearray(Path(path).read_bytes())
    if raw[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',raw,128)[0]
        if fmt in {72,75,78,99}:struct.pack_into('<I',raw,128,fmt-1)
    return np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'),dtype=np.float32)/255.

def sample(image,uv):
    h,w=image.shape[:2]
    xy=np.mod(uv,1.)*np.array([w,h])-.5
    lo=np.floor(xy).astype(np.int64);f=xy-lo
    x,y=lo[:,0]%w,lo[:,1]%h;xx,yy=(x+1)%w,(y+1)%h
    return (image[y,x]*(1-f[:,0,None])*(1-f[:,1,None])+
            image[y,xx]*f[:,0,None]*(1-f[:,1,None])+
            image[yy,x]*(1-f[:,0,None])*f[:,1,None]+
            image[yy,xx]*f[:,0,None]*f[:,1,None])

def segment_distance(points,a,b):
    edge=b-a;length=np.dot(edge,edge)
    t=np.clip((points-a)@edge/(length or 1.),0.,1.)
    return np.linalg.norm(points-(a+t[:,None]*edge),axis=1)

def stage(size=4096):
    source=PROJECT/'preview-packed/mp_phase_runner_preview.bsp'
    triangles=[];meshes=[];edges={};seams=[]
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        headers=[struct.unpack_from('<4I',data,16+i*16) for i in range(128)]
        def lump(i):o,n,_,_=headers[i];return data[o:o+n]
        m,s,tex,table,names,ix=(lump(i) for i in (0x50,0x52,2,0x2c,0x2b,0x4f))
        po,vo=headers[3][0],headers[0x49][0]
        first_prop=json.loads(source.with_name('source-build.json').read_text())['structural_props']['first_mesh']
        for mi in range(first_prop):
            at=mi*28;first,count=struct.unpack_from('<IH',m,at);sort=struct.unpack_from('<H',m,at+22)[0]
            ti,_,_,_,base=struct.unpack_from('<3hHi',s,sort*12)
            ni=struct.unpack_from('<I',tex,ti*36+12)[0];no=struct.unpack_from('<I',table,ni*4)[0]
            name=names[no:names.index(0,no)].decode().replace('\\','/').rsplit('/',1)[-1]
            if name not in TARGETS:continue
            meshes.append(mi)
            for t in range(count):
                local=struct.unpack_from('<3H',ix,(first+t*3)*2)
                points=[];uv=[];keys=[]
                for li in local:
                    va=vo+(base+li)*44;pi=struct.unpack_from('<I',data,va)[0]
                    raw=data[po+pi*12:po+pi*12+12];keys.append(raw)
                    points.append(struct.unpack('<3f',raw));u,v=struct.unpack_from('<2f',data,va+8);uv.append((u,v))
                xy=np.array(points)[:,:2]
                matrix=np.column_stack([xy,np.ones(3)])
                if abs(np.linalg.det(matrix))<1e-8:raise ValueError('Terrain has vertical or degenerate XY projection')
                item=dict(points=points,uv=np.array(uv),matrix=np.linalg.inv(matrix),material=TARGETS.index(name),seams=[])
                index=len(triangles);triangles.append(item)
                for a,b in [(0,1),(1,2),(2,0)]:
                    key=tuple(sorted((keys[a],keys[b])))
                    if key in edges:
                        other,oa,ob=edges[key]
                        if triangles[other]['material']!=item['material']:
                            item['seams'].append((other,a,b));triangles[other]['seams'].append((index,oa,ob));seams.append((index,other))
                    else:edges[key]=(index,a,b)
    xy=np.concatenate([np.array(t['points'])[:,:2] for t in triangles])
    lo=xy.min(axis=0)-32;hi=xy.max(axis=0)+32;span=hi-lo
    images=[];masks=[]
    for name in TARGETS:
        folder=ROOT/'tools/legion/exported_files/materials'/name
        images.append(dds(folder/(name+'_albedoTexture.dds')))
        masks.append(dds(folder/(name+'_layerBlendTexture.dds')))
    folder=ROOT/'tools/legion/exported_files/materials'/TARGETS[0]
    moss=dds(folder/(TARGETS[0]+'_albedo2Texture.dds'))
    atlas=np.zeros((size,size,3),dtype=np.uint8);coverage=np.zeros((size,size),dtype=bool)
    for i,t in enumerate(triangles):
        p=np.array(t['points'])[:,:2];pixel=(p-lo)/span*size
        low=np.maximum(np.floor(pixel.min(axis=0)).astype(int),0);high=np.minimum(np.ceil(pixel.max(axis=0)).astype(int),size-1)
        xx,yy=np.meshgrid(np.arange(low[0],high[0]+1),np.arange(low[1],high[1]+1))
        grid=np.column_stack([xx.ravel(),yy.ravel()]);world=lo+(grid+.5)/size*span
        bary=np.column_stack([world,np.ones(len(world))])@t['matrix']
        keep=np.all(bary>=-1e-6,axis=1);grid=grid[keep];world=world[keep];bary=bary[keep]
        if not len(grid):continue
        uv=bary@t['uv'];colour=sample(images[t['material']],uv)**2.2
        if t['seams']:
            distances=np.stack([segment_distance(world,p[a],p[b]) for _,a,b in t['seams']]);closest=distances.argmin(axis=0)
            for si,(other,a,b) in enumerate(t['seams']):
                select=(closest==si)&(distances[si]<96.)
                if not np.any(select):continue
                w=world[select];other_t=triangles[other]
                other_uv=np.column_stack([w,np.ones(len(w))])@other_t['matrix']@other_t['uv']
                mask=(sample(masks[t['material']],uv[select])[:,0]+sample(masks[other_t['material']],other_uv)[:,0])/2
                falloff=np.clip(1-distances[si,select]/96.,0,1);falloff=falloff*falloff*(3-2*falloff)
                blended=colour[select]*(1-.5*falloff[:,None])+sample(images[other_t['material']],other_uv)**2.2*(.5*falloff[:,None])
                # Shared world coordinates make the moss band continuous on
                # either side. Texture scale is a preview choice, not a claim
                # that the complete source layer shader has been recovered.
                moss_uv=(w+np.array([26000.,19000.]))/256.
                amount=falloff*(.45+.3*mask)
                colour[select]=blended*(1-amount[:,None])+(sample(moss,moss_uv)**2.2)*amount[:,None]
        rgb=np.clip(colour**(1/2.2)*255+.5,0,255).astype(np.uint8)
        atlas[grid[:,1],grid[:,0]]=rgb;coverage[grid[:,1],grid[:,0]]=True
        if i%2000==0:print(f'Terrain bake {i}/{len(triangles)}',flush=True)
    # Edge dilation prevents unpainted texels bleeding into triangle boundaries.
    for _ in range(8):
        old=coverage.copy()
        for dy,dx in [(0,1),(0,-1),(1,0),(-1,0)]:
            rolled=np.roll(old,(dy,dx),(0,1));fill=~coverage&rolled
            atlas[fill]=np.roll(atlas,(dy,dx),(0,1))[fill];coverage[fill]=True
    out=PROJECT/'terrain-atlas';assets=out/'materials'/NAME;assets.mkdir(parents=True,exist_ok=True)
    image=Image.fromarray(atlas).convert('RGBA')
    # DDS writer produces BC3 mip levels explicitly; RePak accepts native DDS.
    save_mips(image,assets/(NAME+'_albedoTexture.dds'))
    Image.fromarray(atlas).resize((1024,1024)).save(out/'terrain-atlas-preview.png')
    report=dict(material_counts={'world/'+NAME:len(triangles)},source_meshes=meshes,
        triangles=len(triangles),shared_transition_edges=len(seams),atlas_size=size,
        xy_min=lo.tolist(),xy_max=hi.tolist(),transition_width=96.,
        original_albedos_secondary_moss_and_layer_masks_used=True,opaque_single_surface=True,
        limitation='Approximate 96-unit seam bake, not the original Apex per-vertex layered terrain shader. Atlas resampling can soften fine texture detail.',visual_verified=False)
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

def save_mips(image,path):
    parts=[];current=image
    while True:
        b=io.BytesIO();current.save(b,format='DDS',pixel_format='DXT5');raw=b.getvalue();parts.append(raw[128:])
        if current.width==1 and current.height==1:break
        current=current.resize((max(1,current.width//2),max(1,current.height//2)),Image.Resampling.BOX)
    b=io.BytesIO();image.save(b,format='DDS',pixel_format='DXT5');header=bytearray(b.getvalue()[:128])
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(parts));struct.pack_into('<I',header,108,0x401008)
    Path(path).write_bytes(header+b''.join(parts))

def apply(source,output):
    source,output=Path(source),Path(output);report=json.loads((PROJECT/'terrain-atlas/report.json').read_text())
    lo=np.array(report['xy_min']);span=np.array(report['xy_max'])-lo
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as d:
        h=[struct.unpack_from('<4I',d,16+i*16) for i in range(128)]
        def lump(i):o,n,_,_=h[i];return d[o:o+n]
        lit=bytearray(lump(0x49));sorts=bytearray(lump(0x52));tex=bytearray(lump(2));table=bytearray(lump(0x2c));names=bytearray(lump(0x2b))
        meshes,ix=lump(0x50),lump(0x4f);po=h[3][0]
        ti=len(tex)//36;table.extend(struct.pack('<I',len(names)));names.extend(('world/phase_runner_preview/'+NAME).encode()+b'\0')
        tex.extend(struct.pack('<3f6I',0,0,0,len(table)//4-1,report['atlas_size'],report['atlas_size'],0,0,0xa00))
        seen=set()
        for mi in report['source_meshes']:
            first,count=struct.unpack_from('<IH',meshes,mi*28);si=struct.unpack_from('<H',meshes,mi*28+22)[0]
            base=struct.unpack_from('<i',sorts,si*12+8)[0];struct.pack_into('<h',sorts,si*12,ti)
            for li in struct.unpack_from('<'+'H'*(count*3),ix,first*2):
                vi=base+li
                if vi in seen:continue
                seen.add(vi);pi=struct.unpack_from('<I',lit,vi*44)[0];p=struct.unpack_from('<3f',d,po+pi*12)
                uv=(np.array(p[:2])-lo)/span
                struct.pack_into('<2f',lit,vi*44+8,float(uv[0]),float(uv[1]))
    compaction=compact(source,output,{0x49:lit,0x52:sorts,2:tex,0x2c:table,0x2b:names})
    status=json.loads(source.with_name('source-build.json').read_text());status['terrain_transition_bake']=report|dict(vertices=len(seen),geometry_and_physics_unchanged=True)
    status['final_compaction']=compaction;output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,output.parent/p.name)
    print(json.dumps(status['terrain_transition_bake'],indent=2))

if __name__=='__main__':stage()
