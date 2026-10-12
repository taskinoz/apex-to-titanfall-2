"""Recover source screen assemblies and isolate the native menu stage (0.5.0)."""
import json,os,struct,sys,subprocess
from pathlib import Path
import recover_composite_details as recovery
from repair_environment_lighting import entities,text_entities
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from stage_prop_geometry import rotation
from read_vg_static import load
np=recovery.np
ROOT=recovery.ROOT;OUT=recovery.OUT;MAP=recovery.MAP
WORK=OUT/'screen-repair';BACKUP=ROOT/'output/repair-backups/20261007-before-screen-repair'
recovery.WORK=WORK;recovery.BACKUP=BACKUP
MODEL_LODS={'thunderdome_screen_tower_arm_01':2,'flexscreen_frame_olympus':2,
            'composite_big_screen_01':2,'composite_screen_animation_01':0}
MENU_DELTA=np.array([-13224.,12144.,11264.]) # scene ref -> (-25000,24000,24000)

def plan():
    WORK.mkdir(exist_ok=True)
    audit=json.loads((OUT/'asset-audit.json').read_text());inventory=json.loads((OUT/'source-inventory.json').read_text())['props']
    scene=json.loads((OUT/'scene.json').read_text());present={p['index'] for p in scene['placements']}
    sections=[];cols=[];rows=[]
    for p in inventory:
        base=Path(p['model']).stem
        if base not in MODEL_LODS or p['index'] in present or not(abs(p['origin'][0])<5000 and -500<p['origin'][1]<8000):continue
        folder=Path(audit['model_paths'][p['model']]);lod=0 if p['index']==8185 else MODEL_LODS[base]
        raw,slots,skins=load(folder,lod);raw=[np.array(s,'<f4').reshape(-1,3,8) for s in raw]
        # The small emissive screen overlay is absent in the low author LOD.
        # Restore only that original section; keep the economical frame LOD.
        if base=='composite_big_screen_01' and lod>0:
            high,hslots,hskins=load(folder,0)
            raw[-1]=np.array(high[-1],'<f4').reshape(-1,3,8)
        skin=skins[min(p['skin'],len(skins)-1)];matrix=np.array(rotation(p['angles']))
        for sec,slot in zip(raw,slots):
            if not len(sec):continue
            name=skin[slot]
            material=ROOT/'tools/composite-legion/exported_files/materials'/name/(name+'_albedoTexture.dds')
            if not material.exists():raise ValueError('Missing source albedo: '+name)
            t=sec.copy();t[:,:,:3]=sec[:,:,:3]@matrix.T*p['scale']+p['origin'];t[:,:,3:6]=sec[:,:,3:6]@matrix.T;t[:,:,7]=1-sec[:,:,7]
            sections.append((name,t))
        row={**p,'folder':str(folder),'lod':lod,'triangles':sum(map(len,raw)),'recovery':'Source VG; original overlay section retained'}
        if base=='composite_screen_animation_01':
            col=np.empty((0,3,3),'f4');method='Decorative screen; existing room boundary clip retained'
        else:
            col,method=recovery.collision(row,raw)
        cols.append(col);rows.append({**row,'collision_triangles':len(col),'collision_recovery':method})
    names=list(dict.fromkeys(n for n,t in sections));tri=np.concatenate([t for n,t in sections]);mi=np.concatenate([np.full(len(t),names.index(n),'i4') for n,t in sections])
    if len(rows)!=43 or len(tri)>5600:raise ValueError('Unexpected source recovery or index budget')
    np.savez(WORK/'addition.npz',triangles=tri,material=mi,names=np.array(names),collision=np.concatenate(cols))
    report=dict(version='0.5.0',added_props=len(rows),added_triangles=len(tri),placements=rows,
                policy='All fifteen banner frame/arm pairs, seven wall screens, six original room closure screens; source transforms, under 90% index capacity')
    (WORK/'plan.json').write_text(json.dumps(report,indent=2));print('Planned',len(rows),'source objects,',len(tri),'triangles',flush=True)

