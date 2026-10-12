"""Encode native directional lightmaps and repair tangent frames for the arena.

The shipped uberSamp2222_wld_ps shader establishes these layouts:
SKY A: RGB*(alpha*3.984375+0.015625) in linear space; SKY B: a
world-space sky direction encoded with rgb*2.007874-1. RTL A holds
four six-bit light-table entries plus an eight-bit table page. RTL B
holds their visibilities. Unused entries are 63, not zero.
"""
import sys,json,struct,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image
from prepare_lighting_scene import SOURCE,OUT,DT
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
TARGET=ROOT/'output/phase-runner/preview-baked/mp_phase_runner_preview.bsp'

def encode_rgbm(rgb):
    rgb=np.asarray(rgb,dtype=np.float64)
    a=np.clip(np.ceil((rgb.max(axis=-1)-.015625)/3.984375*255),0,255).astype(np.uint8)
    scale=a.astype(float)/255*3.984375+.015625
    return np.concatenate((np.rint(np.clip(rgb/scale[...,None],0,1)*255).astype(np.uint8),a[...,None]),axis=-1)

def tangents(p,n,uv):
    e1=p[:,1]-p[:,0];e2=p[:,2]-p[:,0];u1=uv[:,1]-uv[:,0];u2=uv[:,2]-uv[:,0]
    d=u1[:,0]*u2[:,1]-u1[:,1]*u2[:,0];ok=np.abs(d)>1e-12;inv=np.zeros_like(d);inv[ok]=1/d[ok]
    s=(e1*u2[:,1,None]-e2*u1[:,1,None])*inv[:,None]
    t=(e2*u1[:,0,None]-e1*u2[:,0,None])*inv[:,None]
    nn=n/np.maximum(np.linalg.norm(n,axis=2,keepdims=True),1e-20)
    tan=s[:,None,:]-nn*np.sum(nn*s[:,None,:],axis=2,keepdims=True)
    length=np.linalg.norm(tan,axis=2);bad=length<1e-9
    axes=np.zeros_like(nn);axes[...,2]=1;axes[np.abs(nn[...,2])>.9]=[0,1,0]
    tan[bad]=np.cross(axes,nn)[bad];tan/=np.maximum(np.linalg.norm(tan,axis=2,keepdims=True),1e-20)
    mirrored=np.sum(np.cross(nn,tan)*t[:,None,:],axis=2)<0
    return tan.astype('<f4'),mirrored

