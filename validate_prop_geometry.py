"""Check restored prop rendering indices, bounds, winding and unchanged physics."""
import json
import math
import struct
from pathlib import Path
from build_preview_source import cross,subtract

ROOT=Path(__file__).resolve().parent


def validate(phase_structures=False,support_structures=False,area_details=False,missing_sections=False,broad_restore=False,portal_repair=False,landscape_restore=False):
    source=(ROOT/'output/phase-runner'/('preview-packed' if landscape_restore else 'preview-portal-filtered' if portal_repair else 'preview-compact' if broad_restore else 'preview-details' if missing_sections else 'preview-supports' if area_details else 'preview-clean-sky' if support_structures else ('preview-terrain' if phase_structures else 'preview-sky'))/'mp_phase_runner_preview.bsp').read_bytes()
    folder=ROOT/'output/phase-runner'/('preview-expanded' if broad_restore else 'preview-faces' if missing_sections else 'preview-details' if area_details else 'preview-supports' if support_structures else ('preview-structures' if phase_structures else 'preview-props'))
    if landscape_restore:folder=ROOT/'output/phase-runner/preview-landscape'
    if portal_repair:folder=ROOT/'output/phase-runner/preview-portal-surfaces'
    target=(folder/'mp_phase_runner_preview.bsp').read_bytes()
    def lump(data,i):
        o,n,_,_=struct.unpack_from('<4I',data,16+i*16)
        return data[o:o+n]
    for i in (1,0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f):
        if lump(source,i)!=lump(target,i):raise ValueError(f'Unexpected physics change in lump {i:#x}')
    source_meshes=lump(source,0x50)
    meshes=lump(target,0x50)
    if not meshes.startswith(source_meshes):raise ValueError('Existing render meshes were modified')
    for i in (3,0x1e,0x49):
        if not lump(target,i).startswith(lump(source,i)):
            raise ValueError(f'Existing vertex data changed in lump {i:#x}')
    positions,normals,lit,indices,sorts,bounds=(lump(target,i) for i in (3,0x1e,0x49,0x4f,0x52,0x51))
    triangles=0;incorrect_winding=0;normal_disagreements=0
    first=len(source_meshes)//28
    for index in range(first,len(meshes)//28):
        mesh=meshes[index*28:(index+1)*28]
        start,count,first_vertex,last_vertex=struct.unpack_from('<I3H',mesh)
        sort_index=struct.unpack_from('<H',mesh,22)[0]
        texture,_,_,last,base=struct.unpack_from('<3hHi',sorts,sort_index*12)
        if first_vertex!=0 or last_vertex!=count*3-1 or last!=last_vertex:
            raise ValueError('Invalid native prop vertex range')
        bound=struct.unpack_from('<8f',bounds,index*32)
        for t in range(count):
            points=[];ns=[]
            for local in struct.unpack_from('<3H',indices,(start+t*3)*2):
                if local>last:raise ValueError('Prop index exceeds local vertex range')
                record=(base+local)*44
                p,n=struct.unpack_from('<2I',lit,record)
                tangent=struct.unpack_from('<I',lit,record+36)[0]&0x7fffffff
                if p*12+12>len(positions) or n*12+12>len(normals) or tangent*12+12>len(normals):
                    raise ValueError('Prop vertex refers outside a vertex buffer')
                point=struct.unpack_from('<3f',positions,p*12)
                normal=struct.unpack_from('<3f',normals,n*12)
                if not all(math.isfinite(v) for v in point+normal):raise ValueError('Invalid prop vertex')
                if any(abs(point[k]-bound[k])>bound[k+4]+.05 for k in range(3)):
                    raise ValueError('Prop vertex exceeds mesh bounds')
                points.append(point);ns.append(normal)
            face=cross(subtract(points[1],points[0]),subtract(points[2],points[0]))
            averaged=tuple(sum(n[k] for n in ns)/3 for k in range(3))
            dot=sum(face[k]*averaged[k] for k in range(3))
            if dot>1e-4:incorrect_winding+=1
            if sum(v*v for v in averaged)<.01:normal_disagreements+=1
        triangles+=count
    if incorrect_winding:raise ValueError(f'{incorrect_winding} prop triangles face the wrong way')
    expected=json.loads((folder/'source-build.json').read_text())['landscape_restore' if landscape_restore else 'portal_material_repair' if portal_repair else 'broad_restore' if broad_restore else 'missing_sections' if missing_sections else 'area_details' if area_details else 'support_structures' if support_structures else ('map_structures' if phase_structures else 'structural_props')]
    if triangles!=expected['triangles']-expected['degenerate_triangles_removed']:
        raise ValueError('Restored triangle count differs from staged geometry')
    refs=struct.unpack('<'+'H'*(len(lump(target,0x78))//2),lump(target,0x78))
    if sorted(refs)!=list(range(len(meshes)//28)):raise ValueError('Visibility omits or duplicates render meshes')
    from preview_visibility import validate_visibility
    visibility=validate_visibility(lump(target,0x77),lump(target,0x78),lump(target,0x79),bounds)
    report=dict(visibility_tree=visibility,restored_prop_triangles=triangles,prop_meshes=len(meshes)//28-first,
        existing_geometry_unchanged=True,collision_unchanged=True,index_bounds_verified=True,
        native_winding_verified=True,mesh_bounds_verified=True,visibility_references_verified=True,
        triangles_with_disagreeing_vertex_normals=normal_disagreements,visual_verified=False)
    (folder/'validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':validate()
