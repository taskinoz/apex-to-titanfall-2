"""Generate exhaustive release inventories, actual binary layouts and measured capacities."""
import collections,csv,hashlib,json,re,struct,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'));sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import bsp_tool
from bsp_tool.branches import shared
from bsp_tool.branches.respawn import titanfall2
from audit_compatibility import schema
from repair_preview_index_padding import read_lumps
from audit_world_draw_budget import audit
from build_center_detail import active
from finalize_lighting_release import digest

DOC=ROOT/'docs/conversion'
PACKAGE=ROOT/'northstar/PhaseRunner'

def save(name,obj):
    p=DOC/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def entities(data):
    if b'{' not in data:return []
    return [dict(e) for e in shared.Entities.from_bytes(data[data.index(b'{'):])]

def inventory():
    old=json.loads((ROOT/'logs/fir-remaining-objects.json').read_text())
    props=json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
    missing={p['index'] for p in old['remaining_placements']}
    availability={m['model']:m for m in json.loads((ROOT/'logs/remaining-source-model-availability.json').read_text())}
    rows=[];models=[]
    for model,count in collections.Counter(p['model'] for p in old['remaining_placements']).most_common():
        folder=ROOT/'tools/legion/exported_files/models'/Path(model).stem
        a=availability.get(model,{})
        models.append(dict(model=model,placements=count,compiled_available=(folder/(folder.name+'.rmdl')).is_file() and (folder/(folder.name+'.vg')).is_file(),
                           exported_qc_available=a.get('source_qc_exists',False),physics_file_available=(folder/(folder.name+'.phy')).is_file(),
                           omission_reason='Not selected for the bounded world-baked release; availability does not establish compatible skins, shaders or collision.'))
    bymodel={m['model']:m for m in models}
    for p in props:
        status='outside_arena_not_imported' if not p['in_arena'] else 'omitted' if p['index'] in missing else 'rendered'
        rows.append(dict(source_index=p['index'],model=p['model'],category=p['model'].split('/')[1],status=status,source_position=[v+d for v,d in zip(p['origin'],(26000,19000,0))],source_position_translated=p['origin'],angles=p['angles'],scale=p['scale'],skin=p['skin'],solid_mode=p['solid_mode'],flags=p['flags']))
    assert len(rows)==16862 and sum(r['status']=='rendered' for r in rows)==5425
    assert sum(r['status']=='omitted' for r in rows)==10951
    save('static-placement-inventory.json',dict(version='1.0.0',source_placements=len(rows),rendered=5425,omitted_in_arena=10951,outside_arena=486,placements=rows))
    with (DOC/'missing-static-placements.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['source_index','model','category','status','source_x','source_y','source_z','target_x','target_y','target_z','pitch','yaw','roll','scale','skin','solid_mode','flags'])
        for r in rows:
            if r['status']!='rendered':w.writerow([r['source_index'],r['model'],r['category'],r['status'],*r['source_position'],*r['source_position_translated'],*r['angles'],r['scale'],r['skin'],r['solid_mode'],r['flags']])
    save('missing-model-types.json',models)
    source=ROOT/'inputs/extracted-client/maps';parts=[source/'mp_rr_arena_phase_runner.bsp.0000.bsp_lump',*sorted(source.glob('mp_rr_arena_phase_runner_*.ent'))]
    target=entities(read_lumps(PACKAGE/'mod/maps/mp_phase_runner.bsp',(0,))[0])
    for p in (PACKAGE/'mod/maps').glob('mp_phase_runner_*.ent'):target.extend(entities(p.read_bytes()))
    erows=[];counts={}
    def translated(e):
        try:return [float(v)-d for v,d in zip(e['origin'].split(),(26000,19000,0))]
        except (KeyError,ValueError):return None
    for part in parts:
        values=entities(part.read_bytes());counts[part.name]=len(values)
        for i,e in enumerate(values):
            origin=translated(e);matches=[]
            for j,t in enumerate(target):
                if t.get('classname')!=e.get('classname'):continue
                if e.get('targetname') and t.get('targetname')!=e['targetname']:continue
                if origin is not None:
                    try:q=[float(v) for v in t['origin'].split()]
                    except (ValueError,KeyError):continue
                    if len(q)!=3 or max(abs(a-b) for a,b in zip(origin,q))>.1:continue
                matches.append(j)
            model=e.get('model','')
            status='matching_target_identity_semantics_unverified' if matches else 'world_settings_rebuilt' if e.get('classname')=='worldspawn' else 'brush_model_geometry_exported_behavior_unverified' if model.startswith('*') else 'no_matching_target_entity'
            erows.append(dict(source=part.name,index=i,classname=e.get('classname',''),model=model,translated_origin=origin,status=status,target_identity_candidates=matches,source_entity=e))
    save('entity-inventory.json',dict(source_partition_counts=counts,source_entities=len(erows),target_entities=len(target),source=erows,target=target,
                                    limitation='Identity matching is an audit aid, not proof of converted behavior. Brush geometry may be baked while trigger/mover behavior remains unsupported.'))
    dynamic=json.loads((ROOT/'output/phase-runner/entity-prop-inventory.json').read_text());save('missing-dynamic-props.json',dynamic)
    summary=dict(version='1.0.0',source_static_placements=16862,arena_static_placements=16376,rendered_arena_static_placements=5425,missing_arena_static_placements=10951,
                 missing_model_types=len(models),missing_categories=old['remaining_arena_categories'],outside_arena_placements=486,
                 omitted_model_types_with_compiled_files=sum(m['compiled_available'] for m in models),omitted_placements_with_compiled_files=sum(m['placements'] for m in models if m['compiled_available']),
                 source_entities=len(erows),entity_status_counts=dict(collections.Counter(r['status'] for r in erows)),dynamic_render_prop_placements=27,dynamic_render_props_converted=0)
    save('missing-summary.json',summary)
    lines=['# Missing and adapted content — Phase Runner 1.0.0','',f"The release renders **5,425 of 16,376** static placements inside the imported arena. **10,951** placements across **{len(models)} model types** remain omitted. Another **486** placements are outside the arena filter. These are counts of source placements, not triangles or target entities.",'','[Every static placement](static-placement-inventory.json) · [Every omitted static placement, CSV](missing-static-placements.csv) · [Model availability](missing-model-types.json) · [Every source and target entity](entity-inventory.json) · [Dynamic model props](missing-dynamic-props.json)','','## Omitted static categories','','| Source category | Placements |','|---|---:|']
    lines += [f'| {k} | {v:,} |' for k,v in sorted(old['remaining_arena_categories'].items(),key=lambda r:-r[1])]
    lines+=['','## Every omitted arena model type','','Compiled availability means both exported RMDL and VG files exist. It does not certify target format support. Omission reasons need a per-model staging test before recovery.','','| Model | Placements | RMDL + VG available | PHY available |','|---|---:|---|---|']
    lines += [f"| `{m['model']}` | {m['placements']} | {'yes' if m['compiled_available'] else 'no'} | {'yes' if m['physics_file_available'] else 'no'} |" for m in models]
    lines += ['','## Dynamic and behavioral omissions','','The source entity partitions contain 24 animated large IMC fans and 3 holospray model props; none has been converted into a working animated target prop. The entity ledger retains all source key/value data for future adapters. No matching target entity is a precise identity result, not an assertion that related brush geometry is absent.','','Apex phase travel, animated/interactable doors, original game-mode rules, loot/interaction logic, original scripted movers, source sound/FX behavior and AI/navigation have not been faithfully reproduced. Door blockers were adapted/opened where needed for traversal; the tunnel catwalks and rails are target-authored additions. The technical guide describes lighting, material, sky, collision and visibility approximations.','','Historical export audits reporting 54 missing QC/SMD meshes predate direct compiled VG recovery. They must not be quoted as the current release omission count. The static ledger is reconciled against the latest fir recovery inventory; dynamic, outside-arena and behavioral omissions are counted separately.']
    (DOC/'MISSING_CONTENT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary

def layouts():
    src=bsp_tool.load_bsp(str(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp'))
    target=PACKAGE/'mod/maps/mp_phase_runner.bsp';header=target.read_bytes()[:2064]
    rows=[]
    for index in range(128):
        se=src.branch.LUMP(index);te=titanfall2.LUMP(index);sh=src.headers[se.name]
        off,size,version,fourcc=struct.unpack_from('<4I',header,16+index*16)
        ss=schema(src.branch,se.name,sh.version);ts=schema(titanfall2,te.name,version)
        rows.append(dict(index=index,hex_index=f'0x{index:02x}',source_name=se.name,target_name=te.name,source_bytes=sh.length,source_lump_version=sh.version,target_bytes=size,target_lump_version=version,source_parser_schema=ss,target_parser_schema=ts,
                         classification='repurposed_slot' if se.name!=te.name else 'record_format_match_requires_semantic_checks' if ss['format'] and ss['format']==ts['format'] else 'rebuild_or_validate'))
    observed=[('BspHeaderPrefix','<4s3I',None,['magic','version','revision','last_lump_index']),('LumpHeader','<4I',None,['offset','length','version','fourcc']),
              ('LitBumpVertex','<2I2f4B4f2I',0x49,['position_index','normal_index','albedo_u','albedo_v','rgba[4]','lightmap_uv_and_reserved[4]','tangent_index_with_mirror_bit','extra']),
              ('Mesh','<I3H6b2h2BHI',0x50,['first_index','triangles','first_vertex','vertex_span','vertex_type','cubemap','styles[4]','luxel_origin[2]','luxel_max[2]','material_sort','flags']),
              ('MeshBounds','<8f',0x51,['center[3]','radius','half_extent[3]','unused']),('MaterialSort','<3hHI',0x52,['texture_data','lightmap','cubemap','last_local_vertex','vertex_base']),
              ('LightmapHeader','<I2H',0x53,['count','width','height']),('CMBrush','<3f2BH3fI',0x5c,['center[3]','cut_plane_count','cut_plus_bevel_count','brush_index','half_extent[3]','plane_offset_index']),
              ('CMGeoSet','<HHI',0x57,['group','primitive_count','packed_primitive_or_range']),('CMGridCell','<2H',0x56,['first_geoset','geosets']),('PackedCollisionBounds','<3hH3hH',0x58,['center[3]','flags','half_extent[3]','unused']),
              ('TriCollHeader','<6h4i4f',0x45,['flags','texture_flags','texture','vertices','triangles','bevels','first_vertex','first_triangle','first_node','first_bevel','origin[3]','scale']),
              ('CellAABBNode','<3f2BH3f2H',0x77,['mins[3]','children','direct_references','subtree_references','maxs[3]','first_child','first_reference']),
              ('ObjectReferenceBounds','<3fI3fI',0x79,['mins[3]','reserved0','maxs[3]','reserved1']),('ShadowMesh','<2I2h',0x7f,['vertex_base','triangles','opaque','material_sort']),
              ('LightProbe','<16h4B4hI',0x65,['ambient_coefficients[16]','visibility[4]','local_light_indices[4]','reserved']),('LightProbeRef','<3fIi',0x68,['origin[3]','probe_index','reserved']),
              ('LightProbeParent','<i6I',4,['index','first_probe','probes','first_reference','references','first_tree','tree_nodes']),('StaticPropV13','<7fH2B2H4f4b4B2H',None,['origin[3]','angles_yzx[3]','scale','model_index','solid','flags','skin','cubemap','fade','lighting_origin[3]','cpu_gpu_levels[4]','diffuse_modulation[4]','collision_flags[2]']),
              ('StbspMaterialInfo','<2IQ2I',None,['string_offset','unknown','guid','unknown2','unknown3']),('StbspColumn','<QIf4h',None,['payload_offset','payload_length','coverage_scale','bounds_xy[4]'])]
    save('binary-layouts.json',dict(endianness='little',bsp_magic='rBSP',bsp_header_bytes=2064,source_bsp_version=src.version,target_bsp_version=37,lump_slots=rows,
                                  observed_writer_layouts=[dict(name=n,format=f,bytes=struct.calcsize(f),lump=i,fields=k) for n,f,i,k in observed],
                                  limitations='Parser labels and unknown fields are not guaranteed engine semantics; writer-observed records take precedence. All offsets must be bounds-checked, and formats are version-specific.'))
    return rows

def capacities():
    path=PACKAGE/'mod/maps/mp_phase_runner.bsp';b=audit(path)
    l=read_lumps(path,(0x52,0x45,0x42,0x57,0x59,0x5c,0x65,0x68,0x53,0x6c,0x7b))
    live=active(l)
    measurements=dict(**b,material_sorts=len(l[0x52])//12,stored_brushes=len(l[0x5c])//32,active_brushes=sum(k==0 for k,i in live),stored_triangle_headers=len(l[0x45])//44,
                      active_triangle_headers=sum(k==0x40 for k,i in live),stored_collision_triangles=len(l[0x42])//4,collision_geosets=len(l[0x57])//8,lightprobes=len(l[0x65])//48,
                      lightprobe_references=len(l[0x68])//20,lightmap_pages=len(l[0x53])//8,portals_bytes=len(l[0x6c]),raw_index_headroom=3145728-b['native_padded_indices'],policy_95_percent_index_headroom=int(3145728*.95)-b['native_padded_indices'])
    engine=Path('D:/Games/Titanfall2/bin/x64_retail/engine.dll');client=Path('D:/Games/Titanfall2/bin/x64_retail/client.dll')
    bins={str(p):digest(p) for p in (engine,client) if p.is_file()}
    limits=[dict(name='all_visible_world_indices',value=3145728,kind='native_submission_capacity',evidence='audit_world_draw_budget.py; engine.dll RVA 0xb72af; logs/native-reader-engine-0x7cb410.txt'),
            dict(name='world_draw_batches',value=2048,kind='native_submission_capacity',evidence='engine.dll RVA 0xb7304; static keys can be split by dynamic light masks'),
            dict(name='material_sorts',value=8192,kind='native_loader_capacity',evidence='1024-byte loader bitset; 0.1.20 minidump; guard_native_sort_capacity.py; package_northstar.py'),
            dict(name='world_mesh_reference_index',value=65535,kind='serialized_unsigned16_max',evidence='OBJ_REFERENCES uint16; references index meshes, not source prop placements'),
            dict(name='local_vertex_index',value=65535,kind='serialized_unsigned16_max',evidence='MESH_INDICES uint16; global vertex base lives in MATERIAL_SORTS'),
            dict(name='collision_primitive_index',value=65535,kind='serialized_unsigned16_max',evidence='CM_PRIMITIVES bits 8..23; target brush or triangle header; conservative writers use fewer than 65536'),
            dict(name='geoset_start_and_count',value=65535,kind='serialized_unsigned16_max',evidence='CM_GRID_CELLS uint16 fields; range first+count checked conservatively <=65535'),
            dict(name='brush_cut_and_bevel_counts',value=255,kind='serialized_unsigned8_max',evidence='CM_BRUSHES bytes at offsets 12 and 13'),
            dict(name='packed_collision_center_and_extent',value=32767,kind='serialized_signed16_max',evidence='CM_GEO_SET_BOUNDS / CM_PRIMITIVE_BOUNDS / TRICOLL_NODES; require center and extent to fit, not just coordinates'),
            dict(name='flat_cell_child_and_leaf_counts',value=255,kind='serialized_unsigned8_max',evidence='CELL_AABB_NODES; build_camera_visibility also restricts root child count <=255'),
            dict(name='project_world_index_policy',value=.95,kind='project_safety_policy',evidence='build_phase_runner_firs.py; margin, not an engine hard limit'),
            dict(name='project_static_batch_policy',value=512,kind='project_safety_policy_exclusive',evidence='Firs release requires static_batch_runs <512; dynamic lights can multiply batch count'),
            dict(name='project_local_vertices_policy',value=60000,kind='project_safety_policy',evidence='optimize_portalfree_render.py; preserves short local clipping spans'),
            dict(name='project_tricoll_group_triangles',value=96,kind='project_encoding_choice',evidence='native_triangle_collision.py supports 1..300; 96 chosen to keep compact local bounds'),
            dict(name='project_coordinate_clip',value=32760,kind='project_safety_policy',evidence='rebuild_complete_collision.py; remote polygons clipped; shape bounds must still be representable')]
    save('engine-limits.json',dict(scope='Tested installed Titanfall 2 build; RVAs are not portable across updates.',binary_sha256=bins,limits=limits,current_release=measurements,
                                 unknown=['Universal playable map dimensions','Safe static-prop/entity total for native model path','Universal texture residency budget','Fully selective portal graph generation','Complete Apex collision contents equivalence','Apex versions other than the source v47'],
                                 limitation='No universal map-size or total-object limit is inferred from the world-baked renderer budget. Other rendering paths have separate capacities.'))
    return measurements

def provenance():
    paths=[ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp',*sorted((ROOT/'inputs/extracted-client/maps').glob('mp_rr_arena_phase_runner.bsp.*.bsp_lump')),
           *sorted((ROOT/'inputs/extracted-client/maps').glob('mp_rr_arena_phase_runner_*.ent')),
           ROOT/'tools/repak/RePak.exe',ROOT/'tools/mrvn-radiant/install/Release/remap.exe',ROOT/'tools/bake_phase_environment.exe',ROOT/'tools/bake_interior_lighting.exe',ROOT/'tools/bake_character_probes.exe']
    save('source-and-tool-checksums.json',[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in paths if p.is_file()])
    shutil.copy2(ROOT/'inputs/phase-runner-manifest.json',DOC/'source-archive-manifest.json')
    shutil.copy2(ROOT/'output/phase-runner/preview-full-collision/collision-ownership.json',DOC/'collision-ownership-baseline.json')
    for name in ('tunnel-collision-repair.json','catwalks.json','center-detail.json','art-supports.json','trees.json','character-lighting.json','interior-lights.json','loading-repair.json'):
        p=PACKAGE/name
        if p.is_file():shutil.copy2(p,DOC/name)
    patch=ROOT/'output/phase-runner/mrvn-compiler.patch'
    if patch.is_file():shutil.copy2(patch,DOC/'mrvn-compiler.patch')

if __name__=='__main__':
    DOC.mkdir(parents=True,exist_ok=True)
    s=inventory();layouts();b=capacities();provenance()
    print(json.dumps(dict(inventory=s,draw_budget={k:b[k] for k in ('real_triangles','native_padded_indices','static_batch_runs','material_sorts','active_brushes','active_triangle_headers','stored_collision_triangles','lightprobes','lightmap_pages')}),indent=2))
