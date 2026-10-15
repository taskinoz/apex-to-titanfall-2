"""Source-derived Firing Range surface and support repairs, preserving collision.

Sand coverage is baked from the actual world-alpha shader equation. The hidden
landing pad, bone/rock LOD1 replacements and zipline arms retain source transforms. Retired render triangles keep their
lightmap allocation in the incremental ledger, with their shadow casting off.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import numpy as np
from new_arena_ports import ROOT,WORK,folder,source_bsp
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT
from apply_baked_lighting import tangents
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
import recover_composite_details as recovery

OUT=folder('firing-range')
PROJECT=OUT/'surface-repair'
BACKUP=OUT/'before-0.4.0'
# rib_giant_* c_uv1RotScale (x8) only feeds the detail-normal sample (t3) in
# the source pixel shader; albedo/normal/gloss use raw UVs on an unwrapped
# atlas. Scaling base UVs tiled that atlas, so rib UVs are left unchanged.
SAND={'sand_desert_02_wld','sand_desert_02_bm_transparent'}


def write(path,value):
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')


def snapshot():
    if BACKUP.exists():raise ValueError('Rollback already exists')
    BACKUP.mkdir(parents=True)
    for name in ['mp_apex_firing_range.bsp','mp_apex_firing_range.stbsp','scene.json','scene.npz',
                 'source-build.json','physics.json','physics.npz']:
        shutil.copy2(OUT/name,BACKUP/name)
    shutil.copytree(OUT/'materials',BACKUP/'materials')
    # RePak must not overwrite a file linked into any accepted package.
    live=OUT/'materials/build/firing_range_world.rpak'
    tmp=live.with_suffix('.detached.rpak');shutil.copy2(live,tmp);os.replace(tmp,live)


def texture_keys(t):
    # Triangle corner order may differ between source, draw and shadow streams.
    return np.sort(t.astype('<f4'),axis=1).reshape(-1,9).copy().view('V36').reshape(-1)


# Native world index capacity and the fourth (last) lightmap page's tile limit.
INDEX_CAPACITY=3145728
INDEX_FRACTION=.98
CHART_LIMIT=4*512*512
# Hidden source landing pad near (1523,2008,-700). Its deck/stair collision is
# already in the source world BVH, but its stripless VG sections were rejected
# by the 0.3.0 decoder, leaving a walkable but invisible structure.
PAD={'landing_pad_arm_top':1,'landing_pad_tarmac_nobase':1,'tday_vtol_landing_pad_square_01':0,
     'nex_pipe_set_a':1,'nex_pipe_set_b':1,'nex_pipe_set_corner':0,'nex_support_beams':0,
     'nex_support_beam_corner':0,'sewer_staircase_96_quad':0,'bldg_wall_support_imc_01_half':0,
     'air_unit_badlands_02_short':0,'air_unit_badlands_02_tall':0,'runway_light_2ft_blue_on':0}
# Native traces found every pad piece on existing world collision except the
# stairs: their IRPS collider lives only in the prop model, so append it.
SOURCE_COLLIDERS={'sewer_staircase_96_quad'}
# LOD1 removes the reported LOD2/LOD3 faceting at a fraction of LOD0's cost.
REPLACEMENT_LOD=1
SKIP_SECTIONS=('godray','ambient_occlusion','atmosphere','start_barrier','shimmer')


def plan():
    import filecmp
    if (PROJECT/'surface-result.json').exists():raise ValueError('Repair already started')
    # Re-planning is allowed only after the live map was restored from the snapshot.
    if BACKUP.exists() and not filecmp.cmp(BACKUP/'mp_apex_firing_range.bsp',OUT/'mp_apex_firing_range.bsp',shallow=False):
        raise ValueError('Restore the before-0.4.0 snapshot before planning again')
    from audit_world_draw_budget import audit
    PROJECT.mkdir(parents=True,exist_ok=True)
    scene=json.loads((OUT/'scene.json').read_text());ix=asset_index('firing-range')
    current=audit(OUT/'mp_apex_firing_range.bsp')['native_padded_indices']
    pad=[p for p in scene['omitted'] if Path(p['model']).stem.lower() in PAD]
    replace=[p for p in scene['placements'] if p['index']==1292]+            [p for p in scene['placements'] if 'canyonlands_mall_bone_' in p['model']]
    arms=[p for p in scene['omitted'] if Path(p['model']).stem=='zipline_arm']
    raw,slots,skins,armfolder=recovery.smd_arm()
    arm=[np.concatenate([s,np.full((*s.shape[:2],4),255,'f4')],2) for s in raw]
    cache={}
    def geometry(p,kind):
        if kind=='arm':path,lod=armfolder,0
        else:
            stem=Path(p['model']).stem.lower();path=str(ix[stem]) if kind=='pad' else p['folder']
            lod=PAD[stem] if kind=='pad' else REPLACEMENT_LOD
        if (path,lod) not in cache:
            r,sl,sk=(arm,slots,skins) if kind=='arm' else load(path,lod,True)
            cache[path,lod]=[np.asarray(s,'f4') for s in r],sl,sk
        r,sl,sk=cache[path,lod];matrix=np.asarray(rotation(p['angles']));out=[]
        for s,slot in zip(r,sl):
            if not len(s):continue
            name=sk[min(p['skin'],len(sk)-1)][slot]
            if any(w in name.lower() for w in SKIP_SECTIONS):continue
            t=s.copy();t[:,:,:3]=s[:,:,:3]@matrix.T*p['scale']+p['origin']
            t[:,:,3:6]=s[:,:,3:6]@matrix.T;t[:,:,7]=1-s[:,:,7];t[:,:,11]=255
            out.append((name,t))
        return out,path,lod
    # Retired replacement LODs free their indices but keep their chart tiles.
    retired=sum(p['triangles'] for p in replace)
    index_room=INDEX_CAPACITY*INDEX_FRACTION-current+3*retired
    chart_room=CHART_LIMIT-scene['triangles']
    pieces=[];placements=[];skipped=[];colliders=[];used=0;meshes=0
    recovery.ARMS=set()
    for kind,group in (('pad',pad),('replacement',replace),('arm',arms)):
        for p in group:
            out,path,lod=geometry(p,kind);count=sum(len(t) for n,t in out)
            # Each <=512-triangle mesh may add one padding triangle.
            cost=3*(used+count)+3*(meshes+len(out)+(used+count)//512+1)
            if cost>index_room or used+count>chart_room:
                if kind!='arm':raise ValueError('Required %s placement %d exceeds the budget'%(kind,p['index']))
                skipped.append(dict(index=p['index'],model=p['model'],triangles=count,
                    reason='Exceeds the %.0f%% native world index ceiling after required repairs'%(INDEX_FRACTION*100)));continue
            pieces.extend(out);used+=count;meshes+=len(out)
            row=dict(p,folder=str(path),lod=lod,triangles=count,replacement=kind=='replacement',
                recovery={'pad':'Stripless source VG author LOD (decoder repair)','replacement':'Source authored LOD1 replacement',
                          'arm':'Source SMD arm'}[kind],collision_triangles=0,
                collision_recovery='Existing source world collider retained; visual restoration only')
            if kind=='pad' and Path(p['model']).stem.lower() in SOURCE_COLLIDERS:
                col,method=recovery.collision(row,cache[path,lod][0])
                colliders.append(col);row.update(collision_triangles=len(col),collision_recovery=method)
            placements.append(row)
    names=list(dict.fromkeys(n for n,t in pieces))
    np.savez(PROJECT/'addition.npz',triangles=np.concatenate([t for n,t in pieces]),
             material=np.concatenate([np.full(len(t),names.index(n),'i4') for n,t in pieces]),
             names=names,collision=np.concatenate(colliders) if colliders else np.empty((0,3,3),'f4'))
    write(PROJECT/'plan.json',dict(version='0.4.0',added_props=len(placements),added_triangles=used,
        placements=placements,skipped=skipped,retired_triangles=retired,baseline_padded_indices=current,
        estimated_padded_indices=int(current-3*retired+3*used+3*meshes),index_ceiling=INDEX_FRACTION,
        landing_pad_props=len(pad),replacement_props=len(replace),support_props=len(arms)-len(skipped),
        policy='Landing pad, then reported rock/bones, then zipline arms while under the index and lightmap limits'))
    print('Planned',len(placements),'props,',used,'triangles; skipped',len(skipped),'arms',flush=True)


def sand_atlas(triangles,original_alpha):
    from PIL import Image
    from restore_banner_display_textures import image_dds
    from bake_terrain_transitions import sample,save_mips
    mats=OUT/'materials';p=OUT/'legion/exported_files/materials/sand_desert_02_bm_transparent'
    albedo=np.asarray(image_dds(p/'sand_desert_02_bm_transparent_albedoTexture.dds'))/255
    mask=np.asarray(image_dds(p/'sand_desert_02_bm_transparent_layerBlendTexture.dds'))/255
    size,tile=2048,32
    atlas=np.zeros((size,size,4),'u1');opacity=np.zeros_like(atlas);uv=np.empty((len(triangles),3,2),'f4')
    yy,xx=np.mgrid[:tile,:tile]
    # Corner allocation with padding. Extrapolated outside texels prevent seams.
    b=np.stack([1-(xx-2)/27-(yy-2)/27,(xx-2)/27,(yy-2)/27],-1).reshape(-1,3)
    b=np.maximum(b,0);b/=b.sum(1)[:,None]
    for i,t in enumerate(triangles):
        x=i%64*tile;y=i//64*tile
        world=b@t[:,:3];source=world-np.array([-32000,7000,28000])
        coord=source[:,:2]*[1,-1]/256
        colour=sample(albedo,coord)
        layer=sample(mask,coord)[:,0]
        vertex_alpha=b@original_alpha[i]/255
        coverage=1-np.clip(5*layer-5+6*vertex_alpha,0,1)
        colour[:,3]=255/255
        a=np.rint(np.clip(colour,0,1)*255).astype('u1').reshape(tile,tile,4)
        o=np.empty_like(a);o[:,:,:3]=np.rint(coverage.reshape(tile,tile,1)*255).astype('u1');o[:,:,3]=255
        atlas[y:y+tile,x:x+tile]=a;opacity[y:y+tile,x:x+tile]=o
        uv[i]=(np.array([[x+2.5,y+2.5],[x+29.5,y+2.5],[x+2.5,y+29.5]]))/size
    for name,image in [('sand_overlay_atlas',atlas),('sand_overlay_coverage',opacity)]:
        target=mats/'assets/texture/firing_range'/name
        save_mips(Image.fromarray(image),target.with_suffix('.dds'))
    return uv


def patch():
    if not BACKUP.exists():snapshot()
    mapping=json.loads((OUT/'materials/mapping.json').read_text())
    original=np.load(BACKUP/'scene.npz');tri=original['triangles'];mi=original['material'];names=list(original['names']);original.close()
    retired=np.zeros(len(tri),bool);retired_keys=[]
    scene=json.loads((OUT/'scene.json').read_text())
    for p in scene['placements']:
        if 'canyonlands_mall_bone_' not in p['model'] and p['index']!=1292:continue
        raw,sl,sk=load(p['folder'],p['lod'],True);matrix=np.asarray(rotation(p['angles']))
        points=np.concatenate([np.asarray(s)[:,:,:3]@matrix.T*p['scale']+p['origin'] for s in raw if len(s)])
        retired_keys.append(texture_keys(points))
    retired_keys=np.concatenate(retired_keys)
    retired=np.isin(texture_keys(tri[:,:,:3]),retired_keys)
    # Match the reported rock exactly by authored placement and LOD geometry.
    p=next(p for p in json.loads((OUT/'scene.json').read_text())['placements'] if p['index']==1292)
    raw,sl,sk=load(p['folder'],p['lod'],True);matrix=np.asarray(rotation(p['angles']))
    points=np.concatenate([np.asarray(s)[:,:,:3]@matrix.T*p['scale']+p['origin'] for s in raw if len(s)])
    rockkeys=texture_keys(points)
    retired|=np.isin(texture_keys(tri[:,:,:3]),rockkeys)
    # Actual source world alpha, keyed by exact recentered position.
    sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    from bsp_tool.branches.respawn.titanfall import MeshFlags
    geo=bsp_tool.load_bsp(str(source_bsp('firing-range'))).external
    alpha_pos=[];alpha_value=[]
    for mesh in geo.MESHES:
        sort=geo.MATERIAL_SORTS[mesh.material_sort]
        name=geo.texture_data_surface_name(sort.texture_data).replace('\\','/').rsplit('/',1)[-1]
        if name!='sand_desert_02_bm_transparent':continue
        records=getattr(geo,(mesh.flags&MeshFlags.MASK_VERTEX).name)
        for index in geo.MESH_INDICES[mesh.first_mesh_index:mesh.first_mesh_index+mesh.num_triangles*3]:
            v=records[index+sort.vertex_offset];pos=np.asarray(list(geo.VERTICES[v.position_index]))+[-32000,7000,28000]
            # 0.4.0 coverage, kept as published. The bsp_tool `negative_one`
            # field is the real vertex colour, but a 0.4.1 rebuild using it
            # over-covered the metal floors (see port-0.4.0/README.md).
            alpha_pos.append(pos);alpha_value.append(v.colour[3])
    sand_ids=np.flatnonzero(mi==names.index('sand_desert_02_bm_transparent'))
    # Scene corners are float32 copies of these recentered positions; match by
    # nearest source vertex rather than by decimal rounding, which can split.
    from scipy.spatial import cKDTree
    distance,nearest=cKDTree(np.asarray(alpha_pos)).query(tri[sand_ids,:,:3].reshape(-1,3).astype('f8'))
    if distance.max()>.01:raise ValueError('Sand corner has no matching source vertex')
    source_alpha=np.asarray(alpha_value,'f4')[nearest].reshape(-1,3)
    overlay_uv=sand_atlas(tri[sand_ids],source_alpha)
    for name in SAND:
        ids=np.flatnonzero(mi==names.index(name))
        if name=='sand_desert_02_bm_transparent':tri[ids,:,6:8]=overlay_uv;tri[ids,:,:3]+=tri[ids,:,3:6]*.35
        elif name=='sand_desert_02_wld':
            pos=tri[ids,:,:3]-[-32000,7000,28000];tri[ids,:,6:8]=pos[:,:,:2]*[1,-1]/256
    l=read_lumps(OUT/'mp_apex_firing_range.bsp',range(128));buf={k:bytearray(v) for k,v in l.items()}
    native=[]
    for at in range(0,len(l[2]),36):
        st=struct.unpack_from('<I',l[2],at+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0]
        native.append(l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/').rsplit('/',1)[-1])
    sorts=list(struct.iter_unpack('<3hHI',l[0x52]));records=np.frombuffer(buf[0x49],DT)
    positions=np.frombuffer(buf[3],'<f4').reshape(-1,3)
    normals=np.frombuffer(bytes(buf[0x1e]),'<f4').reshape(-1,3)
    # Source-to-native triangle corners are linked by exact position, not index.
    overlay_lookup={key.tobytes():j for key,j in zip(texture_keys(original_points(BACKUP,mi==names.index('sand_desert_02_bm_transparent'))),range(len(sand_ids)))}
    keep_mesh=[];changed_vertices=set();removed=0;newindices=bytearray()
    for i,mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
        sort=sorts[mesh[-2]];name=native[sort[0]]
        ix=np.frombuffer(l[0x4f],'<u2',mesh[1]*3,mesh[0]*2).astype('u4')+sort[-1]
        pts=positions[records['pi'][ix]].reshape(-1,3,3)
        drop=np.isin(texture_keys(pts),retired_keys)
        removed+=int(drop.sum())
        if drop.all():continue
        local=np.frombuffer(l[0x4f],'<u2',mesh[1]*3,mesh[0]*2).reshape(-1,3)[~drop]
        ids=local.astype('u4')+sort[-1]
        n=normals[records['ni'][ids]];p=positions[records['pi'][ids]]
        local=local.copy();flip=np.sum(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])*n.sum(1),axis=1)>0
        local[flip]=local[flip][:,[0,2,1]]
        newmesh=list(mesh);newmesh[0]=len(newindices)//2;newmesh[1]=len(local)
        newindices.extend(local.tobytes())
        if len(local)&1:newindices.extend(struct.pack('<3H',*[int(local[-1,-1])]*3))
        struct.pack_into('<I3H6b2h2BHI',buf[0x50],i*28,*newmesh)
        keep_mesh.append(i)
        if name not in SAND:continue
        if name=='sand_desert_02_bm_transparent':
            for face_ix,face in zip(ix.reshape(-1,3),pts):
                source_id=overlay_lookup[texture_keys(face[None])[0].tobytes()]
                for vi,pos in zip(face_ix,face):
                    # Match each corner against the original source face.
                    tid=sand_ids[source_id]
                    original_pos=tri[tid,:,:3]-.35*tri[tid,:,3:6]
                    corner=int(np.argmin(np.linalg.norm(original_pos-pos,axis=1)))
                    if np.linalg.norm(original_pos[corner]-pos)>.002:raise ValueError('Overlay corner mismatch')
                    records['uv'][vi]=overlay_uv[source_id,corner]
                    pi=records['pi'][vi]
                    if int(vi) not in changed_vertices:positions[pi]+=.35*normals[records['ni'][vi]]
                    changed_vertices.add(int(vi))
        for vi in np.unique(ix):
            if int(vi) in changed_vertices:continue
            changed_vertices.add(int(vi));pi=records['pi'][vi]
            if name=='sand_desert_02_wld':records['uv'][vi]=(positions[pi]-[-32000,7000,28000])[:2]*[1,-1]/256
        if name=='sand_desert_02_bm_transparent':
            struct.pack_into('<I',buf[0x50],i*28+24,mesh[-1]|0x10)
            struct.pack_into('<I',buf[2],sort[0]*36+32,struct.unpack_from('<I',buf[2],sort[0]*36+32)[0]|0x10)
    # Shadow stream filtering removes retired LODs and transparent sand occluders.
    excluded=texture_keys(np.concatenate((original_points(BACKUP,retired),original_points(BACKUP,mi==names.index('sand_desert_02_bm_transparent')))))
    shv=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);newv=bytearray();newix=bytearray();newrecords=bytearray()
    for first,count,page,unused in struct.iter_unpack('<2I2h',l[0x7f]):
        pts=shv[first:first+count*3].reshape(-1,3,3);pts=pts[~np.isin(texture_keys(pts),excluded)]
        if not len(pts):continue
        newrecords.extend(struct.pack('<2I2h',len(newv)//12,len(pts),page,unused));newv.extend(pts.tobytes());newix.extend(np.arange(len(pts)*3,dtype='<u2').tobytes())
    buf[0x7c],buf[0x7e],buf[0x7f]=newv,newix,newrecords
    buf[0x4f]=newindices
    bounds=bytearray(l[0x51])
    for i in keep_mesh:
        mesh=struct.unpack_from('<I3H6b2h2BHI',buf[0x50],i*28);sort=sorts[mesh[-2]]
        ix=np.frombuffer(buf[0x4f],'<u2',mesh[1]*3,mesh[0]*2).astype('u4')+sort[-1]
        pts=positions[records['pi'][ix]];lo=pts.min(0)-.02;hi=pts.max(0)+.02;c=(lo+hi)/2;e=(hi-lo)/2
        struct.pack_into('<8f',bounds,i*32,*c,float(np.linalg.norm(e))+.02,*e,0)
        tan,mir=tangents(pts.reshape(-1,3,3),normals[records['ni'][ix]].reshape(-1,3,3),records['uv'][ix].reshape(-1,3,2))
        start=len(buf[0x1e])//12;buf[0x1e].extend(tan.astype('<f4').tobytes())
        records['tangent'][ix]=np.arange(start,start+len(ix),dtype='u4')|(mir.reshape(-1).astype('u4')<<31)
    buf[0x50]=bytearray(b''.join(buf[0x50][i*28:i*28+28] for i in keep_mesh));buf[0x51]=bytearray(b''.join(bounds[i*32:i*32+32] for i in keep_mesh))
    count=len(keep_mesh);struct.pack_into('<2I',buf[0xe],24,0,count)
    buf[0x77],buf[0x78],buf[0x79]=map(bytearray,build_camera_visibility(buf[0x51],np.arange(count,dtype='<u2').tobytes()))
    struct.pack_into('<3I',buf[0x7b],0,count,count,count)
    for at in [0,36]:struct.pack_into('<i',buf[5],at+20,len(newrecords)//12)
    struct.pack_into('<i',buf[5],44,len(newrecords)//12)
    buf.update(reorder(buf)[0]);tmp=OUT/'surfaces.bsp';compact(OUT/'mp_apex_firing_range.bsp',tmp,buf);os.replace(tmp,OUT/'mp_apex_firing_range.bsp')
    np.savez(PROJECT/'retired.npz',mask=retired)
    # Keep the incremental chart ledger unchanged for the bounded append.
    append_base=PROJECT/'append-baseline';append_base.mkdir(exist_ok=True)
    np.savez(append_base/'scene.npz',triangles=tri,material=mi,names=names)
    shutil.copy2(BACKUP/'scene.json',append_base/'scene.json')
    shutil.copy2(BACKUP/'source-build.json',append_base/'source-build.json')
    np.savez(OUT/'scene.npz',triangles=tri,material=mi,names=names)
    write(PROJECT/'surface-result.json',dict(retired_render_triangles=removed,sand_overlay_triangles=len(sand_ids),
         collision_unchanged=True,coverage_equation='1 - saturate(5 * layerMask - 5 + 6 * sourceVertexAlpha)',
         source_world_uv='(original_world_x, -original_world_y) / 256',overlay_offset=.35,
         atlas_size=2048,atlas_limit='32 texels per triangle; resampled static coverage approximation'))


def original_points(backup,mask):
    x=np.load(backup/'scene.npz');t=x['triangles'][mask,:,:3].copy();x.close();return t


def materials():
    from extract_native_material import NativePak
    from bake_terrain_transitions import save_mips
    from PIL import Image
    import prepare_composite_materials as prepare
    mats=OUT/'materials';mapping=json.loads((mats/'mapping.json').read_text());manifest=json.loads((mats/'build.json').read_text())
    files={f['_path']:f for f in manifest['files']}
    addition=np.load(PROJECT/'addition.npz');names=list(addition['names']);ids=addition['material'];addition.close()
    new={str(n):int((ids==i).sum()) for i,n in enumerate(names) if n not in mapping['materials']}
    if new:
        write(PROJECT/'material-scene.json',dict(materials=new))
        prepare.OUT=PROJECT/'materials'
        shared=ROOT/'output/phase-runner/shared-assets/materials'
        if not shared.exists():shared=Path('D:/Games/ApexToTitanfallWork/project-storage/output/phase-runner/shared-assets/materials')
        prepare.prepare(PROJECT/'material-scene.json',[shared,OUT/'legion/exported_files/materials'],'firing_range')
        staged=json.loads((prepare.OUT/'mapping.json').read_text())
        for f in json.loads((prepare.OUT/'build.json').read_text())['files']:
            if f['_path'] in files:continue
            for ext in ('json','uber') if f['_type']=='matl' else ('dds',) if f['_type']=='txtr' else ('msw',):
                a=(prepare.OUT/'assets'/f['_path']).with_suffix('.'+ext);b=(mats/'assets'/f['_path']).with_suffix('.'+ext)
                b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
            files[f['_path']]=f
        mapping['materials'].update({n:staged['materials'][n] for n in new})
    native=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak')
    spec,uber=native.material(next(a for a in native.assets if a['guid']==0x92b5ba61a3bf2e7a))
    r=mapping['materials']['sand_desert_02_bm_transparent'];r['transparent']=True
    textures={'0':'texture/firing_range/sand_overlay_atlas.rpak','13':'texture/firing_range/sand_overlay_coverage.rpak'}
    # Atlas coordinates apply to all channels, so tiled old normal/gloss maps
    # cannot be bound here. Neutral maps avoid unrelated stretched PBR detail.
    for slot,name,col in [('1','normal',(128,128,255,255)),('2','gloss',(30,30,30,255)),('3','spec',(8,8,8,255))]:
        path='texture/firing_range/sand_overlay_neutral_'+name+'.rpak';target=(mats/'assets'/path).with_suffix('.dds')
        save_mips(Image.new('RGBA',(4,4),col),target);textures[slot]=path
    for path in textures.values():files[path]=dict(_type='txtr',_path=path,**{'$disableStreaming':True})
    albedo=(mats/'assets'/textures['0']).with_suffix('.dds');raw=albedo.read_bytes()
    if raw[84:88]==b'DXT5':
        raw=raw[:84]+b'DX10'+raw[88:128]+struct.pack('<5I',78,3,0,1,0)+raw[128:];albedo.write_bytes(raw)
    path='material/'+r['name']+'_wld.rpak'
    spec=dict(spec,name=r['name'],width=2048,height=2048,shaderSet='shaderset/firing_range_world_alpha.rpak',
              rasterizerFlags='0x16',surfaceProp='sand')
    spec['blendStates']=spec['blendStates']+['0x0']*4;spec['$textures']=textures
    buffer=bytearray(uber);struct.pack_into('<6f',buffer,0,1,0,0,1,0,0);struct.pack_into('<f',buffer,108,1)
    (mats/'assets'/path).with_suffix('.json').write_text(json.dumps(spec,indent=2));(mats/'assets'/path).with_suffix('.uber').write_bytes(buffer)
    r.update(textures=textures,native_source_channels='World-space source sand plus shader-derived baked blend coverage',
             coverage_equation='1-saturate(5*mask-5+6*source_vertex_alpha)',atlas_size=2048)
    # RePak auto-adds a material's undeclared textures as streamed assets, which
    # fails without a starpak. Declare every texture before any material.
    manifest['files']=sorted(files.values(),key=lambda f:f['_type']!='txtr')
    write(mats/'build.json',manifest);write(mats/'mapping.json',mapping)
    import subprocess
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(mats/'build.json')],capture_output=True,text=True)
    (PROJECT/'material-build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    scene=json.loads((OUT/'scene.json').read_text())
    for i,n in enumerate(names):scene['materials'][str(n)]=scene['materials'].get(str(n),0)+int((ids==i).sum())
    write(OUT/'scene.json',scene)
    write(PROJECT/'material-result.json',dict(new_materials=list(new),sand_shader='Native world alpha',
          all_other_materials_retained=True,water_and_hdr_preserved=True))


def append():
    if (PROJECT/'result.json').exists():raise ValueError('Already appended')
    base=PROJECT/'bake-base';base.mkdir(exist_ok=True)
    oldtri=np.fromfile(OUT/'source-feature-recovery/bake-triangles.bin','<f4').reshape(-1,3,3)
    casts=np.fromfile(OUT/'source-feature-recovery/bake-casters.bin','u1')
    x=np.load(BACKUP/'scene.npz');t=x['triangles'];mi=x['material'];names=list(x['names']);x.close()
    retired=np.load(PROJECT/'retired.npz')['mask'];sand=mi==names.index('sand_desert_02_bm_transparent')
    casts[np.isin(texture_keys(oldtri),texture_keys(t[retired|sand,:,:3]))]=0
    oldtri.tofile(base/'bake-triangles.bin');casts.tofile(base/'bake-casters.bin')
    recovery.OUT,recovery.WORK,recovery.MAP,recovery.BACKUP=OUT,PROJECT,OUT/'mp_apex_firing_range.bsp',PROJECT/'append-baseline'
    direction=-np.asarray(json.loads((OUT/'environment.json').read_text())['native_sun_normal'])
    recovery.append(base,.98,str(WORK/'tools/bake_arena_environment.exe'),direction.tolist())
    # Replacements take the existing authored placement identity, not new props.
    scene=json.loads((OUT/'scene.json').read_text());scene['placements']=list({p['index']:p for p in scene['placements']}.values())
    scene['props']=len(scene['placements']);scene['retired_triangle_ledger']=np.flatnonzero(retired).tolist()
    scene['active_render_triangles']=scene['triangles']-int(retired.sum());write(OUT/'scene.json',scene)
    from build_preview_stbsp import build
    build(OUT,OUT/'materials','mp_apex_firing_range','firing_range_world')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['plan','patch','materials','append'])
    a=p.parse_args();dict(plan=plan,patch=patch,materials=materials,append=append)[a.action]()
