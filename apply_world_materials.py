"""Regroup the preview's world triangles by their original Apex OBJ materials."""
import collections
import json
import math
import shutil
import struct
from pathlib import Path
from package_northstar import validate_bsp

ROOT = Path(__file__).resolve().parent


def build():
    source = ROOT/'output/phase-runner/preview-collision/mp_phase_runner_preview.bsp'
    output = ROOT/'output/phase-runner/preview-textured/mp_phase_runner_preview.bsp'
    report = json.loads((ROOT/'output/phase-runner/world-materials/mapping.json').read_text())
    groups = collections.defaultdict(list)
    material = ''
    triangle = 0
    for line in (ROOT/'output/phase-runner/mp_rr_arena_phase_runner.obj').open():
        if line.startswith('usemtl '):
            material = line.split()[1]
        elif line.startswith('f ') and not material.startswith('tools/'):
            for _ in range(len(line.split())-3):
                groups[material].append(triangle)
                triangle += 1
    original = source.read_bytes()
    data = bytearray(original)
    headers = [struct.unpack_from('<4I',original,16+i*16) for i in range(128)]
    def lump(index):
        offset,length,_,_ = headers[index]
        return original[offset:offset+length]
    def put(index,payload):
        data.extend(bytes((-len(data))%16))
        offset = len(data)
        data.extend(payload)
        struct.pack_into('<4I',data,16+index*16,offset,len(payload),headers[index][2],0)
    old_lit = lump(0x49)
    if len(old_lit) != triangle*3*44:
        raise ValueError('OBJ triangle order does not match the diagnostic vertex buffer')
    positions = list(struct.iter_unpack('<3f',lump(3)))
    # Validate the compiler's face order before assigning original materials.
    # A count match alone would allow textures to be assigned to wrong faces.
    obj_positions = []
    skip = False
    checked = 0
    for line in (ROOT/'output/phase-runner/mp_rr_arena_phase_runner.obj').open():
        if line.startswith('v '):
            p = tuple(map(float,line.split()[1:4]))
            obj_positions.append((p[0]-26000.,p[1]-19000.,p[2]))
        elif line.startswith('usemtl '):
            skip = line.split()[1].startswith('tools/')
        elif line.startswith('f ') and not skip:
            face_indices = [int(v.split('/')[0]) for v in line.split()[1:]]
            corners = [obj_positions[i-1 if i>0 else i] for i in face_indices]
            if len(corners) != 3:
                raise ValueError('Expected pre-triangulated OBJ')
            actual = [positions[struct.unpack_from('<I',old_lit,(checked*3+c)*44)[0]] for c in range(3)]
            if any(not any(max(abs(p[k]-q[k]) for k in range(3)) < .05 for q in actual) for p in corners):
                raise ValueError(f'OBJ/compiler face order differs at triangle {checked}')
            checked += 1
    textures = bytearray(lump(2))
    names = bytearray(lump(0x2b))
    table = bytearray(lump(0x2c))
    lit,meshes,indices,sorts,bounds = (bytearray() for _ in range(5))
    old_meshes,old_indices,old_sorts,old_bounds = (lump(i) for i in (0x50,0x4f,0x52,0x51))
    old_world_count = struct.unpack_from('<I',lump(0x7b))[0]
    for material, triangles in groups.items():
        mapping = report['materials'].get(material)
        texture_index = 0
        if mapping:
            texture_index = len(textures)//36
            name_index = len(table)//4
            table.extend(struct.pack('<I',len(names)))
            names.extend(mapping['name'].replace('/','\\').encode()+b'\0')
            textures.extend(struct.pack('<3f6I',0.,0.,0.,name_index,
                mapping['width'],mapping['height'],0,0,0xa00))
        for start in range(0,len(triangles),10000):
            chunk = triangles[start:start+10000]
            base = len(lit)//44
            first = len(indices)//2
            points = []
            for tri in chunk:
                # Every corner was imported separately. Preserve its UV and normal.
                for corner in range(3):
                    record = old_lit[(tri*3+corner)*44:(tri*3+corner+1)*44]
                    lit.extend(record)
                    points.append(positions[struct.unpack_from('<I',record)[0]])
            count = len(chunk)*3
            mesh_index = len(meshes)//28
            record = bytearray(old_meshes[:28])
            struct.pack_into('<I4H',record,0,first,len(chunk),0,count-1,2)
            struct.pack_into('<H',record,22,mesh_index)
            meshes.extend(record)
            sorts.extend(struct.pack('<3hHi',texture_index,0,-1,count-1,base))
            indices.extend(struct.pack('<'+'H'*count,
                *(v for t in range(0,count,3) for v in (t,t+2,t+1))))
            low = [min(p[k] for p in points) for k in range(3)]
            high = [max(p[k] for p in points) for k in range(3)]
            center = [(low[k]+high[k])/2 for k in range(3)]
            extent = [(high[k]-low[k])/2 for k in range(3)]
            bounds.extend(struct.pack('<8f',*center,math.sqrt(sum(v*v for v in extent))+.01,*extent,0.))
    world_count = len(meshes)//28
    sky_sort = len(sorts)//12
    for i in range(old_world_count,len(old_meshes)//28):
        record = bytearray(old_meshes[i*28:(i+1)*28])
        first = struct.unpack_from('<I',record)[0]
        old_sort = struct.unpack_from('<H',record,22)[0]
        struct.pack_into('<I',record,0,len(indices)//2)
        struct.pack_into('<H',record,22,sky_sort)
        indices.extend(old_indices[first*2:(first+6)*2])
        meshes.extend(record)
        bounds.extend(old_bounds[i*32:(i+1)*32])
    sorts.extend(old_sorts[old_sort*12:(old_sort+1)*12])
    total = len(meshes)//28
    if total > 255:
        raise ValueError('Diagnostic visibility leaf exceeds its object count field')
    world = bytearray(lump(0x0e))
    struct.pack_into('<I',world,28,total)
    level = bytearray(lump(0x7b))
    struct.pack_into('<3I',level,0,world_count,world_count,world_count)
    node = bytearray(lump(0x77))
    struct.pack_into('<BBH',node,12,0,total,total)
    object_bounds = bytearray()
    for record in struct.iter_unpack('<8f',bounds):
        center,extent = record[:3],record[4:7]
        object_bounds.extend(struct.pack('<3fI3fI',
            *(center[k]-extent[k] for k in range(3)),0,
            *(center[k]+extent[k] for k in range(3)),0))
    for index,payload in {2:textures,0x2b:names,0x2c:table,0x49:lit,
        0x50:meshes,0x4f:indices,0x52:sorts,0x51:bounds,0x0e:world,
        0x7b:level,0x77:node,0x78:struct.pack('<'+'H'*total,*range(total)),
        0x79:object_bounds}.items():
        put(index,payload)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'):
        shutil.copy2(ent,output.parent/ent.name)
    status = json.loads(source.with_name('source-build.json').read_text())
    status['world_materials'] = {k:v for k,v in report.items() if k not in ('materials','missing')}
    status['world_materials']['visual_verified'] = False
    status['render_repair']['world_meshes'] = world_count
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(dict(world_meshes=world_count,sky_meshes=6,
        recovered_triangles=report['recovered_triangles'],checks=validate_bsp(output)),indent=2))


if __name__ == '__main__':
    build()
