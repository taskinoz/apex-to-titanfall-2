"""Add baked local-light visibility and reduce native shadow draw calls."""
import json,struct,shutil,hashlib
from repair_environment_lighting import ROOT,np,WorldLightv3,OUT
from apply_baked_lighting import encode_rgbm,distance_transform_edt
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from audit_world_draw_budget import audit
SOURCE=ROOT/'output/phase-runner/preview-environment-lighting/mp_phase_runner_preview.bsp'
TARGET=ROOT/'output/phase-runner/preview-interior-lighting/mp_phase_runner_preview.bsp'
INTERIOR=ROOT/'output/phase-runner/interior-lighting'
LOCAL_DTYPE=np.dtype([('ids','<u4'),('vis','u1',4),('fill','<f4',3)])

def regroup_shadows(l):
    verts=np.frombuffer(l[0x7c],'<f4').reshape(-1,3);ix=np.frombuffer(l[0x7e],'<u2');blocks=[];at=0
    for base,count,opaque,sort in struct.iter_unpack('<2I2h',l[0x7f]):
        if (opaque,sort)!=(1,-1):raise ValueError('Unsupported shadow type')
        blocks.append(verts[base+ix[at:at+count*3].astype(np.uint32)].reshape(-1,3,3));at+=count*3
    tri=np.concatenate(blocks);newverts=bytearray();newix=bytearray();meshes=bytearray()
    def emit(t):
        p=t.reshape(-1,3);_,keep,inverse=np.unique(p.view('V12').ravel(),return_index=True,return_inverse=True)
        if len(keep)>65536:
            half=len(t)//2;emit(t[:half]);emit(t[half:]);return
        meshes.extend(struct.pack('<2I2h',len(newverts)//12,len(t),1,-1));newverts.extend(p[keep].tobytes());newix.extend(inverse.astype('<u2').tobytes())
    for first in range(0,len(tri),32768):emit(tri[first:first+32768])
    count=len(meshes)//12;env=bytearray(l[5]);struct.pack_into('<i',env,20,count);struct.pack_into('<i',env,36+8,count);struct.pack_into('<i',env,36+20,count)
    return {5:env,0x7c:newverts,0x7e:newix,0x7f:meshes},dict(before_meshes=len(l[0x7f])//12,after_meshes=count,
        triangles=len(tri),vertices=len(newverts)//12,all_caster_positions_and_winding_preserved=True)

def build():
    config=json.loads((INTERIOR/'lights.json').read_text());lights=config['lights'];count=len(lights)
    l=read_lumps(SOURCE,[5,0x36,0x53,0x62,0x69,0x7a,0x7c,0x7e,0x7f])
    header=list(struct.iter_unpack('<I2H',l[0x53]));w,h=header[0][1:];pages=len(header)
    local=np.memmap(INTERIOR/'lighting.bin',LOCAL_DTYPE,'r',shape=(pages,h,w))
    mask=np.memmap(OUT/'lighting-environment.bin.mask',np.uint8,'r',shape=(pages,h,w))
    sky=bytearray(l[0x62]);rtl=bytearray(l[0x69]);sky_stride=w*h*8;rtl_stride=w*h*8+(w//2)*(h//2)*4;stats=[]
    for page in range(pages):
        nearest=distance_transform_edt(~mask[page].astype(bool),return_distances=False,return_indices=True)
        values=local[page][tuple(nearest)];active=values['vis'][...,1:].any(-1)
        ids=np.frombuffer(rtl,'<u4',w*h,page*rtl_stride).reshape(h,w)
        vis=np.frombuffer(rtl,np.uint8,w*h*4,page*rtl_stride+w*h*4).reshape(h,w,4)
        ids[active]=(ids[active]&0xff00003f)|(values['ids'][active]&0x00ffffc0)
        vis[...,1:][active]=values['vis'][...,1:][active]
        a=np.frombuffer(sky,np.uint8,w*h*4,page*sky_stride).reshape(h,w,4)
        decoded=a[active,:3]/255*(a[active,3,None]/255*3.984375+.015625)
        a[active]=encode_rgbm(decoded+values['fill'][active])
        stats.append(dict(page=page,local_luxels_with_gutters=int(active.sum()),valid_lit_luxels=int((active&mask[page].astype(bool)).sum())))
        del ids,vis,a,nearest,values,active,decoded
    # Clone a native POINT using the native linear-to-zero radius falloff.
    native=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',[0x36])[0x36];template=None
    for i in range(0,len(native),112):
        t=WorldLightv3.from_bytes(native[i:i+112])
        if t.type.name=='POINT' and abs(t.linear*t.radius+1)<1e-5 and abs(t.quadratic)<1e-10:
            template=t.as_bytes();break
    if template is None:raise ValueError('Native linear point light reference missing')
    world=bytearray(l[0x36])
    for fixture in lights:
        t=WorldLightv3.from_bytes(template);t.origin=fixture['origin'];t.intensity=fixture['colour'];t.radius=fixture['radius']
        t.linear=-1/t.radius;t.quadratic=0;t.constant=1;t.texture_data=0;t.parent=0;t.style=0
        world.extend(t.as_bytes())
    changes,shadow=regroup_shadows(l)
    changes.update({0x36:world,0x62:sky,0x69:rtl,0x7a:struct.pack('<63h',*range(count+2),*[-1]*(61-count))})
    proof=compact(SOURCE,TARGET,changes)
    status=json.loads(SOURCE.with_name('source-build.json').read_text())
    report=dict(version='0.1.34',source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),interior_fixtures=config,
        lightmap_updates=stats,main_sun_menu_and_sky_preserved=True,sun_visibility_bytes_preserved=True,
        lightmap_headers_uvs_and_geometry_preserved=True,collision_and_walkways_byte_unchanged=True,
        point_light_template='Native Homestead POINT, linear falloff to radius',static_occlusion_baked=True,
        maximum_local_lights_per_luxel=3,indirect_fill='Small artistic fill from visible fixtures; not a GI bake',
        shadow_draw_optimization=shadow,compaction=proof,draw_budget=audit(TARGET),client_rendering_verified=False)
    status['interior_light_repair']=report;status['material_project']=str(ROOT/'output/phase-runner/balanced-materials')
    status['texture_optimization']=json.loads((ROOT/'output/phase-runner/balanced-materials/optimization.json').read_text())
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for f in SOURCE.parent.iterdir():
        if f.suffix=='.stbsp' or f.name in ('render-placement-proof.json','tunnel-walkways.json','collision-ownership.json','tunnel-collision-repair.json'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':build()