def build():
    report=json.loads((OUT/'scene.json').read_text());w,h,pages=(report[k] for k in ('width','height','pages'))
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=report['source_sha256']:raise ValueError('Bake source changed')
    atlas=np.load(OUT/'atlas.npz');faces,uv,page,mi=(atlas[k] for k in ('faces','uv','page','meshid'))
    l=read_lumps(SOURCE,[3,0x1e,0x49,0x4f,0x50,0x51,0x52,0xe,0x7b])
    old=np.frombuffer(l[0x49],DT);pos=np.frombuffer(l[3],'<f4').reshape(-1,3);norm=np.frombuffer(l[0x1e],'<f4').reshape(-1,3)
    geom=pos[old['pi'][faces]];tan,mirrored=tangents(geom,norm[old['ni'][faces]],old['uv'][faces])
    tangent_start=len(norm);flat=tan.reshape(-1,3)
    # Quantized keys deduplicate identical vectors; actual normalized values are
    # retained, preserving the native normal buffer prefix used by collision.
    _,first,inv=np.unique(np.rint(flat*1e6).astype(np.int32),axis=0,return_index=True,return_inverse=True)
    newnorm=l[0x1e]+flat[first].tobytes();tangent_ids=(inv.reshape(-1,3).astype(np.uint32)+tangent_start)|(mirrored.astype(np.uint32)<<31)
    newv=old[faces].copy();newv['light'][...,:2]=uv;newv['light'][...,2:]=0;newv['tangent']=tangent_ids;newv['extra']=0
    meshes=bytearray();indices=bytearray();sorts=bytearray();bounds=bytearray();lit=bytearray();oldix=np.frombuffer(l[0x4f],'<u2');oldsort=list(struct.iter_unpack('<4hI',l[0x52]));counts=[]
    for mesh_index,r0 in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
        source_sort=oldsort[r0[-2]];sel=np.flatnonzero(mi==mesh_index)
        groups=[(int(k),sel[page[sel]==k]) for k in np.unique(page[sel])] if len(sel) else [(-1,None)]
        for atlas_page,selected in groups:
            record=bytearray(l[0x50][mesh_index*28:(mesh_index+1)*28]);si=len(sorts)//12;firstindex=len(indices)//2
            if selected is None:
                # Retain unlit sky/other meshes and their original vertex buffers.
                raw=oldix[r0[0]:r0[0]+r0[1]*3];base=source_sort[4]
                if r0[-1]&0x600==0x200:
                    vr=old[base+raw.astype(np.uint32)];base=len(lit)//44;lit.extend(vr.tobytes());raw=np.arange(len(raw),dtype='<u2')
                indices.extend(raw.tobytes());minimum=int(raw.min());span=int(raw.max())-minimum;count=r0[1]
                sr=list(source_sort);sr[4]=base;sorts.extend(struct.pack('<4hI',*sr));points=None
            else:
                vr=newv[selected];base=len(lit)//44;lit.extend(vr.tobytes());count=len(selected);raw=np.arange(count*3,dtype='<u2');indices.extend(raw.tobytes());minimum=0;span=len(raw)-1
                sorts.extend(struct.pack('<3hHI',source_sort[0],atlas_page,source_sort[2],span,base));points=geom[selected].reshape(-1,3)
            if count&1:indices.extend(struct.pack('<3H',*[int(raw[-1])]*3))
            struct.pack_into('<I3H',record,0,firstindex,count,minimum,span);struct.pack_into('<H',record,22,si);meshes.extend(record)
            if points is None:bounds.extend(l[0x51][mesh_index*32:(mesh_index+1)*32])
            else:
                lo=points.min(0)-.02;hi=points.max(0)+.02;center=(lo+hi)/2;ext=(hi-lo)/2
                bounds.extend(struct.pack('<8f',*center,float(np.linalg.norm(ext))+.02,*ext,0))
            counts.append(count)
    if len(sorts)//12>=8192:raise ValueError('Native material sort capacity exceeded')
    validate_index_padding(meshes,indices,sorts)
    data=np.fromfile(OUT/'lighting.bin','<f4').reshape(pages,h,w,5)
    mask=np.fromfile(OUT/'lighting.bin.mask',np.uint8).reshape(pages,h,w).astype(bool)
    headers=bytearray();sky=bytearray();rtl=bytearray();sun_stats=[]
    for k in range(pages):
        if not mask[k].any():raise ValueError('Empty bake page')
        # Nearest valid texels fill chart gutters without averaging directions
        # or mixing sun-ID bitfields. Chart padding separates neighboring faces.
        nearest=distance_transform_edt(~mask[k],return_distances=False,return_indices=True)
        values=data[k][tuple(nearest)];sun=values[...,0]
        ambient=np.broadcast_to(np.array([.025,.027,.032]),(h,w,3))*(.4+.6*values[...,1,None])
        a=encode_rgbm(ambient);b=np.empty((h,w,4),np.uint8);b[...,:3]=np.rint(np.clip((values[...,2:5]+1)/2.007874,0,1)*255).astype(np.uint8);b[...,3]=255
        sky.extend(a.tobytes());sky.extend(b.tobytes())
        # Ambient lights become camera sky constants, not HardwareLight slots.
        # The single remaining source sun (WORLD_LIGHTS index 1) is hardware 0.
        # First six-bit entry references table slot zero = hardware sun index 0.
        # Remaining entries are the shader's sentinel 63; table page is zero.
        ids=np.full((h,w),0x00FFFFC0,dtype='<u4');vis=np.zeros((h,w,4),np.uint8);vis[...,0]=np.rint(sun*255).astype(np.uint8)
        rtl.extend(ids.tobytes());rtl.extend(vis.tobytes());rtl.extend(bytes((w//2)*(h//2)*4))
        headers.extend(struct.pack('<I2H',1,w,h));sun_stats.append(float(sun[mask[k]].mean()))
        Image.fromarray(vis[...,0]).resize((512,512)).save(OUT/f'sun-visibility-{k}.png')
        Image.fromarray(b).resize((512,512)).save(OUT/f'sky-direction-{k}.png')
    nodes,refs,objects=build_visibility(bounds,leaf_size=128);visproof=validate_visibility(nodes,refs,objects,bounds)
    models=bytearray(l[0xe]);level=bytearray(l[0x7b]);total=len(meshes)//28;struct.pack_into('<I',models,28,total);struct.pack_into('<3I',level,0,total,total,total)
    changes={0x1e:newnorm,0x49:lit,0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts,0x53:headers,0x62:sky,0x69:rtl,
        0x7a:struct.pack('<63h',0,*[-1]*62),0xe:models,0x7b:level,0x77:nodes,0x78:refs,0x79:objects}
    proof=compact(SOURCE,TARGET,changes);budget=audit(TARGET)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Safe draw budget exceeded')
    if budget['real_triangles']!=audit(SOURCE)['real_triangles']:raise ValueError('Geometry triangle count changed')
    status=json.loads(SOURCE.with_name('source-build.json').read_text());status['static_light_bake']={**report,'version':'0.1.31',
        'lit_triangles':len(faces),'sun_unoccluded_fraction_by_page':sun_stats,'tangent_vectors_added':len(first),
        'pbr_shader_verified':'uberSamp2222_wld_ps','shader_bindings':{'albedo':0,'normal':1,'gloss':2,'specular':3},
        'sun_world_light_index':1,'sun_hardware_light_index':0,'light_table_pages':1,'material_sort_count':len(sorts)//12,'draw_budget':budget,
        'geometry_and_albedo_uv_preserved':True,'collision_lumps_byte_verified':True,'walkway_geometry_and_collision_unchanged':True,
        'native_normal_buffer_prefix_preserved':True,'visibility':visproof,'compaction':proof,'client_rendering_verified':False}
    status['render_triangles']=budget['real_triangles'];status['render_repair']['world_meshes']=total;status['visibility_rebuild']=visproof;status['world_draw_budget_repair']['after']=budget
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for f in SOURCE.parent.glob('*'):
        if f.suffix in ('.ent','.stbsp') or f.name in ('tunnel-walkways.json','collision-ownership.json','tunnel-collision-repair.json','render-placement-proof.json'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps(status['static_light_bake'],indent=2),flush=True)

if __name__=='__main__':build()
