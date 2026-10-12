"""Repair native pairwise triangle reads and withdraw the 0.1.21 cell experiment.

The client dump at engine+0xae8d3 reads the next mesh's first triangle when
313 source triangles become 314 in the runtime descriptor. Native Homestead
and Colony store three repeated indices after EVERY odd-sized mesh. Source
triangle count excludes that padding. No new rendered triangle is introduced.
"""
import json,shutil,struct
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import validate_visibility

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'output/phase-runner'

def read_lumps(path,ids):
    with Path(path).open('rb') as f:
        h=f.read(2064);result={}
        for i in ids:
            o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);result[i]=f.read(n)
        return result

def validate_index_padding(meshes,indices,sorts):
    covered=[];odd=0;triangles=0
    for mi in range(len(meshes)//28):
        first,count,minimum,span=struct.unpack_from('<I3H',meshes,mi*28)
        si=struct.unpack_from('<H',meshes,mi*28+22)[0]
        if not count or si*12+12>len(sorts):raise ValueError('Invalid mesh/material sort range')
        maximum=minimum+span
        padded=count+(count&1);end=first+padded*3
        if first%6 or end*2>len(indices):raise ValueError(f'Mesh {mi} lacks native triangle-pair padding')
        ids=struct.unpack_from('<'+'H'*(padded*3),indices,first*2)
        if any(v<minimum or v>maximum for v in ids):raise ValueError(f'Mesh {mi} pair read exceeds its vertex span')
        if count&1:
            odd+=1
            if len(set(ids[-3:]))!=1:raise ValueError(f'Mesh {mi} padding is not degenerate')
        covered.append((first,end));triangles+=count
    cursor=0
    for a,b in sorted(covered):
        if a!=cursor:raise ValueError('Index ranges overlap or leave gaps')
        cursor=b
    if cursor*2!=len(indices):raise ValueError('Unreferenced mesh indices')
    return dict(meshes=len(meshes)//28,render_triangles=triangles,odd_meshes_padded=odd,
        pair_reads_within_declared_vertex_ranges=True,padding_triangles_degenerate=True,
        six_index_alignment_verified=True)

def add_index_padding(meshes,indices):
    output=bytearray();newmesh=bytearray(meshes);odd=0
    for at in range(0,len(meshes),28):
        first,count=struct.unpack_from('<IH',meshes,at)
        payload=indices[first*2:(first+count*3)*2]
        if len(payload)!=count*6 or not count:raise ValueError('Truncated mesh indices')
        struct.pack_into('<I',newmesh,at,len(output)//2);output.extend(payload)
        if count&1:
            odd+=1;last=struct.unpack_from('<H',payload,len(payload)-2)[0]
            output.extend(struct.pack('<3H',last,last,last))
    return newmesh,output,odd

def audit_native(path):
    l=read_lumps(path,(0x50,0x4f,0x52))
    return dict(path=str(path),**validate_index_padding(l[0x50],l[0x4f],l[0x52]))

def build():
    # This intermediate already contains the additional 0.1.21 collision, but
    # every render/visibility lump remains byte-identical to the 0.1.20 source.
    source=PROJECT/'preview-structure-physics/mp_phase_runner_preview.bsp'
    prior=PROJECT/'preview-prop-physics/mp_phase_runner_preview.bsp'
    out=PROJECT/'preview-index-repaired/mp_phase_runner_preview.bsp'
    ids=(2,3,0x0e,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x69,*range(0x6a,0x7a),0x7b)
    old=read_lumps(prior,ids);current=read_lumps(source,ids)
    if old!=current:raise ValueError('Pre-repair drawing/visibility differs from 0.1.20')
    meshes,indices,odd=add_index_padding(current[0x50],current[0x4f])
    checks=validate_index_padding(meshes,indices,current[0x52])
    native={name:audit_native(ROOT/relative) for name,relative in (
        ('homestead','inputs/titanfall2-homestead/maps/mp_homestead.bsp'),
        ('colony','inputs/titanfall2-colony/maps/mp_colony02.bsp'))}
    visibility=validate_visibility(current[0x77],current[0x78],current[0x79],current[0x51])
    report=compact(source,out,{0x50:meshes,0x4f:indices})
    status=json.loads(source.with_name('source-build.json').read_text())
    status['index_padding_repair']=dict(checks,native_references=native,
        regression_version='0.1.21',crash_offset='engine.dll+0xae8d3',
        restored_visibility_version='0.1.20',experimental_cells_removed=True,
        previous_vertex_range_metadata_restored=True,real_triangles_attributes_and_materials_preserved=True,
        additional_structure_collision_retained=True,client_grapple_and_rendering_verified=False,
        crash_evidence=dict(mesh=18176,source_triangles=313,runtime_triangles=314,
            mesh_first_vertex=2028,next_mesh_first_indices=[926,919,932],first_invalid_relative_index=-1102,
            dump='logs/client-0.1.21-crash.dmp',analysis='logs/client-0.1.21-crash-analysis.txt'),
        limitation='The invalid pair read is removed by native padding. Dedicated traces do not verify GPU rendering or a player grapple.')
    status['visibility_rebuild']=visibility;status['final_compaction']=report
    out.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,out.parent/p.name)
    shutil.copy2(source.with_suffix('.stbsp'),out.with_suffix('.stbsp'))
    (PROJECT/'client-feedback-0.1.21.json').write_text(json.dumps(dict(version='0.1.21',
        user_feedback='Hall of mirrors issues, then crashed when grappling.',client_crashed=True,
        dump='logs/client-0.1.21-crash.dmp',released_rendering_failed=True),indent=2))
    print(json.dumps(status['index_padding_repair'],indent=2))

if __name__=='__main__':build()
