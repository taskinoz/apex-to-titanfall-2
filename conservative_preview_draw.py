"""Use map-wide draw bounds while investigating preview GPU culling."""
import json,math,shutil,struct
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility

def widened_bounds(bounds,padding=2048.):
    records=list(struct.iter_unpack('<8f',bounds))
    lo=[min(r[k]-r[k+4] for r in records)-padding for k in range(3)]
    hi=[max(r[k]+r[k+4] for r in records)+padding for k in range(3)]
    c=[(lo[k]+hi[k])/2 for k in range(3)]
    e=[(hi[k]-lo[k])/2 for k in range(3)]
    radius=math.sqrt(sum(x*x for x in e))+1.
    return struct.pack('<8f',*c,radius,*e,0.)*len(records)

def build(source,output):
    source,output=Path(source),Path(output)
    with source.open('rb') as f:
        h=f.read(2064);o,n,_,_=struct.unpack_from('<4I',h,16+0x51*16);f.seek(o);old=f.read(n)
    bounds=widened_bounds(old);nodes,refs,objects=build_visibility(bounds)
    # Retain the true geometric bounds so spatial culling can be restored later.
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_name('original-mesh-bounds.bin').write_bytes(old)
    report=compact(source,output,{0x51:bounds,0x77:nodes,0x78:refs,0x79:objects})
    status=json.loads(source.with_name('source-build.json').read_text())
    status['conservative_draw_bounds']=dict(meshes=len(bounds)//32,padding=2048,
        validation=validate_visibility(nodes,refs,objects,bounds),
        triangle_vertices_materials_and_physics_unchanged=True,visual_verified=False,
        limitation='Temporary map-wide bounds reduce individual frustum culling and may lower frame rate. Client verification is required; this is not proof of the original pop-in cause.')
    status['final_compaction']=report
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,output.parent/p.name)
    print(json.dumps(status['conservative_draw_bounds'],indent=2))
