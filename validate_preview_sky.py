"""Verify the dome geometry, inward winding and unchanged collision data."""
import json
import math
import struct
from pathlib import Path
from build_preview_source import cross,subtract

ROOT = Path(__file__).resolve().parent


def validate():
    base = (ROOT/'output/phase-runner/preview-textured/mp_phase_runner_preview.bsp').read_bytes()
    target = (ROOT/'output/phase-runner/preview-sky/mp_phase_runner_preview.bsp').read_bytes()
    def lump(data,index):
        off,size,_,_ = struct.unpack_from('<4I',data,16+index*16)
        return data[off:off+size]
    unchanged = [0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,1]
    for index in unchanged:
        if lump(base,index) != lump(target,index):
            raise ValueError(f'Sky change modified collision lump {index:#x}')
    mesh = lump(target,0x50)[-28:]
    first,triangles = struct.unpack_from('<IH',mesh)
    sort = struct.unpack_from('<H',mesh,22)[0]
    vertex_base = struct.unpack_from('<i',lump(target,0x52),sort*12+8)[0]
    indices = lump(target,0x4f)
    vertices = lump(target,0x49)
    positions,normals = lump(target,3),lump(target,0x1e)
    minimum_area = float('inf')
    for t in range(triangles):
        points = []
        ns = []
        for local in struct.unpack_from('<3H',indices,(first+t*3)*2):
            off = (vertex_base+local)*44
            p,n,u,v = struct.unpack_from('<2I2f',vertices,off)
            if not 0<=u<=1 or not 0<=v<=1:
                raise ValueError('Sky UV exceeds its image bounds')
            points.append(struct.unpack_from('<3f',positions,p*12))
            ns.append(struct.unpack_from('<3f',normals,n*12))
        triangle_normal = cross(subtract(points[1],points[0]),subtract(points[2],points[0]))
        area = math.sqrt(sum(v*v for v in triangle_normal))/2
        minimum_area = min(minimum_area,area)
        if area < 1 or sum(triangle_normal[k]*ns[0][k] for k in range(3)) >= 0:
            raise ValueError(f'Sky triangle {t} is degenerate or faces outward in the native clockwise renderer')
    report = dict(triangles=triangles,inward_native_winding_verified=True,
                  uv_bounds_verified=True,collision_unchanged=True,minimum_triangle_area=minimum_area,
                  visual_verified=False)
    (ROOT/'output/phase-runner/preview-sky/validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    validate()
