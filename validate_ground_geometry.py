"""Check the repaired mesh references and preservation of the source physics."""
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate():
    source = (ROOT/'output/phase-runner/preview-props/mp_phase_runner_preview.bsp').read_bytes()
    target = (ROOT/'output/phase-runner/preview-ground/mp_phase_runner_preview.bsp').read_bytes()
    def lump(data,i):
        o,n,_,_ = struct.unpack_from('<4I',data,16+i*16)
        return data[o:o+n]
    for i in (1,3,0x1e,0x49,0x52,0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f):
        if lump(source,i) != lump(target,i): raise ValueError(f'Unexpected change in {i:#x}')
    meshes,indices,sorts,lit,positions,bounds = (lump(target,i) for i in (0x50,0x4f,0x52,0x49,3,0x51))
    total = len(meshes)//28
    if len(bounds) != total*32: raise ValueError('Mesh bounds count mismatch')
    if list(struct.unpack('<'+'H'*total,lump(target,0x78))) != list(range(total)):
        raise ValueError('Visibility references do not cover every mesh')
    if struct.unpack_from('<I',lump(target,0x0e),28)[0] != total:
        raise ValueError('World mesh count mismatch')
    triangles = 0
    for mi in range(total):
        start,count,first,last = struct.unpack_from('<I3H',meshes,mi*28)
        sort = struct.unpack_from('<H',meshes,mi*28+22)[0]
        base = struct.unpack_from('<i',sorts,sort*12+8)[0]
        b = struct.unpack_from('<8f',bounds,mi*32)
        if start != triangles*3: raise ValueError('Noncontiguous mesh index range')
        for off in range(start,start+count*3):
            local = struct.unpack_from('<H',indices,off*2)[0]
            if not first <= local <= last: raise ValueError('Local index out of mesh range')
            v = (base+local)*44
            if v+44 > len(lit): raise ValueError('Vertex reference out of bounds')
            p = struct.unpack_from('<I',lit,v)[0]*12
            point = struct.unpack_from('<3f',positions,p)
            if any(abs(point[k]-b[k]) > b[k+4]+.02 for k in range(3)):
                raise ValueError('Triangle outside its visibility bounds')
        triangles += count
    status = json.loads((ROOT/'output/phase-runner/preview-ground/source-build.json').read_text())
    old_count = sum(struct.unpack_from('<H',lump(source,0x50),i+4)[0]
                    for i in range(0,len(lump(source,0x50)),28))
    repair = status['ground_surface_repair']
    expected = old_count-repair['unsupported_overlay_triangles']-repair['identical_triangles_removed']
    if triangles != expected or len(indices) != triangles*6:
        raise ValueError('Removed triangle accounting mismatch')
    result = dict(meshes=total,triangles=triangles,mesh_references_valid=True,
                  physics_unchanged=True,vertex_buffers_unchanged=True)
    (ROOT/'output/phase-runner/preview-ground/validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__ == '__main__': validate()
