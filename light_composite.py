"""Bake source-positioned interior light visibility and native character probes."""
import json,struct,sys,subprocess,itertools,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'));sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from scipy.ndimage import distance_transform_edt
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
from apply_baked_lighting import encode_rgbm
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_character_lighting import make_tree
OUT=ROOT/'output/composite';SOURCE=OUT/'mp_arena_composite.bsp'
LOCAL=np.dtype([('ids','<u4'),('vis','u1',4),('fill','<f4',3)])

def fixtures():
    source=json.loads((OUT/'source-inventory.json').read_text())['entities']['mp_rr_arena_composite_env.ent']
    candidates=[]
    for index,e in enumerate(source):
        if e.get('classname') not in ('light','light_spot'):continue
        p=np.array(list(map(float,e['origin'].split())))
        if not (abs(p[0])<6000 and -2000<p[1]<9000 and -1000<p[2]<5000):continue
        c=list(map(float,e.get('_light','255 255 255 255').split()))
        radius=min(1800,max(256,float(e.get('_zero_percent_distance',e.get('_distance','800')))))
        colour=(np.array(c[:3])/255)**2.2*min(2,max(.35,c[3]/1500))
        candidates.append(dict(source_entity=index,source_class=e['classname'],origin=p.tolist(),radius=radius,colour=colour.tolist()))
    # Spatial coverage, rather than the first sixty lights in entity order.
    positions=np.array([e['origin'] for e in candidates]);picked=[int(np.linalg.norm(positions-[0,2400,800],axis=1).argmin())]
    distance=np.full(len(positions),np.inf)
    while len(picked)<min(60,len(candidates)):
        distance=np.minimum(distance,np.linalg.norm(positions-positions[picked[-1]],axis=1));distance[picked]=-1
        picked.append(int(distance.argmax()))
    lights=[dict(candidates[j],hardware_index=i+2) for i,j in enumerate(picked)]
    a=np.zeros(len(lights),np.dtype([('p','<f4',3),('radius','<f4'),('colour','<f4',3),('index','<u4')]))
    for i,e in enumerate(lights):a[i]=(e['origin'],e['radius'],e['colour'],e['hardware_index'])
    a.tofile(OUT/'fixtures.bin');(OUT/'interior-lights.json').write_text(json.dumps(dict(source_local_lights=len(candidates),lights=lights,approximation='Spatially selected source lights; spot lights approximated as points'),indent=2))
    return lights

