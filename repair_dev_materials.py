"""Replace only proven fallback faces; preserve vertices, lightmaps and physics."""
import sys,json,struct,collections,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from prepare_lighting_scene import DT
P=ROOT/'output/phase-runner'
SOURCE=P/'preview-baked/mp_phase_runner_preview.bsp'
TARGET=P/'preview-material-repaired/mp_phase_runner_preview.bsp'

def key(points):return b''.join(sorted(bytes(p) for p in points))

def world_labels():
    # This original compiler buffer was independently checked against OBJ face
    # order by apply_world_materials before any later regrouping or light bake.
    l=read_lumps(P/'preview-collision/mp_phase_runner_preview.bsp',[3,0x49])
    p=np.frombuffer(l[3],dtype='V12');v=np.frombuffer(l[0x49],DT)
    missing=json.loads((P/'world-materials/mapping.json').read_text())['missing']
    out={};face=0;material='';counts=collections.Counter()
    for line in (P/'mp_rr_arena_phase_runner.obj').open():
        if line.startswith('usemtl '):material=line.split()[1]
        elif line.startswith('f ') and not material.startswith('tools/'):
            if len(line.split())!=4:raise ValueError('Non-triangulated source')
            if material in missing:
                k=key(p[v['pi'][face*3:face*3+3]])
                if k in out and out[k]!=material:raise ValueError('Ambiguous coincident source materials')
                out[k]=material;counts[material]+=1
            face+=1
    if face*3!=len(v) or dict(counts)!=missing:raise ValueError('Original OBJ/compiler material order changed')
    return out

def build():
    l=read_lumps(SOURCE,[2,3,0x49,0x4f,0x50,0x51,0x52,0x2b,0x2c,0xe,0x7b])
    p=np.frombuffer(l[3],dtype='V12');xyz=np.frombuffer(l[3],'<f4').reshape(-1,3);v=np.frombuffer(l[0x49],DT)
    ix=np.frombuffer(l[0x4f],'<u2');oldsort=list(struct.iter_unpack('<4hI',l[0x52]));labels=world_labels()
    names=bytearray(l[0x2b]);table=bytearray(l[0x2c]);textures=bytearray(l[2]);byname={}
    for ti,r in enumerate(struct.iter_unpack('<3f6I',textures)):
        no=struct.unpack_from('<I',table,r[3]*4)[0];name=names[no:names.index(0,no)].decode().replace('\\','/')
        byname[name]=ti
    recovered=json.loads((P/'dev-materials/recovered.json').read_text())
    for entry in recovered.values():
        name=entry['name'];ti=len(textures)//36;ni=len(table)//4
        table.extend(struct.pack('<I',len(names)));names.extend(name.replace('/','\\').encode()+b'\0')
        textures.extend(struct.pack('<3f6I',0,0,0,ni,entry['width'],entry['height'],0,0,0xa00));byname[name]=ti
    bindings={
        'world/concrete/dam_concrete_02_gray':'dam_concrete_02_stained_bm',
        'world/s2s/s2s_roof_panel_01_vc':'s2s_roof_panel_01',
        'world/metal/metal_painted_white_01':'pipe_modular_painted_white_vert_color',
        'world/mendoko/white_floor_tile_mendoko':'white_floor_tile_mendoko',
        'world/decal/signage_building_02':'sign_warning_yellow',
        'world/dev/dev_gray_512':'white_floor_tile_mendoko',
        'barrel_latch_blue':'barrel_latch_blue'}
    binding_ids={k:byname['world/phase_runner_preview/'+name] for k,name in bindings.items()}
    placement=json.loads(SOURCE.with_name('render-placement-proof.json').read_text())['placements']
    barrels=[r for r in placement if r['index'] in (11900,11903)]
    if len(barrels)!=2:raise ValueError('Missing barrel placement provenance')
    counts=collections.Counter();meshes=bytearray();sorts=bytearray();indices=bytearray();bounds=bytearray()
    for mi,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
        s=oldsort[r[-2]];tri=ix[r[0]:r[0]+r[1]*3].reshape(-1,3);groups={s[0]:tri}
        if s[0]==0:
            groups=collections.defaultdict(list)
            for local in tri:
                points=p[v['pi'][s[4]+local.astype(np.uint32)]];label=labels.get(key(points))
                if label is None:
                    actual=xyz[v['pi'][s[4]+local.astype(np.uint32)]]
                    if not any(np.all(actual>=np.array(b['bounds'][0])-.1) and np.all(actual<=np.array(b['bounds'][1])+.1) for b in barrels):
                        raise ValueError('Unidentified fallback face '+str(actual.tolist()))
                    label='barrel_latch_blue'
                groups[binding_ids[label]].append(local);counts[label]+=1
        for texture,faces in groups.items():
            faces=np.asarray(faces,dtype='<u2');raw=faces.ravel();count=len(faces);minimum=int(raw.min());span=int(raw.max())-minimum
            record=bytearray(l[0x50][mi*28:mi*28+28]);first=len(indices)//2;si=len(sorts)//12
            struct.pack_into('<I3H',record,0,first,count,minimum,span);struct.pack_into('<H',record,22,si);meshes.extend(record)
            sr=list(s);sr[0]=texture;sr[3]=span;sorts.extend(struct.pack('<3hHI',*sr));indices.extend(raw.tobytes())
            if count&1:indices.extend(struct.pack('<3H',int(raw[-1]),int(raw[-1]),int(raw[-1])))
            if len(groups)==1:bounds.extend(l[0x51][mi*32:mi*32+32])
            else:
                points=xyz[v['pi'][s[4]+raw.astype(np.uint32)]];lo=points.min(0)-.02;hi=points.max(0)+.02;c=(lo+hi)/2;e=(hi-lo)/2
                bounds.extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    if len(sorts)//12>=8192:raise ValueError('Material sort capacity exceeded')
    native=validate_index_padding(meshes,indices,sorts)
    nodes,refs,objects=build_visibility(bounds,leaf_size=128);vis=validate_visibility(nodes,refs,objects,bounds)
    total=len(meshes)//28;models=bytearray(l[0xe]);level=bytearray(l[0x7b]);struct.pack_into('<I',models,28,total);struct.pack_into('<3I',level,0,total,total,total)
    changes={2:textures,0x2b:names,0x2c:table,0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts,0x77:nodes,0x78:refs,0x79:objects,0xe:models,0x7b:level}
    proof=compact(SOURCE,TARGET,changes);budget=audit(TARGET)
    if budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.85:raise ValueError('Insufficient native draw headroom')
    report=dict(version='0.1.32',repaired_triangles=sum(counts.values()),source_face_counts=dict(counts),bindings=bindings,
        exact_recovered_materials=recovered,approximate_variants=['dam_concrete_02_gray','metal_painted_white_01','signage_building_02'],
        authored_placeholder_replaced='White floor tile cladding',fallback_draw_triangles_remaining=0,
        vertex_and_lightmap_lumps_byte_identical=True,collision_lumps_byte_identical=True,walkways_unchanged=True,
        padding=native,visibility=vis,draw_budget=budget,compaction=proof,client_rendering_verified=False)
    status=json.loads(SOURCE.with_name('source-build.json').read_text());status['dev_material_repair']=report
    status['material_project']=str(P/'dev-materials');status['render_repair']['world_meshes']=total;status['world_draw_budget_repair']['after']=budget
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for f in SOURCE.parent.iterdir():
        if f.suffix=='.ent' or f.name in ('render-placement-proof.json','tunnel-walkways.json','collision-ownership.json','tunnel-collision-repair.json'):shutil.copy2(f,TARGET.parent/f.name)
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':build()
