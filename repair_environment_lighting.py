"""Replace lighting only: correct sky occlusion and separate the native menu stage."""
import json,struct,shutil,math,hashlib
from apply_baked_lighting import ROOT,OUT,np,encode_rgbm,distance_transform_edt,Image
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from audit_world_draw_budget import audit
import sys
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.branches import shared
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3
SOURCE=ROOT/'output/phase-runner/preview-material-repaired/mp_phase_runner_preview.bsp'
TARGET=ROOT/'output/phase-runner/preview-environment-lighting/mp_phase_runner_preview.bsp'
NATIVE=ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp'
BAKE=OUT/'lighting-environment.bin'

def entities(path):
    result=[]
    for data in [read_lumps(path,[0])[0]]+[p.read_bytes() for p in path.parent.glob(path.stem+'_*.ent')]:
        if b'{' in data:result.extend(shared.Entities.from_bytes(data[data.index(b'{'):]))
    return result

def text_entities(values):
    return ('\n'.join('{\n'+'\n'.join('"'+k+'" "'+v+'"' for k,v in e.items())+'\n}' for e in values)+'\n\0').encode()

def static_shadow_meshes():
    tri=np.fromfile(OUT/'triangles.bin','<f4').reshape(-1,3,3)
    casters=np.fromfile(OUT/'environment-caster-mask.bin',np.uint8).astype(bool)
    selected=tri[casters];vertices=bytearray();indices=bytearray();meshes=bytearray()
    # The native shadow stream uses mesh-local uint16 indices and a separate
    # global vertex offset, as verified in Coliseum and Homestead. Exact-byte
    # welding reduces storage without moving a single caster vertex.
    for first in range(0,len(selected),8192):
        block=selected[first:first+8192].reshape(-1,3)
        _,keep,inverse=np.unique(block.view('V12').ravel(),return_index=True,return_inverse=True)
        if len(keep)>65536:raise ValueError('Shadow mesh index capacity exceeded')
        meshes.extend(struct.pack('<2I2h',len(vertices)//12,len(block)//3,1,-1))
        vertices.extend(block[keep].tobytes());indices.extend(inverse.astype('<u2').tobytes())
    return {0x7c:vertices,0x7e:indices,0x7f:meshes},dict(meshes=len(meshes)//12,triangles=len(selected),vertices=len(vertices)//12,
        native_indexing_verified=True,decorative_sky_excluded=True,alpha_tested_shadows=False)

def environment_records(shadow_mesh_count=0):
    native=read_lumps(NATIVE,[0x36,0x63])
    old=read_lumps(SOURCE,[0x36])
    lights=[WorldLightv3.from_bytes(native[0x36][i:i+112]) for i in range(0,448,112)]
    source=[WorldLightv3.from_bytes(old[0x36][i:i+112]) for i in (0,112)]
    # Native order is ambient0, ambient1, sun0, sun1. The hardware sun table
    # filters out ambient lights, so table slot 0 remains the gameplay sun.
    for dst,src in ((lights[0],source[0]),(lights[2],source[1])):
        dst.origin=src.origin;dst.intensity=src.intensity;dst.normal=src.normal
    normal=list(source[1].normal);pitch=math.degrees(math.asin(-normal[2]));yaw=math.degrees(math.atan2(normal[1],normal[0]))
    reference=entities(NATIVE)
    env=[dict(e) for e in reference if e.get('classname')=='light_environment']
    if [e['lightEnvironmentIndex'] for e in env]!=['*0','*1']:raise ValueError('Native environment order changed')
    main=env[0];main.update(origin=' '.join(map(str,source[1].origin)),angles=f'{pitch:.9f} {yaw:.9f} 0',pitch=f'{-pitch:.9f}',targetname='phase_runner_main_light',cloudoffset='0 0 0 0')
    def colour(v):
        v=np.array(list(v));scale=float(v.max())
        return ' '.join(str(int(round(x))) for x in list((v/scale)**(1/2.2)*255)+[scale*255])
    main['_ambient']=colour(source[0].intensity);main['_light']=colour(source[1].intensity)
    stage=[dict(e) for e in reference if e.get('script_name') in ('menu_scene_ref','menu_camera_target')]
    if len(stage)!=2:raise ValueError('Missing native menu anchors')
    volume=json.loads((ROOT/'logs/native-light-volumes.json').read_text())['mp_coliseum'][0]
    volume={k:v for k,v in volume.items() if k not in ('link_guid','link_to_guid_0')}
    ents=entities(SOURCE)+env+stage+[volume]
    # Native empty static-prop roots: no sprp models exist in this baked-world
    # port. Compiled world casters are addressed separately by the mesh range.
    # Do not invent prop references; Coliseum also has empty prop roots while
    # its shadow environments contain nonempty compiled-world mesh ranges.
    if len(native[0x63])!=64:raise ValueError('Native empty CSM roots changed')
    shadow=struct.pack('<6i3f',0,0,0,1,0,shadow_mesh_count,*lights[2].normal)
    shadow+=struct.pack('<6i3f',1,0,shadow_mesh_count,2,0,shadow_mesh_count,*lights[3].normal)
    return {0:text_entities(ents),5:shadow,0x36:b''.join(a.as_bytes() for a in lights),0x63:native[0x63]},normal

def build():
    report=json.loads((OUT/'scene.json').read_text());w,h,pages=(report[k] for k in ('width','height','pages'))
    casters=json.loads((OUT/'environment-casters.json').read_text())
    data=np.memmap(BAKE,dtype='<f4',mode='r',shape=(pages,h,w,5))
    mask=np.memmap(str(BAKE)+'.mask',dtype=np.uint8,mode='r',shape=(pages,h,w))
    if not np.isfinite(data).all():raise ValueError('Non-finite baked values')
    sky=bytearray();rtl=bytearray();stats=[]
    for k in range(pages):
        valid=mask[k].astype(bool)
        nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True)
        values=data[k][tuple(nearest)];photo=values[...,1]<0;sun=values[...,0]
        ambient=np.array([.025,.027,.032])*(.4+.6*np.maximum(values[...,1,None],0))
        # A photographed sky is background artwork, not a lit rock ceiling.
        # Its independent constant illumination prevents sun/character shadows
        # from appearing on the sky dome. No changes to material or sky UVs.
        ambient[photo]=[.8,.8,.8]
        a=encode_rgbm(ambient);b=np.empty((h,w,4),np.uint8)
        b[...,:3]=np.rint(np.clip((values[...,2:5]+1)/2.007874,0,1)*255).astype(np.uint8);b[...,3]=255
        sky.extend(a.tobytes());sky.extend(b.tobytes())
        ids=np.full((h,w),0x00FFFFC0,dtype='<u4');ids[photo]=0x00FFFFFF
        vis=np.zeros((h,w,4),np.uint8);vis[...,0]=np.rint(sun*255).astype(np.uint8)
        rtl.extend(ids.tobytes());rtl.extend(vis.tobytes());rtl.extend(bytes((w//2)*(h//2)*4))
        active=valid&~photo
        stats.append(dict(page=k,scene_luxels=int(active.sum()),photo_luxels=int((valid&photo).sum()),
            sun_unoccluded_fraction=float(sun[active].mean()),sky_visibility_mean=float(values[...,1][active].mean())))
        Image.fromarray(vis[...,0]).resize((512,512)).save(OUT/f'environment-sun-{k}.png')
        del nearest,values,photo,ambient,a,b,ids,vis,valid,active
    shadow_changes,shadow_proof=static_shadow_meshes()
    changes,normal=environment_records(shadow_proof['meshes']);changes.update(shadow_changes);changes.update({0x62:sky,0x69:rtl})
    proof=compact(SOURCE,TARGET,changes)
    status=json.loads(SOURCE.with_name('source-build.json').read_text())
    repair=dict(version='0.1.33',source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        casters=casters,pages=stats,main_sun_normal=normal,main_sun_hardware_index=0,menu_sun_hardware_index=1,
        main_light_environment_index=0,menu_light_environment_index=1,menu_stage_origin=[-11776,11856,12736],
        independent_photo_sky_light=.8,geometry_materials_and_lightmap_uvs_unchanged=True,
        collision_and_walkways_byte_unchanged=True,static_shadows_baked=True,dynamic_static_world_csm_meshes=shadow_proof,
        client_rendering_verified=False,compaction=proof,draw_budget=audit(TARGET))
    status['lighting_environment_repair']=repair
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for f in SOURCE.parent.iterdir():
        if f.suffix=='.stbsp' or f.name in ('render-placement-proof.json','tunnel-walkways.json','collision-ownership.json','tunnel-collision-repair.json'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps(repair,indent=2),flush=True)
if __name__=='__main__':build()
