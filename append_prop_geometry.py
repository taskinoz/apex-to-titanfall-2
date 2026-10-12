"""Add staged architectural meshes to the TF2 preview without changing physics."""
import json
import math
import shutil
import struct
from pathlib import Path
from build_preview_source import cross,subtract
from package_northstar import validate_bsp

ROOT=Path(__file__).resolve().parent


def unit(v):
    length=math.sqrt(sum(x*x for x in v))
    return tuple(x/length for x in v) if length>1e-9 else None


def tangent(normal,s,t):
    along=sum(normal[k]*s[k] for k in range(3))
    result=unit(tuple(s[k]-normal[k]*along for k in range(3)))
    if result is None:
        axis=(0.,0.,1.) if abs(normal[2])<.9 else (0.,1.,0.)
        result=unit(cross(axis,normal))
    mirrored=sum(a*b for a,b in zip(cross(normal,result),t))<0
    return result,mirrored


def build(phase_structures=False,support_structures=False,area_details=False,missing_sections=False,broad_restore=False,portal_repair=False,landscape_restore=False):
    source=ROOT/'output/phase-runner'/('preview-compact' if broad_restore else 'preview-details' if missing_sections else 'preview-supports' if area_details else 'preview-clean-sky' if support_structures else ('preview-terrain' if phase_structures else 'preview-sky'))/'mp_phase_runner_preview.bsp'
    output=ROOT/'output/phase-runner'/('preview-expanded' if broad_restore else 'preview-faces' if missing_sections else 'preview-details' if area_details else 'preview-supports' if support_structures else ('preview-structures' if phase_structures else 'preview-props'))/'mp_phase_runner_preview.bsp'
    geometry=ROOT/'output/phase-runner'/('broad-geometry' if broad_restore else 'missing-section-geometry' if missing_sections else 'area-detail-geometry' if area_details else 'support-geometry' if support_structures else ('phase-structure-geometry' if phase_structures else 'prop-geometry'))
    if portal_repair:
        source=ROOT/'output/phase-runner/preview-portal-filtered/mp_phase_runner_preview.bsp'
        output=ROOT/'output/phase-runner/preview-portal-surfaces/mp_phase_runner_preview.bsp'
        geometry=ROOT/'output/phase-runner/portal-geometry'
    if landscape_restore:
        source=ROOT/'output/phase-runner/preview-packed/mp_phase_runner_preview.bsp'
        output=ROOT/'output/phase-runner/preview-landscape/mp_phase_runner_preview.bsp'
        geometry=ROOT/'output/phase-runner/landscape-geometry'
    report=json.loads((geometry/'report.json').read_text())
    materials=json.loads((ROOT/'output/phase-runner/world-materials/mapping.json').read_text())['materials']
    original=source.read_bytes()
    headers=[struct.unpack_from('<4I',original,16+i*16) for i in range(128)]
    def lump(i):
        o,n,_,_=headers[i]
        return original[o:o+n]
    data=bytearray(original)
    def put(i,payload):
        data.extend(bytes((-len(data))%16))
        off=len(data);data.extend(payload)
        struct.pack_into('<4I',data,16+i*16,off,len(payload),headers[i][2],0)
    positions,normals,lit,meshes,bounds,sorts,indices,textures,names,table=(
        bytearray(lump(i)) for i in (3,0x1e,0x49,0x50,0x51,0x52,0x4f,2,0x2b,0x2c))
    first_prop_mesh=len(meshes)//28
    base_mesh=bytes(meshes[:28])
    textured_triangles=0
    degenerate=0
    for material,count in report['material_counts'].items():
        path=geometry/(material.rsplit('/',1)[-1]+'.bin')
        if path.stat().st_size!=count*96:
            raise ValueError(f'Incomplete geometry buffer {path}')
        mapping=materials.get(material)
        if mapping is None and (phase_structures or support_structures or area_details or missing_sections or broad_restore or portal_repair or landscape_restore):
            basename=material.rsplit('/',1)[-1]
            matches=[v for k,v in materials.items() if k.rsplit('/',1)[-1]==basename]
            if matches: mapping=matches[0]
        if (phase_structures or support_structures or area_details or missing_sections or broad_restore or portal_repair or landscape_restore) and mapping is None:
            raise ValueError(f'No recovered material for map structure: {material}')
        texture_index=0
        if mapping:
            texture_index=len(textures)//36
            table.extend(struct.pack('<I',len(names)))
            names.extend(mapping['name'].replace('/','\\').encode()+b'\0')
            textures.extend(struct.pack('<3f6I',0.,0.,0.,len(table)//4-1,mapping['width'],mapping['height'],0,0,0xa00))
        with path.open('rb') as stream:
            while payload:=stream.read(96*10000):
                base=len(lit)//44
                first=len(indices)//2
                low=[float('inf')]*3;high=[float('-inf')]*3
                triangles=0
                for offset in range(0,len(payload),96):
                    vertices=[struct.unpack_from('<8f',payload,offset+c*32) for c in range(3)]
                    a,b,c=vertices
                    e1,e2=subtract(b[:3],a[:3]),subtract(c[:3],a[:3])
                    face=cross(e1,e2)
                    if sum(v*v for v in face)<1e-10:
                        degenerate+=1;continue
                    u1,v1=b[6]-a[6],b[7]-a[7]
                    u2,v2=c[6]-a[6],c[7]-a[7]
                    determinant=u1*v2-u2*v1
                    if abs(determinant)>1e-9:
                        s=tuple((e1[k]*v2-e2[k]*v1)/determinant for k in range(3))
                        t=tuple((e2[k]*u1-e1[k]*u2)/determinant for k in range(3))
                    else:
                        s,t=e1,e2
                    local=len(lit)//44-base
                    averaged=tuple(sum(v[k+3] for v in vertices)/3 for k in range(3))
                    winding=(0,2,1) if sum(face[k]*averaged[k] for k in range(3))>0 else (0,1,2)
                    for vertex in vertices:
                        p,n,uv=vertex[:3],vertex[3:6],vertex[6:8]
                        for k in range(3): low[k]=min(low[k],p[k]);high[k]=max(high[k],p[k])
                        pi,ni=len(positions)//12,len(normals)//12
                        positions.extend(struct.pack('<3f',*p));normals.extend(struct.pack('<3f',*n))
                        si=len(normals)//12
                        tangent_s,mirrored=tangent(n,s,t)
                        normals.extend(struct.pack('<3f',*tangent_s))
                        lit.extend(struct.pack('<2I2f4B4f2I',pi,ni,*uv,255,255,255,255,
                            .25015666584,.13143643240,0.,0.,si|(0x80000000 if mirrored else 0),0))
                    indices.extend(struct.pack('<3H',*(local+i for i in winding)))
                    triangles+=1
                if not triangles: continue
                if mapping: textured_triangles+=triangles
                count_vertices=triangles*3
                mesh_index=len(meshes)//28
                record=bytearray(base_mesh)
                struct.pack_into('<I4H',record,0,first,triangles,0,count_vertices-1,2)
                # Overlay removal can leave unused sort records. Mesh and
                # material-sort indices are therefore no longer interchangeable.
                struct.pack_into('<H',record,22,len(sorts)//12)
                meshes.extend(record)
                sorts.extend(struct.pack('<3hHi',texture_index,0,-1,count_vertices-1,base))
                center=[(low[k]+high[k])/2 for k in range(3)]
                extent=[(high[k]-low[k])/2 for k in range(3)]
                bounds.extend(struct.pack('<8f',*center,math.sqrt(sum(v*v for v in extent))+.01,*extent,0.))
    total=len(meshes)//28
    if total>=65535: raise ValueError('Mesh index limit exceeded')
    world=bytearray(lump(0x0e))
    low=list(struct.unpack_from('<3f',world));high=list(struct.unpack_from('<3f',world,12))
    objects=bytearray()
    for record in struct.iter_unpack('<8f',bounds):
        c,e=record[:3],record[4:7]
        lo=[c[k]-e[k] for k in range(3)];hi=[c[k]+e[k] for k in range(3)]
        for k in range(3):low[k]=min(low[k],lo[k]);high[k]=max(high[k],hi[k])
        objects.extend(struct.pack('<3fI3fI',*lo,0,*hi,0))
    struct.pack_into('<6f',world,0,*low,*high);struct.pack_into('<I',world,28,total)
    level=bytearray(lump(0x7b));struct.pack_into('<3I',level,0,total,total,total)
    from preview_visibility import build_visibility,validate_visibility
    nodes,visibility_refs,objects=build_visibility(bounds)
    visibility_report=validate_visibility(nodes,visibility_refs,objects,bounds)
    for i,payload in {3:positions,0x1e:normals,0x49:lit,0x50:meshes,0x51:bounds,0x52:sorts,
        0x4f:indices,2:textures,0x2b:names,0x2c:table,0x0e:world,0x7b:level,
        0x77:nodes,0x78:visibility_refs,0x79:objects}.items():put(i,payload)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(ent,output.parent/ent.name)
    status=json.loads(source.with_name('source-build.json').read_text())
    status_key='broad_restore' if broad_restore else 'missing_sections' if missing_sections else 'area_details' if area_details else 'support_structures' if support_structures else ('map_structures' if phase_structures else 'structural_props')
    if portal_repair:status_key='portal_material_repair'
    if landscape_restore:status_key='landscape_restore'
    status[status_key]={k:v for k,v in report.items() if k not in ('restored','material_counts')}
    status[status_key].update(first_mesh=first_prop_mesh,mesh_count=total-first_prop_mesh,
        textured_triangles=textured_triangles,degenerate_triangles_removed=degenerate,
        prop_collision_converted=False,visual_verified=False)
    status['visibility_rebuild']=visibility_report
    status['render_repair']['world_meshes']=total
    status['render_triangles']=sum(struct.unpack_from('<H',meshes,i+4)[0] for i in range(0,len(meshes),28))
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(dict(props=status[status_key],checks=validate_bsp(output)),indent=2))


if __name__=='__main__':build()
