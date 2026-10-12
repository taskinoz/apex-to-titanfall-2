"""Group exact world draw records below native submission's 2,048-batch limit."""
import json,os,shutil,struct
from pathlib import Path
from audit_world_draw_budget import audit,batch_audit,static_draw_key,enforce_camera_bypass_budget
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from preview_visibility import validate_visibility
from finalize_lighting_release import digest

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'output/phase-runner/playable-visibility/mp_phase_runner.bsp'
OUT=ROOT/'output/phase-runner/batch-ordered'
TARGET=OUT/'mp_phase_runner.bsp'
BASE=ROOT/'northstar/PhaseRunner.Preview'
PACKAGE=ROOT/'northstar/PhaseRunner.BatchOrderedRelease'

def reorder(l):
    meshes=l[0x50];n=len(meshes)//28
    # This map has a single world model and one native partition, all opaque
    # world-shader records. Other maps require sorting within their own ranges.
    if len(l[0xe])!=32 or struct.unpack_from('<2I',l[0xe],24)!=(0,n):
        raise ValueError('Only the full single-world-model layout is supported')
    if struct.unpack_from('<3I',l[0x7b])!=(n,n,n):
        raise ValueError('Sorting would cross a native render partition')
    if l[0x64]:raise ValueError('CSM mesh references require explicit remapping')
    records=[meshes[i*28:i*28+28] for i in range(n)]
    flags={struct.unpack_from('<I',r,24)[0] for r in records}
    if len(flags)!=1 or any(f&0x600!=0x200 or f&0x10 for f in flags):
        raise ValueError('Non-opaque or mixed vertex-channel ordering requires separate handling')
    order=sorted(range(n),key=lambda i:static_draw_key(records[i]))
    inverse=[0]*n
    for new,old in enumerate(order):inverse[old]=new
    refs=[inverse[i] for i, in struct.iter_unpack('<H',l[0x78])]
    changes={0x50:b''.join(records[i] for i in order),
             0x51:b''.join(l[0x51][i*32:i*32+32] for i in order),
             0x78:struct.pack('<'+'H'*len(refs),*refs)}
    validate_visibility(l[0x77],changes[0x78],l[0x79],changes[0x51])
    validate_index_padding(changes[0x50],l[0x4f],l[0x52])
    return changes,order,inverse

def build():
    if json.loads((BASE/'mod.json').read_text())['Version']!='0.1.39':raise ValueError('Unexpected baseline')
    if digest(BASE/'mod/maps/mp_phase_runner.bsp')!=digest(SOURCE):raise ValueError('Canonical baseline differs')
    l=read_lumps(SOURCE,(0xe,0x4f,0x50,0x51,0x52,0x64,0x77,0x78,0x79,0x7b))
    changes,order,inverse=reorder(l)
    compaction=compact(SOURCE,TARGET,changes)
    before=audit(SOURCE);after=enforce_camera_bypass_budget(TARGET)
    cats=json.loads((BASE/'catwalks.json').read_text())
    cat_ids=list(range(cats['first_new_mesh'],cats['first_new_mesh']+cats['new_meshes']))
    report=dict(version='0.1.40',source_version='0.1.39',before=before,after=after,
        new_to_old_mesh=order,old_to_new_mesh=inverse,
        catwalk_meshes_before=cat_ids,catwalk_meshes_after=[inverse[i] for i in cat_ids],
        changed_payloads=['MESHES','MESH_BOUNDS','OBJ_REFERENCES'],
        all_mesh_records_preserved_exactly=True,all_triangles_vertices_uvs_materials_preserved=True,
        each_visibility_reference_still_targets_its_original_physical_geometry=True,
        collision_lighting_character_probes_presentation_portals_preserved=True,
        native_index_and_batch_limits_checked=True,compaction=compaction,
        client_rendering_verified=False,
        limitation='Native limit and exact-data checks establish safe static submission. '
                   'Final GPU appearance and dynamic-light batch splits need a client check.')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'batch-order.json').write_text(json.dumps(report,indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    for source in BASE.rglob('*'):
        if not source.is_file():continue
        rel=source.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else source
        if dest.exists():
            if os.path.samefile(actual,dest):continue
            dest.unlink()
        if actual.stat().st_size>10*1024*1024:os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    mod=json.loads((PACKAGE/'mod.json').read_text());mod['Version']='0.1.40'
    mod['Description']='Phase Runner with native draw-batch ordering for complete tunnel and prop visuals.'
    (PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2))
    status=json.loads((PACKAGE/'build-status.json').read_text());status['world_batch_order_repair']=report
    status['world_draw_budget_repair']['after']=after
    (PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    shutil.copy2(OUT/'batch-order.json',PACKAGE/'batch-order.json')
    print(json.dumps({k:v for k,v in report.items() if k not in ('new_to_old_mesh','old_to_new_mesh','compaction')},indent=2),flush=True)

if __name__=='__main__':build()
