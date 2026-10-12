"""Remove unsupported transparent terrain overlays and identical render copies.

The preview uses opaque TF2 materials. Apex terrain overlays need blend shaders
that are not ported yet; drawing them opaque produces coplanar interference.
Collision, vertices, materials and the sky dome are preserved byte-for-byte.
"""
import collections
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path
from package_northstar import validate_bsp

ROOT = Path(__file__).resolve().parent


def build():
    sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    apex = bsp_tool.load_bsp(str(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp')).external
    overlays = set()
    for mesh in apex.MESHES:
        name = apex.texture_data_surface_name(apex.MATERIAL_SORTS[mesh.material_sort].texture_data).replace('\\','/').lower()
        if int(mesh.flags) & 0x10 and any(part in name for part in (
                '/moss/', '/snow/', '/dirt/', '/lava_land/', 'slum_grime_decal')):
            overlays.add(name.rsplit('/',1)[-1])
    source = ROOT/'output/phase-runner/preview-props/mp_phase_runner_preview.bsp'
    output = ROOT/'output/phase-runner/preview-ground/mp_phase_runner_preview.bsp'
    original = source.read_bytes()
    headers = [struct.unpack_from('<4I',original,16+i*16) for i in range(128)]
    def lump(i):
        o,n,_,_ = headers[i]
        return original[o:o+n]
    positions,lit,old_meshes,old_indices,sorts,textures,names,table = (
        lump(i) for i in (3,0x49,0x50,0x4f,0x52,2,0x2b,0x2c))
    lump_normals = lump(0x1e)
    meshes,indices,bounds = bytearray(),bytearray(),bytearray()
    seen = set()
    removed = collections.Counter()
    duplicates = collections.Counter()
    for mi in range(len(old_meshes)//28):
        record = bytearray(old_meshes[mi*28:(mi+1)*28])
        start,count = struct.unpack_from('<IH',record)
        sort = struct.unpack_from('<H',record,22)[0]
        texture,_,_,_,base = struct.unpack_from('<3hHi',sorts,sort*12)
        ni = struct.unpack_from('<I',textures,texture*36+12)[0]
        no = struct.unpack_from('<I',table,ni*4)[0]
        name = names[no:names.index(0,no)].decode().replace('\\','/').lower()
        basename = name.rsplit('/',1)[-1]
        if basename in overlays and mi < 93:
            removed[basename] += count
            continue
        first = len(indices)//2
        kept = 0
        for t in range(count):
            raw = old_indices[(start+t*3)*2:(start+t*3+3)*2]
            corners = []
            for local in struct.unpack('<3H',raw):
                vertex = lit[(base+local)*44:(base+local+1)*44]
                p = struct.unpack_from('<I',vertex)[0]
                # Match position, normal vector, UV, color and lightmap UV.
                # Cyclic rotations match; reversed winding does not.
                normal = struct.unpack_from('<I',vertex,4)[0]
                corners.append(positions[p*12:p*12+12]+lump_normals[normal*12:normal*12+12]+vertex[8:36])
            key = hashlib.sha256(name.encode()+min(
                b''.join(corners[i:]+corners[:i]) for i in range(3))).digest()
            if key in seen:
                duplicates[basename] += 1
                continue
            seen.add(key)
            indices.extend(raw)
            kept += 1
        if kept:
            struct.pack_into('<IH',record,0,first,kept)
            meshes.extend(record)
            bounds.extend(lump(0x51)[mi*32:(mi+1)*32])
    total = len(meshes)//28
    world,level,node = (bytearray(lump(i)) for i in (0x0e,0x7b,0x77))
    if total > 255: raise ValueError('Visibility leaf capacity exceeded')
    struct.pack_into('<I',world,28,total)
    struct.pack_into('<3I',level,0,total,total,total)
    struct.pack_into('<BBH',node,12,0,total,total)
    objects = bytearray()
    for b in struct.iter_unpack('<8f',bounds):
        c,e = b[:3],b[4:7]
        objects.extend(struct.pack('<3fI3fI',*(c[k]-e[k] for k in range(3)),0,
                                   *(c[k]+e[k] for k in range(3)),0))
    changes = {0x50:meshes,0x4f:indices,0x51:bounds,0x0e:world,0x7b:level,
               0x77:node,0x78:struct.pack('<'+'H'*total,*range(total)),0x79:objects}
    data = bytearray(original)
    for i,payload in changes.items():
        data.extend(bytes((-len(data))%16))
        off = len(data);data.extend(payload)
        struct.pack_into('<4I',data,16+i*16,off,len(payload),headers[i][2],0)
    # Validate every unmodified lump, including all physics and vertex data.
    for i in range(128):
        if i not in changes:
            o,n,_,_ = struct.unpack_from('<4I',data,16+i*16)
            if data[o:o+n] != lump(i): raise ValueError(f'Unintended change in lump {i}')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'): shutil.copy2(ent,output.parent/ent.name)
    status = json.loads(source.with_name('source-build.json').read_text())
    status['ground_surface_repair'] = dict(unsupported_overlay_triangles=sum(removed.values()),
        removed_overlays=dict(removed),identical_triangles_removed=sum(duplicates.values()),
        duplicates_by_material=dict(duplicates),collision_unchanged=True,visual_verified=False,
        limitation='Transparent terrain detail layers are omitted until native blending is ported.')
    status['render_triangles'] = len(indices)//6
    status['render_repair']['world_meshes'] = total
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(dict(repair=status['ground_surface_repair'],checks=validate_bsp(output)),indent=2))


if __name__ == '__main__':
    build()
