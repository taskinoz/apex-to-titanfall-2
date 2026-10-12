"""Repair the diagnostic compiler's render records using TF2's native layouts.

This deliberately keeps the existing lumps at their original offsets: game-lump
directories contain absolute offsets. Changed lumps are appended and their main
headers updated. No original input is edited.
"""
import argparse
import json
import math
import shutil
import struct
from pathlib import Path


def repair(source, native, output):
    original=source.read_bytes()
    reference=native.read_bytes()
    data=bytearray(original)
    headers=[struct.unpack_from('<4I',original,16+16*i) for i in range(128)]
    def lump(index):
        offset,length,_,_=headers[index]
        return original[offset:offset+length]
    def native_lump(index):
        offset,length,_,_=struct.unpack_from('<4I',reference,16+16*index)
        return reference[offset:offset+length]
    def put(index,payload,version=None):
        data.extend(bytes((-len(data))%16))
        offset=len(data)
        data.extend(payload)
        struct.pack_into('<4I',data,16+16*index,offset,len(payload),
                         headers[index][2] if version is None else version,0)

    unlit=lump(0x47)
    if not unlit or lump(0x49):
        raise ValueError('Expected an unrepaired preview with unlit world vertices')
    normals=bytearray(lump(0x1e))
    tangent_indices={}
    lit=bytearray()
    for offset in range(0,len(unlit),20):
        normal_index=struct.unpack_from('<I',unlit,offset+4)[0]
        if normal_index not in tangent_indices:
            n=struct.unpack_from('<3f',normals,normal_index*12)
            axis=(0.,0.,1.) if abs(n[2])<.9 else (0.,1.,0.)
            s=(axis[1]*n[2]-axis[2]*n[1],axis[2]*n[0]-axis[0]*n[2],axis[0]*n[1]-axis[1]*n[0])
            length=math.sqrt(sum(v*v for v in s))
            if length<1e-8:
                raise ValueError('Degenerate world normal')
            tangent_indices[normal_index]=len(normals)//12
            normals.extend(struct.pack('<3f',*(v/length for v in s)))
        lit.extend(unlit[offset:offset+20])
        # This coordinate lies inside a lit native floor triangle. The previous
        # coordinate sampled zero illumination in SKY_A and left ground black.
        lit.extend(struct.pack('<4f2I',.25015666584,.13143643240,0.,0.,tangent_indices[normal_index],0))

    original_meshes=lump(0x50)
    original_indices=lump(0x4f)
    meshes=bytearray()
    indices=bytearray()
    sorts=bytearray()
    bounds=bytearray()
    positions=list(struct.iter_unpack('<3f',lump(3)))
    vertex_start=0
    for i in range(len(original_meshes)//28):
        offset=i*28
        first,triangles,old_first,count=struct.unpack_from('<I3H',original_meshes,offset)
        old_sort=struct.unpack_from('<H',original_meshes,offset+22)[0]
        old_base=struct.unpack_from('<i',lump(0x52),old_sort*12+8)[0]
        local_indices=[]
        for j in range(first,first+triangles*3):
            old=struct.unpack_from('<H',original_indices,j*2)[0]
            local=old+old_base-vertex_start
            if not 0<=local<count:
                raise ValueError(f'Mesh {i} has invalid local index {local}')
            local_indices.append(local)
        if local_indices!=list(range(count)):
            raise ValueError('Expected the diagnostic importer\'s per-corner vertex layout')
        # Native first_vertex and num_vertices are local first/last offsets,
        # rather than a global start and an exclusive vertex count.
        for chunk_start in range(0,count,30000):
            chunk_count=min(30000,count-chunk_start)
            index=len(meshes)//28
            record=bytearray(original_meshes[offset:offset+28])
            struct.pack_into('<I4H',record,0,len(indices)//2,chunk_count//3,0,chunk_count-1,2)
            struct.pack_into('<H',record,22,index)
            struct.pack_into('<I',record,24,0x100a00)
            meshes.extend(record)
            clockwise=[corner for t in range(0,chunk_count,3) for corner in (t,t+2,t+1)]
            indices.extend(struct.pack('<'+'H'*chunk_count,*clockwise))
            sorts.extend(struct.pack('<3hHi',0,0,-1,chunk_count-1,vertex_start+chunk_start))
            points=[positions[struct.unpack_from('<I',unlit,v*20)[0]]
                    for v in range(vertex_start+chunk_start,vertex_start+chunk_start+chunk_count)]
            minimum=[min(p[k] for p in points) for k in range(3)]
            maximum=[max(p[k] for p in points) for k in range(3)]
            center=[(minimum[k]+maximum[k])/2 for k in range(3)]
            extent=[(maximum[k]-minimum[k])/2 for k in range(3)]
            bounds.extend(struct.pack('<8f',*center,math.sqrt(sum(v*v for v in extent))+.01,*extent,0.))
        vertex_start+=count
    if vertex_start!=len(unlit)//20:
        raise ValueError('Mesh vertex ranges do not cover the imported geometry')
    world_count=len(meshes)//28

    # Six inward-facing sky quads enclose the imported world. They use the
    # installed native sky material and the sky pass's unlit vertex format.
    world=bytearray(lump(0x0e))
    limits=struct.unpack_from('<6f',world)
    low=[v-512. for v in limits[:3]]
    # The 3D sky camera/vista at (30000,30000,30000) must belong to the
    # visibility root. The earlier root ended at z=1060 and culled the sky.
    high=[max(v+512.,35000.) for v in limits[3:]]
    struct.pack_into('<6f',world,0,*low,*high)
    points=list(struct.iter_unpack('<3f',lump(3)))
    # Keep sky surfaces within the engine's normal view distance around the
    # playable arena, rather than wrapping distant Apex backdrop geometry.
    sky_low=[-16000.,-16000.,-4000.]
    sky_high=[16000.,16000.,12000.]
    sky=bytearray()
    sky_sort=world_count
    for axis in range(3):
        other=[a for a in range(3) if a!=axis]
        for side in range(2):
            normal=[0.,0.,0.];normal[axis]=1. if side==0 else -1.
            normal_index=len(normals)//12
            normals.extend(struct.pack('<3f',*normal))
            corners=[]
            for u,v in [(0,0),(1,0),(1,1),(0,1)]:
                p=[0.,0.,0.]
                p[axis]=(sky_low,sky_high)[side][axis]
                p[other[0]]=(sky_low,sky_high)[u][other[0]]
                p[other[1]]=(sky_low,sky_high)[v][other[1]]
                corners.append(p)
            a,b,c=corners[:3]
            cross=( (b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]),
                    (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]),
                    (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) )
            if sum(cross[k]*normal[k] for k in range(3))<0:
                corners.reverse()
            start=len(sky)//20
            first_index=len(indices)//2
            for j,p in enumerate(corners):
                sky.extend(struct.pack('<2I2f4B',len(points),normal_index,j&1,j>>1,255,255,255,255))
                points.append(tuple(p))
            indices.extend(struct.pack('<6H',start,start+2,start+1,start,start+3,start+2))
            # Match native sky metadata, including its unused vertex_type field.
            meshes.extend(struct.pack('<I3H6b2h2BHI',first_index,2,start,3,0,-1,-1,-1,-1,-1,-1,-1,255,255,sky_sort,0x404))
            center=[sum(p[k] for p in corners)/4 for k in range(3)]
            extent=[max(abs(p[k]-center[k]) for p in corners) for k in range(3)]
            bounds.extend(struct.pack('<8f',*center,math.sqrt(sum(v*v for v in extent))+.01,*extent,0.))
    sorts.extend(struct.pack('<3hHi',2,-1,0,23,0))
    total=len(meshes)//28
    struct.pack_into('<I',world,28,total)
    tex=bytearray(lump(2))
    struct.pack_into('<4I',tex,16,512,512,0,0)
    struct.pack_into('<I',tex,32,0xa00)
    names=lump(0x2b)+b'tools\\toolsskybox\0'
    name_table=lump(0x2c)+struct.pack('<I',len(lump(0x2b)))
    tex.extend(struct.pack('<3f6I',0.,0.,0.,2,128,128,0,0,0x404))
    # One visibility leaf references every world mesh exactly once. This is
    # intentionally unoptimized; it avoids the unfinished portal/tree stubs.
    node=struct.pack('<3f2BH3f2H',*low,0,total,total,*high,0,0)
    object_bounds=bytearray()
    for i in range(total):
        record=struct.unpack_from('<8f',bounds,i*32)
        center,extent=record[:3],record[4:7]
        object_bounds.extend(struct.pack('<3fI3fI',*(center[k]-extent[k] for k in range(3)),0,*(center[k]+extent[k] for k in range(3)),0))
    level=bytearray(lump(0x7b))
    struct.pack_into('<3I',level,0,world_count,world_count,world_count)
    level[16:28]=native_lump(0x7b)[16:28]
    replacements={3:b''.join(struct.pack('<3f',*p) for p in points),2:tex,0x0e:world,
                  0x1e:normals,0x47:sky,0x49:lit,0x4f:indices,0x50:meshes,
                  0x51:bounds,0x52:sorts,0x2b:names,0x2c:name_table,
                  0x77:node,0x78:struct.pack('<'+'H'*total,*range(total)),
                  0x7b:level,0x79:object_bounds,
                  0x6a:struct.pack('<2i',-1,0),0x6b:struct.pack('<2H2h',0,0,1,-1),
                  0x53:native_lump(0x53),0x62:native_lump(0x62),0x69:native_lump(0x69)}
    for index,payload in replacements.items():
        put(index,payload)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'):
        shutil.copy2(ent,output.parent/ent.name)
    report=json.loads(source.with_name('source-build.json').read_text())
    report['render_triangles']+=12
    report['render_repair']=dict(world_meshes=world_count,sky_meshes=6,
        local_vertex_ranges=True,nonzero_mesh_radii=True,native_world_vertex_format=True,
        single_visibility_leaf=True,temporary_native_lightmaps=True,
        lightmap_uv=[.25015666584,.13143643240],sky_camera_inside_visibility_root=True,
        visual_verified=False)
    report['render_repair']['native_clockwise_winding']=True
    (output.parent/'source-build.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['render_repair'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('native',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    repair(args.source,args.native,args.output)