def build():
    cfg=json.loads((OUT/'bake.json').read_text());w,h,pages=cfg['width'],cfg['height'],cfg['pages'];lights=fixtures()
    subprocess.run([str(ROOT/'tools/bake_interior_lighting.exe'),str(OUT/'bake-triangles.bin'),str(OUT/'bake-jobs.bin'),str(OUT/'fixtures.bin'),str(OUT/'local-lighting.bin'),str(w),str(h),str(pages),str(OUT/'bake-casters.bin')],check=True)
    l=read_lumps(SOURCE,(0,4,5,0x36,0x7c,0x7e,0x7f));data=np.memmap(OUT/'baked-lighting.bin','<f4','r',shape=(pages,h,w,5));mask=np.memmap(OUT/'baked-lighting.bin.mask',np.uint8,'r',shape=(pages,h,w));local=np.memmap(OUT/'local-lighting.bin',LOCAL,'r',shape=(pages,h,w))
    sky=bytearray();rtl=bytearray();stats=[]
    scene=np.load(OUT/'scene.npz');names=list(scene['names']);sky_material=names.index('sky');sky_first=int((scene['material']<sky_material).sum());sky_count=int((scene['material']==sky_material).sum())
    for k in range(pages):
        nearest=distance_transform_edt(~mask[k].astype(bool),return_distances=False,return_indices=True);values=data[k][tuple(nearest)];loc=local[k][tuple(nearest)]
        tile=k*(w//4)*(h//4)+(nearest[0]//4)*(w//4)+nearest[1]//4;photo=(tile>=sky_first)&(tile<sky_first+sky_count)
        ambient=np.array([.09,.10,.12])*(.65+.35*np.maximum(values[...,1,None],0))+loc['fill'];ambient[photo]=[.8,.8,.8]
        a=encode_rgbm(ambient);b=np.empty((h,w,4),np.uint8);b[...,:3]=np.rint(np.clip((values[...,2:5]+1)/2.007874,0,1)*255).astype(np.uint8);b[...,3]=255
        sky.extend(a.tobytes());sky.extend(b.tobytes());ids=loc['ids'].copy();vis=loc['vis'].copy();vis[...,0]=np.rint(values[...,0]*255).astype(np.uint8);rtl.extend(ids.tobytes());rtl.extend(vis.tobytes());rtl.extend(bytes((w//2)*(h//2)*4))
        stats.append(dict(page=k,sunlit=float(values[...,0][mask[k].astype(bool)].mean()),local_luxels=int(loc['vis'][...,1:].any(-1).sum())))
    native=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',(0x36,))[0x36]
    template=next(WorldLightv3.from_bytes(native[i:i+112]).as_bytes() for i in range(0,len(native),112) if WorldLightv3.from_bytes(native[i:i+112]).type.name=='POINT' and abs(WorldLightv3.from_bytes(native[i:i+112]).linear*WorldLightv3.from_bytes(native[i:i+112]).radius+1)<1e-5)
    world=bytearray(l[0x36])
    for e in lights:
        t=WorldLightv3.from_bytes(template);t.origin=e['origin'];t.intensity=e['colour'];t.radius=e['radius'];t.linear=-1/t.radius;t.quadratic=0;t.constant=1;t.texture_data=0;t.parent=0;t.style=0;world.extend(t.as_bytes())
    points=np.unique(np.array(list(itertools.product(range(-4608,4609,512),range(-512,7681,512),(0,160,320,512,768,1024,1536,2048,4096))),'<f4'),axis=0);points.tofile(OUT/'probe-positions.bin')
    triangles=np.fromfile(OUT/'bake-triangles.bin','<f4').reshape(-1,3,3);casters=np.fromfile(OUT/'bake-casters.bin',np.uint8).astype(bool);triangles[casters].tofile(OUT/'probe-casters.bin')
    subprocess.run([str(ROOT/'tools/bake_character_probes.exe'),str(OUT/'probe-casters.bin'),str(OUT/'probe-positions.bin'),str(OUT/'fixtures.bin'),str(OUT/'probe-lighting.bin')],check=True)
    values=np.fromfile(OUT/'probe-lighting.bin','<f4').reshape(len(points),24)
    # Match the surface ambient floor; preserve the baked sky direction and IDs.
    values[:,:12]*=np.tile([3.6]*4+[3.703704]*4+[3.75]*4,(len(points),1))
    probes=b''.join(struct.pack('<16h4B4hI',*np.rint(np.clip(row[:16]*8192,-32768,32767)).astype(int),*row[16:20].astype(int),*row[20:24].astype(int),0) for row in values)
    tree,order=make_tree(points);references=b''.join(struct.pack('<3fIi',*points[i],int(i),0) for i in order);parent=struct.pack('<i6I',0,0,len(points),0,len(points),0,len(tree)//8)
    # Replace provisional starts with floor/hull-verified opposing team starts.
    from repair_environment_lighting import entities
    from build_composite_map import entity_bytes
    rows=[e for e in entities(SOURCE) if not e.get('classname','').startswith('info_spawnpoint')]
    proof=json.loads((OUT/'team-spawn-probes.json').read_text())['data'];safe=[p['origin'] for p in proof if p['floor'] and p['pilot']]
    for p in safe:
        team=2 if p[0]<0 else 3;yaw=0 if team==2 else 180
        for kind,number in (('info_spawnpoint_human_start',team),('info_spawnpoint_human',0)):
            rows.append(dict(classname=kind,origin=' '.join(map(str,p)),angles=f'0 {yaw} 0',teamnumber=str(number),gamemode_tdm='1',gamemode_ffa='1',gamemode_ps='1'))
    titan_proof=json.loads((OUT/'spawn-probes-corrected.json').read_text())['data']
    titan_safe=[p['origin'] for p in titan_proof if p['floor'] and p['pilot'] and p['titan'] and abs(p['origin'][0])>=2000]
    for p in titan_safe:
        team=2 if p[0]<0 else 3;yaw=0 if team==2 else 180
        for kind,number in (('info_spawnpoint_titan_start',team),('info_spawnpoint_titan',0)):
            rows.append(dict(classname=kind,origin=' '.join(map(str,p)),angles=f'0 {yaw} 0',teamnumber=str(number),gamemode_tdm='1',gamemode_ffa='1'))
    changes={0:entity_bytes(rows),4:parent,0x36:world,0x62:sky,0x69:rtl,0x7a:struct.pack('<63h',*range(len(lights)+2),*[-1]*(61-len(lights))),0x65:probes,0x67:tree,0x68:references}
    target=OUT/'mp_arena_composite-lit.bsp';compact(SOURCE,target,changes);os.replace(target,SOURCE)
    report=dict(surface_pages=pages,chart_resolution='Four texels per triangle',source_sky_projection='Photographic sphere approximation',interior_lights=len(lights),character_probes=len(points),team_starts=len(safe),titan_starts=len(titan_safe),lightmap_stats=stats,limitations=['No bounced GI or new reflection cubemaps','Source spot lights approximated as points','Native alpha approximation; multilayer glass and source vertex colours not yet reproduced'])
    (OUT/'lighting.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':build()
