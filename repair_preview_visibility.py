"""Correct visibility subtree starts without changing geometry, assets or physics."""
import json
import shutil
import struct
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT/'output/phase-runner'


def audit_native(path):
    with Path(path).open('rb') as stream:
        header=stream.read(2064)
        def lump(i):
            o,n,_,_=struct.unpack_from('<4I',header,16+i*16);stream.seek(o);return stream.read(n)
        nodes=list(struct.iter_unpack('<3f2BH3f2H',lump(0x77)))
        refs=lump(0x78)
        roots=len(lump(0x6b))//8
        bounds=lump(0x51)
    seen=set();internal=0
    def walk(i):
        nonlocal internal
        if i in seen or not 0<=i<len(nodes):raise ValueError('Native visibility graph is invalid')
        seen.add(i);n=nodes[i];children,own,total,first,ref=n[3],n[4],n[5],n[9],n[10]
        if ref+total>len(refs)//2:raise ValueError('Native subtree range is invalid')
        cursor=ref+own
        if children:internal+=1
        for child in range(first,first+children):
            if nodes[child][10]!=cursor:raise ValueError('Native subtree ranges are not contiguous')
            cursor+=walk(child)
        if cursor!=ref+total:raise ValueError('Native subtree count disagrees')
        return total
    root_ranges=[(nodes[i][10],walk(i)) for i in range(roots)]
    if len(seen)!=len(nodes):raise ValueError('Unreachable native visibility nodes')
    cursor=0
    for start,count in root_ranges:
        if not count:continue  # Native empty cells use a zero start sentinel.
        if start!=cursor:raise ValueError('Native cell reference ranges overlap or leave gaps')
        cursor+=count
    if cursor!=len(refs)//2:raise ValueError('Unreferenced native objects')
    return dict(path=str(Path(path)),world_meshes=len(bounds)//32,cells=roots,
        empty_cells=sum(not count for _,count in root_ranges),
        nodes=len(nodes),internal_nodes=internal,object_references=cursor,
        contiguous_subtree_ranges_verified=True,all_nodes_reachable=True)


def build():
    references={name:audit_native(ROOT/path) for name,path in [
        ('homestead','inputs/titanfall2-homestead/maps/mp_homestead.bsp'),
        ('colony','inputs/titanfall2-colony/maps/mp_colony02.bsp')]}
    source=PROJECT/'preview-portal-complete/mp_phase_runner_preview.bsp'
    output=PROJECT/'preview-visibility-fixed/mp_phase_runner_preview.bsp'
    with source.open('rb') as stream:
        header=stream.read(2064)
        def lump(i):
            o,n,_,_=struct.unpack_from('<4I',header,16+i*16);stream.seek(o);return stream.read(n)
        old_nodes,old_refs,old_objects,bounds=(lump(i) for i in (0x77,0x78,0x79,0x51))
    nodes,refs,objects=build_visibility(bounds)
    if old_refs!=refs or old_objects!=objects or len(old_nodes)!=len(nodes):
        raise ValueError('Unexpected visibility layout change')
    changed=[]
    for i in range(len(nodes)//32):
        at=i*32
        if old_nodes[at:at+30]!=nodes[at:at+30]:
            raise ValueError('Unexpected bounds, children or count change')
        if old_nodes[at+30:at+32]!=nodes[at+30:at+32]:changed.append(i)
    if not changed:raise ValueError('No incorrect subtree starts were found')
    before=[]
    for i in changed:
        before.append(dict(node=i,old_start=struct.unpack_from('<H',old_nodes,i*32+30)[0],
            corrected_start=struct.unpack_from('<H',nodes,i*32+30)[0],
            subtree_references=struct.unpack_from('<H',nodes,i*32+14)[0]))
    validation=validate_visibility(nodes,refs,objects,bounds)
    report=compact(source,output,{0x77:nodes})
    status=json.loads(source.with_name('source-build.json').read_text())
    status['visibility_range_repair']=dict(corrected_internal_nodes=len(changed),
        changes=before,native_references=references,validation=validation,
        geometry_material_lighting_physics_unchanged=True,
        changed_lumps=[0x77],visual_verified=False,
        explanation='Internal first_obj_ref must start the entire contiguous subtree; zero is not a sentinel for branches with no own references.')
    status['visibility_rebuild']=validation;status['final_compaction']=report
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    (PROJECT/'native-visibility-range-audit.json').write_text(json.dumps(references,indent=2))
    for ent in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(ent,output.parent/ent.name)
    shutil.copy2(source.with_suffix('.stbsp'),output.with_suffix('.stbsp'))
    print(json.dumps(dict(corrected_nodes=len(changed),validation=validation,native_references=references,compaction=report),indent=2))


if __name__=='__main__':build()