def menu():
    receipt=WORK/'menu.json'
    if receipt.exists():raise ValueError('Menu relocation already applied')
    from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
    rows=entities(MAP);moved=[]
    for e in rows:
        if e.get('script_name') in ('menu_scene_ref','menu_camera_target') or e.get('lightEnvironmentIndex')=='*1':
            before=e['origin'];p=np.array(list(map(float,before.split())))+MENU_DELTA
            e['origin']=' '.join(map(str,p));moved.append(dict(classname=e['classname'],script_name=e.get('script_name'),before=before,after=e['origin']))
    if len(moved)!=4:raise ValueError('Unexpected native menu entities')
    data=bytearray(read_lumps(MAP,[0x36])[0x36])
    for index in (1,3):
        wl=WorldLightv3.from_bytes(data[index*112:(index+1)*112]);wl.origin=np.array(list(wl.origin))+MENU_DELTA;data[index*112:(index+1)*112]=wl.as_bytes()
    temp=MAP.with_suffix('.menu.bsp');compact(MAP,temp,{0:text_entities(rows),0x36:data});os.replace(temp,MAP)
    receipt.write_text(json.dumps(dict(delta=MENU_DELTA.tolist(),entities=moved,reason='Native client menu actors and effects were inside the photographic sky sphere; preserve relative scene/camera/light-volume transforms outside it'),indent=2))
    print('Moved native menu stage beyond the sky dome',flush=True)

def screen_pass():
    """Use native transparency for the six source forcefield surfaces."""
    ids=(2,3,0xe,0x49,0x4f,0x50,0x51,0x52,0x64,0x77,0x78,0x79,0x7b,0x7c,0x7e,0x7f)
    b={k:bytearray(v) for k,v in read_lumps(MAP,ids).items()}
    from repair_native_render_partitions import reorder
    l=read_lumps(MAP,(0x2b,0x2c));texture=None
    for at in range(0,len(b[2]),36):
        st=struct.unpack_from('<I',b[2],at+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0]
        if l[0x2b][off:l[0x2b].index(0,off)].decode().replace('\\','/').endswith('/composite_big_screen_animation_01'):texture=at//36
    if texture is None:raise ValueError('Missing source closure screen material')
    struct.pack_into('<I',b[2],texture*36+32,0xa10);count=0
    for at in range(0,len(b[0x50]),28):
        sort=struct.unpack_from('<H',b[0x50],at+22)[0]
        if struct.unpack_from('<h',b[0x52],sort*12)[0]==texture:
            flags=struct.unpack_from('<I',b[0x50],at+24)[0];struct.pack_into('<I',b[0x50],at+24,flags|0x10);count+=struct.unpack_from('<H',b[0x50],at+4)[0]
    a=np.load(WORK/'addition.npz');names=a['names'];mi=a['material'];faces=a['triangles'][mi==list(names).index('composite_big_screen_animation_01'),:,:3];a.close()
    from repair_composite_source_layout import canon
    shadow=np.frombuffer(b[0x7c],'<f4').reshape(-1,3,3);mask=np.isin(canon(shadow),canon(faces))
    for ti in np.flatnonzero(mask):
        i=struct.unpack_from('<H',b[0x7e],int(ti)*6)[0];struct.pack_into('<3H',b[0x7e],int(ti)*6,i,i,i)
    if count!=12 or mask.sum()!=12:raise ValueError('Wrong screen pass coverage')
    b.update(reorder(b)[0]);temp=MAP.with_suffix('.screen-pass.bsp');compact(MAP,temp,b);os.replace(temp,MAP)
    # Keep the canonical caster cache consistent for future incremental bakes.
    count0=json.loads((BACKUP/'scene.json').read_text())['triangles'];caster=np.fromfile(WORK/'bake-casters.bin','u1')
    ordered=np.concatenate([np.full(int((mi==i).sum()),str(name)=='composite_big_screen_animation_01','u1') for i,name in enumerate(names)])
    caster[count0:][ordered.astype(bool)]=0;caster.tofile(WORK/'bake-casters.bin')
    (WORK/'screen-pass.json').write_text(json.dumps(dict(translucent_source_triangles=count,disabled_shadow_triangles=int(mask.sum()),opacity=.2),indent=2))

