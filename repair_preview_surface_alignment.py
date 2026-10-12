"""Build the next preview with native sweep bevels and corrected draw metadata."""
import json,shutil,struct
from pathlib import Path
from compact_preview_bsp import compact
from repair_preview_index_padding import read_lumps,validate_index_padding
from preview_visibility import build_visibility,validate_visibility

ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

def tighten_and_filter(meshes,indices,sorts,bounds,textures,names,table):
    outmesh=bytearray();outindex=bytearray();outbounds=bytearray();removed=[];changed=0
    for mi in range(len(meshes)//28):
        r=bytearray(meshes[mi*28:mi*28+28]);first,count,minimum,span=struct.unpack_from('<I3H',r)
        si=struct.unpack_from('<H',r,22)[0];tex=struct.unpack_from('<h',sorts,si*12)[0]
        ni=struct.unpack_from('<I',textures,tex*36+12)[0];off=struct.unpack_from('<I',table,ni*4)[0]
        name=names[off:names.index(0,off)].decode().replace('\\','/')
        if name.rsplit('/',1)[-1].startswith('ar_arena_start_barrier'):
            removed.append({'mesh':mi,'triangles':count,'material':name,'bounds':struct.unpack_from('<8f',bounds,mi*32)})
            continue
        ids=struct.unpack_from('<'+'H'*(count*3),indices,first*2);lo=min(ids);hi=max(ids)
        changed+=int((lo,hi-lo)!=(minimum,span))
        struct.pack_into('<I3H',r,0,len(outindex)//2,count,lo,hi-lo)
        outindex.extend(indices[first*2:(first+count*3)*2])
        if count&1:outindex.extend(struct.pack('<3H',ids[-1],ids[-1],ids[-1]))
        outmesh.extend(r);outbounds.extend(bounds[mi*32:mi*32+32])
    checks=validate_index_padding(outmesh,outindex,sorts)
    return outmesh,outindex,outbounds,{'vertex_ranges_tightened':changed,'removed_arena_barriers':removed,'padding_validation':checks}

def uniform_lightmaps(headers,sky,rtl,uv=(.25015666584,.13143643240)):
    # Preserve the native page dimensions and encoding. Calibrate flat lighting
    # from the known lit floor sample; copy no spatial native scene illumination.
    outsky=bytearray();outrtl=bytearray();sa=ra=0;report=[]
    for kind,w,h in struct.iter_unpack('<I2H',headers):
        pixels=w*h;plane=pixels*4;x=min(w-1,int(uv[0]*w));y=min(h-1,int(uv[1]*h));samples=[]
        for j in range(2):
            at=sa+j*plane+(y*w+x)*4;sample=sky[at:at+4]
            if len(sample)!=4:raise ValueError('Invalid sky illumination sample')
            outsky.extend(sample*pixels);samples.append(list(sample))
            # RTL coordinates in the preview are zero. Preserve that calibration
            # without retaining another map's baked pixel patterns.
            pixel=rtl[ra+j*plane:ra+j*plane+4]
            if len(pixel)!=4:raise ValueError('Invalid real-time illumination sample')
            outrtl.extend(pixel*pixels)
        # Native internal lightmaps also carry the half-resolution third plane.
        half=rtl[ra+2*plane:ra+2*plane+4]
        outrtl.extend(half*(pixels//4))
        report.append({'width':w,'height':h,'sky_rgba':samples,'native_spatial_pixels_retained':False})
        sa+=2*plane;ra+=2*plane+pixels
    if len(outsky)!=len(sky) or len(outrtl)!=len(rtl):raise ValueError('Lightmap page layout changed')
    return outsky,outrtl,report

def build():
    src=P/'preview-index-repaired/mp_phase_runner_preview.bsp';out=P/'preview-aligned/mp_phase_runner_preview.bsp'
    ids=(2,0xe,0x2b,0x2c,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,0x7b)
    l=read_lumps(src,ids)
    meshes,indices,bounds,draw=tighten_and_filter(l[0x50],l[0x4f],l[0x52],l[0x51],l[2],l[0x2b],l[0x2c])
    if sum(r['triangles'] for r in draw['removed_arena_barriers'])!=108:raise ValueError('Unexpected arena barrier geometry')
    nodes,refs,objects=build_visibility(bounds,leaf_size=16);vis=validate_visibility(nodes,refs,objects,bounds)
    world=bytearray(l[0xe]);level=bytearray(l[0x7b]);total=len(meshes)//28
    struct.pack_into('<I',world,28,total);struct.pack_into('<3I',level,0,total,total,total)
    sky,rtl,lighting=uniform_lightmaps(l[0x53],l[0x62],l[0x69])
    repair=P/'hull-edge-repair';collision={int(f.stem,16):f.read_bytes() for f in repair.glob('*.bin')}
    if set(collision)!={1,0x5c,0x5d,0x5e,0x5f}:raise ValueError('Incomplete collision edge repair')
    changes={**collision,0x50:meshes,0x4f:indices,0x51:bounds,0x77:nodes,0x78:refs,0x79:objects,0xe:world,0x7b:level,0x62:sky,0x69:rtl}
    compaction=compact(src,out,changes);status=json.loads(src.with_name('source-build.json').read_text())
    edge=json.loads((repair/'report.json').read_text())
    status['hull_clearance_probes']=edge['clearance_probes']
    status['surface_alignment_repair']={'version':'0.1.23','draw':draw,'collision':{k:v for k,v in edge.items() if k not in ('changed_brushes','complex_brushes_deferred')},
        'deferred_complex_colliders':len(edge['complex_brushes_deferred']),'illumination_pages':lighting,
        'native_scene_shadow_meshes_present':False,'cell_lookup_assigns_same_cell_everywhere':True,
        'runtime_out_of_bounds_culling_not_established':True,'arena_barrier_collision_not_removed':True,
        'ramp_material_and_pbr_investigation_pending_location':True,'client_rendering_and_movement_verified':False,
        'limitations':['Swept player collision is corrected where bevel reconstruction succeeds. Complex rock/tube colliders and missing collision remain unfinished.',
            'Uniform preview illumination replaces borrowed spatial lightmaps; final directional lighting and shadows require a real bake.',
            'Start barrier visuals are removed. Their source collision ownership is not inferred from nearby bounds.',
            'Native-sized vertex spans replace broad material-batch spans; remaining client pop-in needs verification.']}
    status['render_triangles']=draw['padding_validation']['render_triangles'];status['render_repair']['world_meshes']=total
    status['visibility_rebuild']=vis;status['final_compaction']=compaction
    out.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(src.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
    for f in src.parent.glob(src.stem+'_*.ent'):shutil.copy2(f,out.parent/f.name)
    print(json.dumps(status['surface_alignment_repair'],indent=2))

if __name__=='__main__':build()
