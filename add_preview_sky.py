"""Replace failed sky portals with a diagnostic dome using the recovered sky image.

The original vista model is not converted yet. A sphere-map projection is an
explicit approximation; the client must verify its orientation and seam.
"""
import json
import math
import shutil
import struct
from pathlib import Path
from package_northstar import validate_bsp

ROOT = Path(__file__).resolve().parent


def add():
    source = ROOT/'output/phase-runner/preview-textured/mp_phase_runner_preview.bsp'
    output = ROOT/'output/phase-runner/preview-sky/mp_phase_runner_preview.bsp'
    original = source.read_bytes()
    data = bytearray(original)
    headers = [struct.unpack_from('<4I',original,16+i*16) for i in range(128)]
    def lump(i):
        off,size,_,_ = headers[i]
        return original[off:off+size]
    def put(i,payload):
        data.extend(bytes((-len(data))%16))
        off = len(data)
        data.extend(payload)
        struct.pack_into('<4I',data,16+i*16,off,len(payload),headers[i][2],0)
    world_count = struct.unpack_from('<I',lump(0x7b))[0]
    meshes = bytearray(lump(0x50)[:world_count*28])
    bounds = bytearray(lump(0x51)[:world_count*32])
    sorts = bytearray(lump(0x52)[:world_count*12])
    first_sky_index = struct.unpack_from('<I',lump(0x50),world_count*28)[0]
    indices = bytearray(lump(0x4f)[:first_sky_index*2])
    lit = bytearray(lump(0x49))
    positions = bytearray(lump(3))
    normals = bytearray(lump(0x1e))
    textures = bytearray(lump(2))
    names = bytearray(lump(0x2b))
    table = bytearray(lump(0x2c))
    texture_index = len(textures)//36
    textures.extend(struct.pack('<3f6I',0.,0.,0.,len(table)//4,4096,4096,0,0,0xa00))
    table.extend(struct.pack('<I',len(names)))
    names.extend(b'world\\phase_runner_preview\\phase_runner_sky\0')
    center = (-761.369792,-4444.361979,-1024.)
    radius = 22000.
    start_vertex = len(lit)//44
    triangles = 0
    def vertex(theta,phi):
        n = (math.sin(theta)*math.cos(phi),math.sin(theta)*math.sin(phi),math.cos(theta))
        point = [center[k]+radius*n[k] for k in range(3)]
        # Sphere-map projection: zenith in the image center, horizon ring,
        # nadir at the outside edge. Original mesh UVs remain to be recovered.
        radial = .5*math.sin(theta/2)
        uv = (.5+radial*math.cos(phi),.5-radial*math.sin(phi))
        pos_index,normal_index = len(positions)//12,len(normals)//12
        positions.extend(struct.pack('<3f',*point))
        normals.extend(struct.pack('<3f',*(-v for v in n)))
        tangent_index = len(normals)//12
        normals.extend(struct.pack('<3f',-math.sin(phi),math.cos(phi),0.))
        return struct.pack('<2I2f4B4f2I',pos_index,normal_index,*uv,255,255,255,255,
            .25015666584,.13143643240,0.,0.,tangent_index,0)
    for latitude in range(32):
        for longitude in range(64):
            corners = [(math.pi*latitude/32,2*math.pi*longitude/64),
                       (math.pi*(latitude+1)/32,2*math.pi*longitude/64),
                       (math.pi*(latitude+1)/32,2*math.pi*(longitude+1)/64),
                       (math.pi*latitude/32,2*math.pi*(longitude+1)/64)]
            for corner_ids in ((0,1,2),(0,2,3)):
                if (latitude==0 and corner_ids==(0,2,3)) or (latitude==31 and corner_ids==(0,1,2)):
                    continue
                local = len(lit)//44-start_vertex
                for corner in corner_ids:
                    lit.extend(vertex(*corners[corner]))
                # Sphere parameterization points outward for this order;
                # native clockwise rendering therefore shows its inside.
                indices.extend(struct.pack('<3H',local,local+1,local+2))
                triangles += 1
    count = triangles*3
    record = bytearray(meshes[:28])
    struct.pack_into('<I4H',record,0,first_sky_index,triangles,0,count-1,2)
    struct.pack_into('<H',record,22,world_count)
    meshes.extend(record)
    sorts.extend(struct.pack('<3hHi',texture_index,0,-1,count-1,start_vertex))
    bounds.extend(struct.pack('<8f',*center,radius+1,radius,radius,radius,0.))
    total = world_count+1
    world = bytearray(lump(0x0e))
    old_limits = struct.unpack_from('<6f',world)
    low = [min(old_limits[k],center[k]-radius-1) for k in range(3)]
    high = [max(old_limits[k+3],center[k]+radius+1) for k in range(3)]
    struct.pack_into('<6f',world,0,*low,*high)
    struct.pack_into('<I',world,28,total)
    level = bytearray(lump(0x7b))
    struct.pack_into('<3I',level,0,total,total,total)
    objects = bytearray()
    for record in struct.iter_unpack('<8f',bounds):
        c,e = record[:3],record[4:7]
        objects.extend(struct.pack('<3fI3fI',*(c[k]-e[k] for k in range(3)),0,
                                             *(c[k]+e[k] for k in range(3)),0))
    replacements = {2:textures,3:positions,0x1e:normals,0x2b:names,0x2c:table,
        0x47:b'',0x49:lit,0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts,
        0x0e:world,0x7b:level,0x77:struct.pack('<3f2BH3f2H',*low,0,total,total,*high,0,0),
        0x78:struct.pack('<'+'H'*total,*range(total)),0x79:objects}
    for i,payload in replacements.items():
        put(i,payload)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'):
        shutil.copy2(ent,output.parent/ent.name)
    status = json.loads(source.with_name('source-build.json').read_text())
    status['preview_sky'] = dict(recovered_image=True,projection_approximate=True,
        native_vista_model_converted=False,triangles=triangles,visual_verified=False)
    status['render_triangles'] = sum(struct.unpack_from('<H',meshes,i+4)[0] for i in range(0,len(meshes),28))
    status['render_repair']['sky_meshes'] = 0
    status['render_repair']['world_meshes'] = total
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(dict(sky=status['preview_sky'],checks=validate_bsp(output)),indent=2))


if __name__ == '__main__':
    add()