def lighting():
    """Reassign two unused hardware slots; update only affected chart/probe RTL."""
    from build_composite_map import DT
    from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
    from light_composite import LOCAL
    from scipy.ndimage import distance_transform_edt
    receipt=WORK/'lighting.json'
    if receipt.exists():raise ValueError('Targeted lighting already applied')
    cfg=json.loads((OUT/'interior-lights.json').read_text());old=cfg['lights'];es=json.loads((OUT/'source-inventory.json').read_text())['entities']['mp_rr_arena_composite_env.ent']
    # Native IDs 3 and 4 had zero surface references in the existing bake.
    rows=[]
    for slot,index in ((3,309),(4,51)):
        e=es[index];c=list(map(float,e['_light'].split()));radius=min(1800,max(256,float(e['_zero_percent_distance'])))
        rows.append(dict(hardware_index=slot,source_entity=index,source_class=e['classname'],origin=list(map(float,e['origin'].split())),radius=radius,colour=((np.array(c[:3])/255)**2.2*min(2,max(.35,c[3]/1500))).tolist()))
    lights=[next((r for r in rows if r['hardware_index']==e['hardware_index']),e) for e in old]
    fixture=np.zeros(60,np.dtype([('p','<f4',3),('radius','<f4'),('colour','<f4',3),('index','<u4')]))
    for i,e in enumerate(lights):fixture[i]=(e['origin'],e['radius'],e['colour'],e['hardware_index'])
    fixture.tofile(WORK/'fixtures.bin')
    lids=(3,0x1e,0x36,0x49,0x4f,0x50,0x52,0x62,0x65,0x69,2,0x2b,0x2c)
    l=read_lumps(MAP,lids);positions=np.frombuffer(l[3],'<f4').reshape(-1,3);normals=np.frombuffer(l[0x1e],'<f4').reshape(-1,3);vertices=np.frombuffer(l[0x49],DT);indices=np.frombuffer(l[0x4f],'<u2')
    jobs=[];casters=[];emissive=[]
    for at in range(0,len(l[0x50]),28):
        first,n=struct.unpack_from('<IH',l[0x50],at);sort=struct.unpack_from('<H',l[0x50],at+22)[0];material,page,_,_,base=struct.unpack_from('<3hHI',l[0x52],sort*12)
        ix=indices[first:first+n*3].reshape(-1,3).astype('u4')+base;v=vertices[ix]
        j=np.zeros(n,recovery.JOB);j['p']=positions[v['pi']];j['n']=normals[v['ni']];j['uv']=v['light'][:,:,:2]*2048;j['page']=page
        flag=struct.unpack_from('<I',l[0x50],at+24)[0];st=struct.unpack_from('<I',l[2],material*36+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0];name=l[0x2b][off:l[0x2b].index(0,off)].decode()
        cast=np.full(n,not bool(flag&0x10) and not name.endswith('\\sky'),'u1');cast[np.linalg.norm(np.cross(j['p'][:,1]-j['p'][:,0],j['p'][:,2]-j['p'][:,0]),axis=1)<1e-5]=0
        glow=np.zeros(n,'u1')
        if name.endswith('\\composite_big_screen_animation_01'):glow[:]=2
        elif name.endswith('\\beacon_big_screen_animation_01'):glow[:]=1
        elif name.endswith('\\composite_big_screen_01'):glow[(v['uv'][:,:,1]<.48).all(1)]=1
        jobs.append(j);casters.append(cast);emissive.append(glow)
    jobs=np.concatenate(jobs);casters=np.concatenate(casters);emissive=np.concatenate(emissive);centers=jobs['p'].mean(1)
    affected=np.zeros(len(jobs),bool)
    for e in rows:affected|=(np.linalg.norm(centers-e['origin'],axis=1)<e['radius']+256)
    uv=jobs['uv'].copy();jobs['uv'][~affected]=-10
    jobs['p'].astype('<f4').tofile(WORK/'rtl-triangles.bin');jobs.tofile(WORK/'rtl-jobs.bin');casters.tofile(WORK/'rtl-casters.bin')
    subprocess.run([str(ROOT/'tools/bake_interior_lighting.exe'),str(WORK/'rtl-triangles.bin'),str(WORK/'rtl-jobs.bin'),str(WORK/'fixtures.bin'),str(WORK/'rtl-local.bin'),'2048','2048','4',str(WORK/'rtl-casters.bin')],check=True)
    loc=np.fromfile(WORK/'rtl-local.bin',LOCAL).reshape(4,2048,2048);buf=bytearray(l[0x69]);ambient=bytearray(l[0x62]);sky=np.frombuffer(ambient,'u1').reshape(4,2,2048,2048,4);stride=2048**2*8+1024**2*4
    changed=0;glowcharts=0;newrefs={3:0,4:0}
    for i in np.flatnonzero(affected|(emissive>0)):
        page=int(jobs['page'][i]);x=int(uv[i,0,0]//4)*4;y=int(uv[i,0,1]//4)*4
        if affected[i] and casters[i]:
            tile=loc[page,y:y+4,x:x+4];valid=tile['vis'][:, :,1:].any(-1)
            # Unlit samples are also valid raster receivers. Use the known six
            # four-texel triangle samples instead of a light-dependent mask.
            valid=np.array([[1,1,1,0],[1,1,0,0],[1,0,0,0],[0,0,0,0]],bool)
            nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True);v=tile[tuple(nearest)]
            ids=np.ndarray((2048,2048),'<u4',buffer=buf,offset=page*stride);vis=np.ndarray((2048,2048,4),'u1',buffer=buf,offset=page*stride+2048**2*4)
            ids[y:y+4,x:x+4]=v['ids'];vis[y:y+4,x:x+4,1:]=v['vis'][:,:,1:];changed+=1
            for k in range(1,4):
                for slot in newrefs:newrefs[slot]+=int(((v['ids']>>(6*k)&63)==slot).sum())
        if emissive[i]:
            colour=np.array([.4,.8,.8]) if emissive[i]==2 else np.array([.8,.8,.8])
            sky[page,0,y:y+4,x:x+4]=recovery.encode_rgbm(colour);glowcharts+=1
    world=bytearray(l[0x36])
    for e in rows:
        # Ambient environments are filtered out of the hardware index table.
        offset=(e['hardware_index']+2)*112;wl=WorldLightv3.from_bytes(world[offset:offset+112]);wl.origin=e['origin'];wl.intensity=e['colour'];wl.radius=e['radius'];wl.linear=-1/wl.radius;wl.quadratic=0;wl.constant=1;world[offset:offset+112]=wl.as_bytes()
    points=np.fromfile(OUT/'probe-positions.bin','<f4').reshape(-1,3);near=np.zeros(len(points),bool)
    for e in rows:near|=np.linalg.norm(points-e['origin'],axis=1)<e['radius']
    jobs['p'][casters.astype(bool)].astype('<f4').tofile(WORK/'probe-casters.bin');points.tofile(WORK/'probe-positions.bin')
    subprocess.run([str(ROOT/'tools/bake_character_probes.exe'),str(WORK/'probe-casters.bin'),str(WORK/'probe-positions.bin'),str(WORK/'fixtures.bin'),str(WORK/'probe-lighting.bin')],check=True)
    values=np.fromfile(WORK/'probe-lighting.bin','<f4').reshape(len(points),24);values[:,:12]*=np.array([3.6]*4+[3.703704]*4+[3.75]*4);probes=bytearray(l[0x65])
    for i in np.flatnonzero(near):
        r=values[i];probes[i*48:(i+1)*48]=struct.pack('<16h4B4hI',*np.rint(np.clip(r[:16]*8192,-32768,32767)).astype(int),*r[16:20].astype(int),*r[20:24].astype(int),0)
    temp=MAP.with_suffix('.hall-light.bsp');compact(MAP,temp,{0x36:world,0x62:ambient,0x69:buf,0x65:probes});os.replace(temp,MAP)
    temp=OUT/'fixtures.screen.bin';fixture.tofile(temp);os.replace(temp,OUT/'fixtures.bin');cfg['lights']=lights;cfg['screen_repair_reassignments']=rows;temp=OUT/'interior-lights.screen.json';temp.write_text(json.dumps(cfg,indent=2));os.replace(temp,OUT/'interior-lights.json')
    np.savez(WORK/'lighting-scope.npz',jobs=recovery.np.array(jobs),uv=uv,affected=affected,emissive=emissive,probes=near)
    receipt.write_text(json.dumps(dict(source_lights=rows,previous_slots=[e for e in old if e['hardware_index'] in (3,4)],updated_chart_count=changed,illuminated_screen_charts=glowcharts,updated_probes=int(near.sum()),new_light_luxel_references=newrefs,approximation='Source spots treated as points; source screen appearances frozen with constant chart illumination, no animated emissive shader'),indent=2));print('Lit hall charts',changed,'screen charts',glowcharts,'probes',int(near.sum()),'references',newrefs,flush=True)

if __name__=='__main__':
    action=sys.argv[1]
    if action=='plan':plan()
    elif action=='materials':recovery.snapshot();recovery.stage_materials()
    elif action=='append':recovery.append(OUT/'detail-recovery')
    elif action=='menu':menu()
    elif action=='screen-pass':screen_pass()
    elif action=='lighting':lighting()
    else:raise ValueError('Unknown action')
