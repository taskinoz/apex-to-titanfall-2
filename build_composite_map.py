"""Build an independent native v37 Northstar arena from the recovered scene.

Every draw and collision buffer is generated anew. The verified portal-free
native container provides engine metadata, never old arena geometry or props.
"""
import collections,itertools,json,math,shutil,struct,subprocess,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from repair_camera_visibility import build_camera_visibility
from stage_prop_geometry import rotation
from read_prop_physics import read_phy,read_bvh,convex_planes
from repair_preview_hull_edges import vertices_and_bevels
from native_triangle_collision import encode,collision_grid
from apply_baked_lighting import tangents,encode_rgbm
from spatial_preview_meshes import partition
from audit_world_draw_budget import audit,enforce_camera_bypass_budget
from build_character_lighting import make_tree
from build_preview_stbsp import build as stbsp
OUT=ROOT/'output/composite';MAP='mp_arena_composite'
SOURCE_BSP=ROOT/'inputs/composite/client/maps/mp_rr_arena_composite.bsp'
PAK_NAME='composite_world'
TEMPLATE=ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'
DT=np.dtype([('pi','<u4'),('ni','<u4'),('uv','<f4',2),('color','u1',4),('light','<f4',4),('tangent','<u4'),('extra','<u4')])

def entity_bytes(rows):
    return ('\n'.join('{\n'+'\n'.join('"'+k+'" "'+str(v)+'"' for k,v in r.items())+'\n}' for r in rows)+'\n\0').encode()

