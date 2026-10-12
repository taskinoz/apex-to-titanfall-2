"""Bake recovered Apex terrain UV transforms into the native preview vertices.

OBJ import flips V. Apply the source transform in source UV space and then
restore the importer's convention. Geometry, materials and physics stay intact.
"""
import json
import math
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TERRAIN = {
    'icelandic_moss_01_wld_desertlands_snow_04_wld_bm',
    'icelandic_moss_01_wld_moss_01_lavender_wld_bm',
    'icelandic_moss_01_wld_icelandic_dirt_01_wld_bm',
    'icelandic_dirt_02_wld_icelandic_dirt_01_wld_bm',
    'metal_plate_trim_slums_01_to_dirt_wld_bm',
}


def transformed_uv(u,v,m):
    a,b,c,d,x,y = m
    source_v = 1-v
    return a*u+b*source_v+x, 1-(c*u+d*source_v+y)


def build():
    source = ROOT/'output/phase-runner/preview-ground/mp_phase_runner_preview.bsp'
    output = ROOT/'output/phase-runner/preview-terrain/mp_phase_runner_preview.bsp'
    original = source.read_bytes()
    def lump(i):
        o,n,_,_ = struct.unpack_from('<4I',original,16+i*16)
        return original[o:o+n]
    lit = bytearray(lump(0x49))
    meshes,sorts,textures,table,names,indices = (lump(i) for i in (0x50,0x52,2,0x2c,0x2b,0x4f))
    changed = set()
    report = {}
    for off in range(0,len(meshes),28):
        start,count = struct.unpack_from('<IH',meshes,off)
        sort = struct.unpack_from('<H',meshes,off+22)[0]
        texture,_,_,_,base = struct.unpack_from('<3hHi',sorts,sort*12)
        ni = struct.unpack_from('<I',textures,texture*36+12)[0]
        no = struct.unpack_from('<I',table,ni*4)[0]
        name = names[no:names.index(0,no)].decode().replace('\\','/').rsplit('/',1)[-1]
        if name not in TERRAIN: continue
        cpu = ROOT/'tools/legion/exported_files/materials'/name/(name+'.cpu')
        raw = cpu.read_bytes()
        if len(raw) != 592: raise ValueError(f'Unsupported material buffer for {name}')
        matrix = struct.unpack_from('<6f',raw)
        if not all(math.isfinite(v) and abs(v)<=10 for v in matrix):
            raise ValueError('Invalid source UV transform')
        item = report.setdefault(name,dict(matrix=list(matrix),triangles=0,vertices=0))
        item['triangles'] += count
        for index in struct.unpack_from('<'+'H'*(count*3),indices,start*2):
            vertex = base+index
            if vertex in changed: continue
            offset = vertex*44+8
            u,v = struct.unpack_from('<2f',lit,offset)
            struct.pack_into('<2f',lit,offset,*transformed_uv(u,v,matrix))
            changed.add(vertex)
            item['vertices'] += 1
    # Check that only the intended UV bytes changed, and each transformed value
    # agrees with the recovered source matrix within float32 rounding.
    old_lit = lump(0x49)
    for vertex in range(len(lit)//44):
        a,b = old_lit[vertex*44:(vertex+1)*44],lit[vertex*44:(vertex+1)*44]
        if vertex in changed:
            if a[:8]!=b[:8] or a[16:]!=b[16:]: raise ValueError('Non-UV vertex data changed')
        elif a!=b: raise ValueError('Untargeted vertex changed')
    data = bytearray(original)
    data.extend(bytes((-len(data))%16))
    offset = len(data);data.extend(lit)
    version = struct.unpack_from('<I',original,16+0x49*16+8)[0]
    struct.pack_into('<4I',data,16+0x49*16,offset,len(lit),version,0)
    for i in range(128):
        if i==0x49: continue
        o,n,_,_ = struct.unpack_from('<4I',data,16+i*16)
        if data[o:o+n]!=lump(i): raise ValueError(f'Unintended lump change in {i:#x}')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'): shutil.copy2(ent,output.parent/ent.name)
    status = json.loads(source.with_name('source-build.json').read_text())
    status['terrain_uv_repair'] = dict(materials=report,vertices=len(changed),
        triangles=sum(r['triangles'] for r in report.values()),
        geometry_and_physics_unchanged=True,visual_verified=False,
        limitation='Restores base texture scaling; original multi-layer terrain blending remains unfinished.')
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status['terrain_uv_repair'],indent=2))


if __name__ == '__main__': build()
