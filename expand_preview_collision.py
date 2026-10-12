"""Build bounded native TF2 brush collision for recovered support surfaces.

All nondegenerate merged regular floors/ramps are retained. Remaining capacity
goes to arena walls nearest its centre. Static props and special Apex leaves
are still unsupported. This is a development collider, not original physics.
"""
import json
import math
import shutil
import struct
from pathlib import Path
from merge_collision import polygons
from build_preview_source import cross, subtract


def expand(source, collision, output):
    data=bytearray(source.read_bytes())
    floors=[]; walls=[]
    for p in polygons(collision):
        n=cross(subtract(p[1],p[0]),subtract(p[2],p[0]))
        length=math.sqrt(sum(v*v for v in n))
        if length<.01: continue
        n=tuple(v/length for v in n)
        if abs(n[2])>.5:
            if n[2]<0: p=list(reversed(p)); n=tuple(-v for v in n)
            centre=[sum(v[k] for v in p)/len(p) for k in range(3)]
            if abs(centre[0])<8000 and abs(centre[1])<8000 and -4000<centre[2]<6000:
                floors.append((p,n))
        else:
            center=[sum(v[k] for v in p)/len(p) for k in range(3)]
            # Centre wall coverage on the actual inspection spawn, rather than
            # on the coordinate origin several kilometres away in game units.
            anchor=(-761.369792,-4444.361979,-1024.)
            walls.append((sum((center[k]-anchor[k])**2 for k in range(3)),p,n))
    walls.sort(key=lambda v:v[0])
    selected=floors+[(p,n) for _,p,n in walls[:64000-len(floors)]]
    if len(selected)>64000: raise ValueError('Too many support brushes for this development grid')
    brushes=bytearray(); planes=bytearray(); props=bytearray(); offsets=bytearray(); tex=bytearray()
    bounds=[]; tests=[]; wall_tests=[]
    for p,n in selected:
        bottom=[tuple(v[k]-n[k]*8 for k in range(3)) for v in p]
        vertices=p+bottom
        low=[min(v[k] for v in vertices) for k in range(3)]
        high=[max(v[k] for v in vertices) for k in range(3)]
        if any(v < -32760 or v > 32760 for v in low+high): continue
        center=[(low[k]+high[k])/2 for k in range(3)]
        extent=[(high[k]-low[k])/2 for k in range(3)]
        interior=[sum(v[k] for v in vertices)/len(vertices) for k in range(3)]
        cutting=[]
        faces=[p[:3],bottom[:3]]+[[p[i],p[(i+1)%len(p)],bottom[i]] for i in range(len(p))]
        for face in faces:
            normal=cross(subtract(face[1],face[0]),subtract(face[2],face[0]))
            size=math.sqrt(sum(v*v for v in normal))
            if size<1e-6: continue
            normal=[v/size for v in normal]
            distance=sum(normal[k]*face[0][k] for k in range(3))
            if sum(normal[k]*interior[k] for k in range(3))>distance:
                normal=[-v for v in normal]; distance=-distance
            if any(abs(abs(v)-1)<1e-6 for v in normal): continue
            cutting.append((*normal,distance))
        index=len(brushes)//32; first=len(planes)//16
        brushes.extend(struct.pack('<3f2BH3fI',*center,len(cutting),len(cutting),index,*extent,first))
        # Match the compiler's material assignment for implicit AABB faces
        # and polygon cutting planes.
        props.extend(struct.pack('<'+'H'*(6+len(cutting)),*([0]*6+[1]*len(cutting))))
        tex.extend(bytes(32*(6+len(cutting))))
        for plane in cutting:
            planes.extend(struct.pack('<4f',*plane)); offsets.extend(struct.pack('<H',0))
        bounds.append((low,high))
        if len(tests)<12 and n[2]>.5:
            c=[sum(v[k] for v in p)/len(p) for k in range(3)]
            tests.append(dict(brush_index=index,kind='support',start=[c[k]+n[k]*32 for k in range(3)],end=[c[k]-n[k]*32 for k in range(3)]))
        elif len(wall_tests)<12 and abs(n[2])<=.5:
            c=[sum(v[k] for v in p)/len(p) for k in range(3)]
            if not any(sum((c[k]-other['centre'][k])**2 for k in range(3))<128**2 for other in wall_tests):
                wall_tests.append(dict(brush_index=index,kind='wall',centre=c,start=[c[k]+n[k]*32 for k in range(3)],end=[c[k]-n[k]*32 for k in range(3)]))
    sets=bytearray(); cells=bytearray(); set_bounds=bytearray()
    # TF2 runtime probes confirm row-major cells: X increments before Y.
    # The older schema comment states the opposite; mixed-sign quadrants
    # otherwise lose all their traces even with correct brush geometry.
    for y in (-1,0):
        for x in (-1,0):
            first=len(sets)//8
            for i,(low,high) in enumerate(bounds):
                if high[0]<x*32768 or low[0]>(x+1)*32768 or high[1]<y*32768 or low[1]>(y+1)*32768: continue
                sets.extend(struct.pack('<HHI',0,1,(i<<8)))
                center=[round((low[k]+high[k])/2) for k in range(3)]
                extent=[math.ceil(max(abs(low[k]-center[k]),abs(high[k]-center[k])))+2 for k in range(3)]
                set_bounds.extend(struct.pack('<3hH3hH',*center,0x8000,*extent,0))
            count=len(sets)//8-first
            if first+count>65535: raise ValueError('Collision grid reference overflow')
            cells.extend(struct.pack('<HH',first,count))
    cells.extend(struct.pack('<HH',len(sets)//8,0))
    old_planes=struct.unpack_from('<I',data,16+16)[0]
    # The visibility root's existing plane remains at index zero.
    plane_zero=data[old_planes:old_planes+16]
    entity_offset,entity_length=struct.unpack_from('<2I',data,16)
    entities=bytes(data[entity_offset:entity_offset+entity_length]).rstrip(b'\0')
    entities+=b'\n{\n"classname" "sky_camera"\n"targetname" "skybox_cam_level"\n"origin" "30000 30000 30000"\n"angles" "0 0 0"\n"skyscale" "1000"\n"scale" "1"\n"fogenable" "0"\n"useworldfog" "0"\n}\n\0'
    replacements={0:entities,1:plane_zero+planes,0x55:struct.pack('<f6i',32768.,-1,-1,2,2,0,1),
                  0x56:cells,0x57:sets,0x58:set_bounds,0x59:b'',0x5a:b'',
                  0x5b:struct.pack('<I',1),0x5c:brushes,0x5d:offsets,0x5e:props,0x5f:tex}
    for i,payload in replacements.items():
        data.extend(bytes((-len(data))%16)); offset=len(data); data.extend(payload)
        version=struct.unpack_from('<I',data,16+16*i+8)[0]
        struct.pack_into('<4I',data,16+16*i,offset,len(payload),version,0)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'): shutil.copy2(ent,output.parent/ent.name)
    report=json.loads(source.with_name('source-build.json').read_text())
    report['initial_collision_sample']=dict(limit=report['collision_sample_limit'],counts=report['collision_counts'])
    report['collision_sample_limit']=64000
    report['collision_counts']=dict(original_regular_polygons=report['collision_counts']['source_polygons'],arena_support_polygons=len(floors),selected_wall_polygons=len(selected)-len(floors))
    report['limitations']=['Missing Apex static props and prop collision','Original Apex textures not yet packaged','Partial wall coverage and unsupported special collision leaves','Approximate solid prisms; original contents flags not translated','Lighting and sky awaiting manual visual verification']
    report['collision_sample_brushes']=len(bounds)
    report['collision_probes']=tests+wall_tests
    report['collision_expansion']=dict(merged_support_polygons=len(floors),selected_wall_polygons=len(selected)-len(floors),brushes=len(bounds),geo_sets=len(sets)//8,grid_order='y rows, x columns',thickness=8,walking_verified=False,remaining=['Static props','Special collision leaves','Excluded walls','Original contents flags'])
    output.with_name('source-build.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['collision_expansion'],indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('collision',type=Path); parser.add_argument('output',type=Path)
    a=parser.parse_args(); expand(a.source,a.collision,a.output)