def physics(report):
    cachefile=OUT/'physics.npz'
    fingerprint=hashlib.sha256(json.dumps(report['placements'],sort_keys=True).encode()).hexdigest()
    metadata=OUT/'physics-source.json'
    valid_cache=not report.get('config') or (metadata.exists() and json.loads(metadata.read_text()).get('placements_sha256')==fingerprint)
    if cachefile.exists() and valid_cache:
        a=np.load(cachefile);return {int(k):a[k].tobytes() for k in a.files}
    groups=[];brush_bounds=[];owners=[];cache={};buf={1:bytearray(16),0x5c:bytearray(),0x5d:bytearray(),0x5e:bytearray(),0x5f:bytearray()}
    def add_tris(raw):
        t=np.asarray(raw,'<f4').reshape(-1,3,3)
        if not len(t):return
        good=(np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)>1e-5)&np.all(abs(t)<32750,axis=(1,2));t=t[good]
        if not len(t):return
        centers=t.mean(1);q=np.floor(centers/128).astype(np.int32);order=np.lexsort((centers[:,2],q[:,1],q[:,0]));t=t[order]
        groups.extend(t[i:i+180] for i in range(0,len(t),180))
    # Contents are translated deliberately. Only player-blocking source leaves
    # become native SOLID; remote menu rooms and non-solid volumes are omitted.
    faces=[];points=[];blocking=False;contents=0;removed_clips=collections.Counter()
    def obsolete_clip(points):
        # These source clips close intentional rooms and restricted rooftops.
        # They must not be removed simply because no visible panel was ported.
        return None
    for line in (OUT/'collision/world-collision-regular.obj').open():
        if line.startswith('g '):points=[];contents=int(line.split()[1].split('_')[1],16);blocking=bool(contents&0x1000b)
        elif line.startswith('v '):points.append(list(map(float,line.split()[1:4])))
        elif line.startswith('f ') and blocking and all(abs(p[0])<12000 and abs(p[1])<12000 and abs(p[2])<12000 for p in points):
            reason=obsolete_clip(points)
            if reason:removed_clips[reason]+=len(points)-2
            else:faces.extend([points[0],points[i],points[i+1]] for i in range(1,len(points)-1))
    if faces:add_tris(faces)
    import decode_inline_world_collision as inline
    inline.TRANSLATION=tuple(-v for v in report.get('source_offset',(0,0,0)))
    fs,n=inline.decode(SOURCE_BSP,OUT/'inline-collision.json')
    add_tris([[f[0],f[i],f[i+1]] for f in fs if all(abs(v)<12000 for p in f for v in p) for i in range(1,len(f)-1)])
    world_count=sum(len(g) for g in groups)
    def convex(points,planes):
        p=np.array(points);lo=p.min(0);hi=p.max(0)
        if np.any(abs(p)>32750):raise ValueError('Placed convex physics exceeds native coordinates')
        cuts=[q for q in planes if not any(abs(abs(v)-1)<1e-7 for v in q[:3])]
        _,extra=vertices_and_bevels(lo,hi,cuts,source_vertices=points)
        center=((lo+hi)/2).astype('<f4');ext=np.nextafter(np.maximum(abs(lo-center),abs(hi-center)).astype('<f4'),np.float32(np.inf))
        index=len(brush_bounds);offset=len(buf[0x5d])//2
        if index>=65535 or len(cuts)+len(extra)>255:raise ValueError('Native convex capacity exceeded')
        buf[0x5c].extend(struct.pack('<3f2BH3fI',*center,len(cuts),len(cuts)+len(extra),index,*ext,offset));brush_bounds.append(((center-ext).tolist(),(center+ext).tolist()))
        for q in cuts+extra:buf[1].extend(struct.pack('<4f',*q));buf[0x5d].extend(bytes(2))
        buf[0x5e].extend(struct.pack('<'+'H'*(6+len(cuts)+len(extra)),*([0]*6+[1]*len(cuts)+[0x4001]*len(extra))));buf[0x5f].extend(bytes(32*(6+len(cuts)+len(extra))))
    # Required CM brush stream includes a small unreachable sentinel, not a map-wide hull.
    convex([list(p) for p in itertools.product((-30002.,-30000.),(-30002.,-30000.),(-30002.,-30000.))],[])
    for p in report['placements']:
        if p['solid'] not in (2,6,7):continue
        folder=Path(p['folder']);name=folder.name;base=folder/name
        if name not in cache:
            try:
                if base.with_suffix('.phy').exists():pieces=read_phy(base.with_suffix('.phy'));method='IRPS'
                else:pieces,_=read_bvh(base.with_suffix('.rmdl'));method='BVH'
                cache[name]=(method,pieces)
            except Exception as e:cache[name]=('unavailable:'+str(e),[])
        method,pieces=cache[name];matrix=np.array(rotation(p['angles']));org=np.array(p['origin']);before=(len(brush_bounds),len(groups))
        if method=='BVH' and pieces:
            add_tris(np.array([[f[0],f[i],f[i+1]] for piece in pieces for f in piece for i in range(1,len(f)-1)])@matrix.T*p['scale']+org)
        for piece in (pieces if method!='BVH' else []):
            result=convex_planes(piece) if method=='IRPS' else None
            if result:
                points,planes=result;pts=np.array(points)@matrix.T*p['scale']+org;qs=np.array(planes);norm=qs[:,:3]@matrix.T;d=qs[:,3]*p['scale']+norm@org
                if np.any(abs(pts)>32750):
                    from rebuild_complete_collision import clip_polygon
                    fs=[clip_polygon((np.array(f)@matrix.T*p['scale']+org).tolist()) for f in piece]
                    add_tris([[f[0],f[i],f[i+1]] for f in fs if len(f)>=3 for i in range(1,len(f)-1)])
                else:convex(pts.tolist(),np.column_stack((norm,d)).tolist())
            else:add_tris(np.array([[f[0],f[i],f[i+1]] for f in piece for i in range(1,len(f)-1)])@matrix.T*p['scale']+org)
        owners.append(dict(index=p['index'],model=p['model'],method=method,brushes=len(brush_bounds)-before[0],headers=len(groups)-before[1]))
        if len(owners)%500==0:print('Collision placements',len(owners),'brushes',len(brush_bounds),'triangle groups',len(groups),flush=True)
    if len(groups)>65535:raise ValueError('Native triangle header capacity exceeded')
    encoded,bounds=encode(groups);changes={**buf,**encoded,0x5b:struct.pack('<I',1),0x55:struct.pack('<f6i',32768.,-1,-1,2,2,0,1),**collision_grid(brush_bounds,bounds)}
    np.savez(cachefile,**{str(k):np.frombuffer(v,np.uint8) for k,v in changes.items()})
    metadata.write_text(json.dumps(dict(placements_sha256=fingerprint),indent=2))
    (OUT/'physics.json').write_text(json.dumps(dict(world_triangles=world_count,removed_obsolete_clip_triangles=dict(removed_clips),brushes=len(brush_bounds),triangle_headers=len(groups),triangles=len(encoded[0x42])//4,owners=owners,missing=[p for p in owners if not p['brushes'] and not p['headers']]),indent=2))
    return changes

def build():
    started=time.monotonic();report=json.loads((OUT/'scene.json').read_text());data=np.load(OUT/'scene.npz');tris=data['triangles'];mi=data['material'];names=list(data['names'])
    material_map=json.loads((OUT/'materials/mapping.json').read_text())['materials'];changes=physics(report)
    old=read_lumps(TEMPLATE,(0x23,0x7b,0x63));texture=bytearray();strings=bytearray();table=bytearray();binding={}
    transparent={name for name in names if material_map[name].get('transparent')}
    foliage={name for name in names if material_map[name].get('native_foliage_cutout')}
    for name in names:
        native=material_map[name]['name'];binding[name]=len(texture)//36
        table.extend(struct.pack('<I',len(strings)));strings.extend(native.replace('/','\\').encode()+b'\0')
        texture.extend(struct.pack('<3f6I',0,0,0,len(table)//4-1,1024,1024,0,0,0xa00|(0x10 if name in transparent else 0)))
    positions=bytearray(changes[3]);normals=bytearray();lit=bytearray();indices=bytearray();meshes=bytearray();bounds=bytearray();sorts=bytearray();shadowp=bytearray();shadowi=bytearray();shadowm=bytearray()
    # A four-texel chart for every source triangle is a coarse but real static
    # visibility bake, keeping albedo UVs separate and unmodified.
    resolution=2048;tiles=resolution//4;perpage=tiles*tiles;pages=math.ceil(len(tris)/perpage)
    jobs=np.zeros(len(tris),np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')]))
    tri_index=0
    for ti,name in enumerate(names):
        selected=tris[mi==ti]
        for first in range(0,len(selected),10000):
            src=selected[first:first+10000];n=len(src);points=src[:,:,:3];normal=src[:,:,3:6];uv=src[:,:,6:8];tan,mirror=tangents(points,normal,uv)
            normal=normal/np.maximum(np.linalg.norm(normal,axis=2,keepdims=True),1e-12)
            pi=len(positions)//12;ni=len(normals)//12;base=len(lit)//44
            positions.extend(points.astype('<f4').tobytes());nb=np.empty((n*6,3),'<f4');nb[::2]=normal.reshape(-1,3);nb[1::2]=tan.reshape(-1,3);normals.extend(nb.tobytes())
            records=np.zeros(n*3,DT);records['pi']=np.arange(pi,pi+n*3);records['ni']=np.arange(ni,ni+n*6,2);records['uv']=uv.reshape(-1,2);records['color']=255;records['tangent']=np.arange(ni+1,ni+n*6,2,dtype=np.uint32)|(mirror.reshape(-1).astype(np.uint32)<<31)
            if src.shape[2]>=12:records['color']=np.rint(np.clip(src[:,:,8:12],0,255)).astype('u1').reshape(-1,4)
            ids=np.arange(tri_index,tri_index+n);page=ids//perpage;tile=ids%perpage;corner_uv=np.stack((tile%tiles,tile//tiles),1)[:,None,:]*4+np.array([[.5,.5],[3.2,.5],[.5,3.2]])
            records['light'][:,:2]=(corner_uv/resolution).reshape(-1,2)
            local=np.arange(n*3,dtype='<u2').reshape(-1,3);front=np.sum(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])*normal.sum(1),axis=1)>0;local[front]=local[front][:,[0,2,1]]
            # Match bake and native corner order exactly, including UV chart winding.
            jobs['p'][ids]=points;jobs['n'][ids]=normal;jobs['uv'][ids]=corner_uv;jobs['page'][ids]=page;tri_index+=n
            lit.extend(records.tobytes())
            for lightpage in np.unique(page):
                si=len(sorts)//12;sorts.extend(struct.pack('<3hHI',ti,int(lightpage),-1,n*3-1,base))
                subset=np.flatnonzero(page==lightpage)
                for selectedids in partition(points.mean(1),subset,limit=512):
                    ix=local[selectedids];flat=points[selectedids].reshape(-1,3);lo=flat.min(0).astype(float)-.02;hi=flat.max(0).astype(float)+.02;c=(lo+hi)/2;e=(hi-lo)/2
                    meshes.extend(struct.pack('<I3H6b2h2BHI',len(indices)//2,len(ix),int(ix.min()),int(ix.max()-ix.min()),2,-1,-1,-1,-1,-1,-1,-1,255,255,si,0x100a00|(0x10 if name in transparent else 0)));indices.extend(ix.tobytes())
                    if len(ix)&1:indices.extend(struct.pack('<3H',*[int(ix[-1,-1])]*3))
                    bounds.extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
            # Independent exact shadow meshes use local uint16 indices.
            if name!='sky' and name not in transparent and name not in foliage:
                shadowm.extend(struct.pack('<2I2h',len(shadowp)//12,n,1,-1));shadowp.extend(points.astype('<f4').tobytes());shadowi.extend(local.tobytes())
        if ti%25==0:print('Draw material',ti+1,'/',len(names),flush=True)
    if tri_index!=len(tris):raise ValueError('Scene triangle coverage changed')
    jobs['p'].tofile(OUT/'bake-triangles.bin');jobs.tofile(OUT/'bake-jobs.bin')
    # Jobs are grouped by material, so retain the same order for exclusions.
    np.concatenate([np.full(int((mi==i).sum()),name!='sky' and name not in transparent and name not in foliage,np.uint8) for i,name in enumerate(names)]).tofile(OUT/'bake-casters.bin')
    (OUT/'bake.json').write_text(json.dumps(dict(width=resolution,height=resolution,pages=pages,triangles=len(tris)),indent=2))
    validate_index_padding(meshes,indices,sorts)
    count=len(meshes)//28;refs=np.arange(count,dtype='<u2').tobytes();nodes,refs,objects=build_camera_visibility(bounds,refs)
    level=bytearray(old[0x7b]);struct.pack_into('<3I',level,0,count,count,count)
    low=np.minimum(np.array(report['bounds'][0]),[-16384,-16384,-8192]);high=np.maximum(np.array(report['bounds'][1]),[16384,16384,8192])
    # Native gameplay/menu environments are separate. The main light is scoped
    # over the entire arena; the native menu area remains far outside it.
    lights=read_lumps(ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp',(0x36,))[0x36][:448]
    from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
    wl=[WorldLightv3.from_bytes(lights[i:i+112]) for i in range(0,448,112)]
    wl[0].intensity=[.055,.07,.085];wl[0].origin=[0,0,2048];wl[2].origin=[0,0,12000];wl[2].intensity=[.62,.69,.8];wl[2].normal=[-.6178957224,.4823191166,-.6209453344]
    from repair_environment_lighting import entities
    native_entities=entities(ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp')
    env=[dict(e) for e in native_entities if e.get('classname')=='light_environment'];env[0].update(origin='0 0 12000',angles='38.4 142 0',pitch='-38.4',_light='224 238 255 204',_ambient='185 208 230 30',targetname='composite_sun')
    rows=[dict(classname='worldspawn',mapversion='220',skyname='sky_day',detailvbsp='detail.vbsp'),*env,*[dict(e) for e in native_entities if e.get('script_name') in ('menu_scene_ref','menu_camera_target')]]
    menu_volume=json.loads((ROOT/'logs/native-light-volumes.json').read_text())['mp_coliseum'][0]
    rows.append({k:v for k,v in menu_volume.items() if k not in ('link_guid','link_to_guid_0')})
    flags={'gamemode_'+m:'1' for m in ('tdm','at','ctf','cp','ffa','lts','fw','fd','lh')}
    # Initial native starts; actual floor/hull probes refine these after loading.
    for team,x,yaw in ((2,-2400,0),(3,2400,180)):
        for y in (-1600,-1400,-1200):
            for dx in (-96,96):
                pos=f'{x+dx} {y} 160';rows.append(dict(classname='info_spawnpoint_human_start',origin=pos,angles=f'0 {yaw} 0',teamnumber=str(team),**flags));rows.append(dict(classname='info_spawnpoint_human',origin=pos,angles=f'0 {yaw} 0',teamnumber='0',**flags))
    rows.append(dict(classname='info_player_start',origin='3284 1314 160',angles='0 180 0'))
    # Fresh lighting data: no reused native ground lightmap texels.
    sky=np.broadcast_to(encode_rgbm(np.array([.055,.07,.085])),(resolution,resolution,4)).tobytes()+bytes([127,127,255,255])*(resolution*resolution)
    rtl=struct.pack('<I',0x00FFFFC0)*(resolution*resolution)+bytes([255,0,0,0])*(resolution*resolution)+bytes((resolution//2)**2*4)
    shadow=struct.pack('<6i3f',0,0,0,1,0,len(shadowm)//12,*wl[2].normal)+struct.pack('<6i3f',1,0,len(shadowm)//12,2,0,len(shadowm)//12,*wl[3].normal)
    changes.update({0:entity_bytes(rows),2:texture,3:positions,5:shadow,0xe:struct.pack('<6f2I',*low,*high,0,count),0x18:b'',0x1e:normals,0x2b:strings,0x2c:table,0x36:b''.join(w.as_bytes() for w in wl),0x49:lit,0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts,0x53:struct.pack('<I2H',1,resolution,resolution)*pages,0x62:sky*pages,0x69:rtl*pages,0x7a:struct.pack('<63h',0,*[-1]*62),0x77:nodes,0x78:refs,0x79:objects,0x7b:level,0x7c:shadowp,0x7e:shadowi,0x7f:shadowm,0x23:old[0x23],0x63:old[0x63],0x6a:struct.pack('<2i',-1,0),0x6b:struct.pack('<2H2h',0,0,1,-1)})
    # Source-independent optional structures must not address old meshes/probes.
    for lid in (4,6,7,0x47,0x48,0x4a,0x4b,0x4c,0x4d,0x64,0x65,0x66,0x67,0x68,0x6c,0x6d,0x6e,0x6f,0x70,0x71,0x72,0x73,0x74,0x75,0x76):changes[lid]=b''
    # GAME_LUMP embeds absolute file offsets. Let the compactor relocate its
    # native empty prop payload instead of treating it as raw replacement data.
    changes.pop(0x23,None)
    from repair_native_render_partitions import reorder
    ordered,_,_=reorder(changes);changes.update(ordered)
    native=OUT/(MAP+'.bsp');proof=compact(TEMPLATE,native,changes);budget=enforce_camera_bypass_budget(native)
    status=dict(source_map=report['source_map'],map=MAP,version='0.1.0',render_triangles=len(tris),render_repair={'world_meshes':count},geometry=report['bounds'],draw_budget=budget,build=proof,source_props=len(report['placements']),missing_props=len(report['omitted']),client_verified=False,lighting='Coarse source-scene bake pending',collision=json.loads((OUT/'physics.json').read_text())|{'owners':None,'missing':None})
    (OUT/'source-build.json').write_text(json.dumps(status,indent=2));stbsp(OUT,OUT/'materials',MAP,PAK_NAME)
    print('Built',native,'seconds',time.monotonic()-started,flush=True)
if __name__=='__main__':build()
