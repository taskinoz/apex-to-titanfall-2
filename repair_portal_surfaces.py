"""Replace identified tunnel surfaces and restore newly recovered moss meshes."""
import collections
import json
import math
import mmap
import shutil
import struct
from pathlib import Path
from recover_model_slots import load_bound_sections
from stage_prop_geometry import rotation, transform, load_mesh
from build_preview_source import cross, subtract
from compact_preview_bsp import compact
from preview_visibility import build_visibility, validate_visibility

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT/'output/phase-runner'
PORTALS = {16729, 16730}
MOSS = 'mdl/desertlands/icelandic_moss_mod_01.rmdl'
OVERLAYS = {'ambient_occlusion', 'slum_grime_decal_01_bt', 's2s_bolt_decals_01'}


def placed(corners, prop):
    matrix = rotation(prop['angles'])
    result = []
    for c in corners:
        p = transform(c[:3], matrix, prop['origin'], prop['scale'])
        n = transform(c[3:6], matrix)
        length = math.sqrt(sum(v*v for v in n))
        if length < 1e-6 or not all(math.isfinite(v) for v in c):
            raise ValueError('Invalid source vertex')
        result.append(struct.pack('<8f', *p, *(v/length for v in n), c[6], 1-c[7]))
    return result


def nondegenerate(vertices):
    p = [struct.unpack_from('<3f', v) for v in vertices]
    return sum(v*v for v in cross(subtract(p[1], p[0]), subtract(p[2], p[0]))) >= 1e-10


def key(vertices):
    # Engine winding changes vertex order, but leaves the eight source fields intact.
    return tuple(sorted(vertices))


def stage():
    props = json.loads((PROJECT/'static-props.json').read_text())
    geometry = PROJECT/'portal-geometry'
    geometry.mkdir(exist_ok=True)
    sources = [ROOT/'tools/legion/exported_files/materials', PROJECT/'shared-assets/materials',
        PROJECT/'common-assets/exported_files/materials', PROJECT/'common-assets/materials',
        PROJECT/'legion-assets/exported_files/materials']
    available = {p.name.lower() for d in sources if d.is_dir() for p in d.iterdir()
        if p.is_dir() and (p/(p.name+'_albedoTexture.dds')).is_file()}
    streams = {}; counts = collections.Counter(); restored = []; excluded = collections.Counter()
    cache = {}; old = collections.Counter(); old_positions = set()
    try:
        for prop in props:
            is_portal = prop['index'] in PORTALS
            if not is_portal and not (prop['in_arena'] and prop['model'] == MOSS and not prop['source_qc']):
                continue
            basename = Path(prop['model']).stem
            raw = ROOT/'tools/legion/exported_files/models'/basename/(basename+'.rmdl')
            qc = Path(prop['source_qc']) if is_portal else raw.with_suffix('.qc')
            if basename not in cache:
                cache[basename] = load_bound_sections(qc, raw)
            sections, slots, skins = cache[basename]
            if prop['skin'] >= len(skins):
                raise ValueError('Placement selects an invalid original skin family')
            skin = skins[prop['skin']]
            required = {skin[slot] for slot in slots} - OVERLAYS
            if required - available:
                raise ValueError(f'Missing recovered textures for {basename}: {required-available}')
            if is_portal:
                mesh, _ = load_mesh(qc)
                for _, corners in mesh:
                    vertices = placed(corners, prop)
                    if nondegenerate(vertices):
                        old[key(vertices)] += 1
                        old_positions.update(v[:12] for v in vertices)
            count = 0
            for section, slot in zip(sections, slots):
                name = skin[slot]
                if name in OVERLAYS:
                    excluded[name] += len(section)
                    continue
                material = 'prop/'+name
                if material not in streams:
                    streams[material] = (geometry/(name+'.bin')).open('wb')
                for corners in section:
                    vertices = placed(corners, prop)
                    streams[material].write(b''.join(vertices))
                counts[material] += len(section); count += len(section)
            restored.append(dict(index=prop['index'], model=prop['model'], triangles=count,
                compiled_material_slots=slots, original_materials=skin,
                origin=prop['origin'], angles=prop['angles'], scale=prop['scale']))
    finally:
        for stream in streams.values(): stream.close()
    report = dict(candidate_props=len(restored), restored_props=len(restored), models=len(cache),
        triangles=sum(counts.values()), material_counts=dict(counts), restored=restored,
        compiled_material_slots_verified=True, ambiguous_material_triangles=0,
        unsupported_opaque_overlay_triangles_removed=dict(excluded), collision_added=False,
        limitations=['Native TF2 world shader approximation; layered Apex materials remain approximate.',
            'AO and decal overlay meshes are omitted rather than drawn as opaque metal.',
            'GPU pop-in still requires a client check.'])
    (geometry/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('restored','material_counts')}, indent=2))
    return old, old_positions


def filter_old(old, old_positions):
    source = PROJECT/'preview-complete-pass/mp_phase_runner_preview.bsp'
    output = PROJECT/'preview-portal-filtered/mp_phase_runner_preview.bsp'
    expected = sum(old.values()); removed = 0
    with source.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        headers = [struct.unpack_from('<4I', data, 16+i*16) for i in range(128)]
        offsets = {i:headers[i][0] for i in (3,0x1e,0x49,0x4f,0x52)}
        def payload(i):
            o,n,_,_ = headers[i]; return data[o:o+n]
        meshdata = payload(0x50); boundsdata = payload(0x51)
        meshes = bytearray(); bounds = bytearray(); indices = bytearray()
        for meshno in range(len(meshdata)//28):
            at = meshno*28
            first, count = struct.unpack_from('<IH', meshdata, at)
            sort = struct.unpack_from('<H', meshdata, at+22)[0]
            base = struct.unpack_from('<i', data, offsets[0x52]+sort*12+8)[0]
            kept = bytearray()
            for t in range(count):
                packed = data[offsets[0x4f]+(first+t*3)*2:offsets[0x4f]+(first+t*3+3)*2]
                local = struct.unpack('<3H', packed)
                li = offsets[0x49]+(base+local[0])*44
                pi = struct.unpack_from('<I', data, li)[0]
                p = data[offsets[3]+pi*12:offsets[3]+pi*12+12]
                matched = None
                if p in old_positions:
                    vertices=[]
                    for v in local:
                        vi = offsets[0x49]+(base+v)*44
                        pi,ni = struct.unpack_from('<2I', data, vi)
                        vertices.append(data[offsets[3]+pi*12:offsets[3]+pi*12+12]
                            +data[offsets[0x1e]+ni*12:offsets[0x1e]+ni*12+12]+data[vi+8:vi+16])
                    candidate=key(vertices)
                    if old[candidate]: matched=candidate
                if matched is not None:
                    old[matched]-=1; removed+=1
                else: kept.extend(packed)
            if kept:
                record=bytearray(meshdata[at:at+28])
                struct.pack_into('<IH',record,0,len(indices)//2,len(kept)//6)
                meshes.extend(record);indices.extend(kept);bounds.extend(boundsdata[meshno*32:meshno*32+32])
        if removed != expected or any(old.values()):
            raise ValueError(f'Exact tunnel replacement failed: {removed}/{expected} matched')
        total=len(meshes)//28
        world=bytearray(payload(0x0e));struct.pack_into('<I',world,28,total)
        level=bytearray(payload(0x7b));struct.pack_into('<3I',level,0,total,total,total)
        nodes,refs,objects=build_visibility(bounds)
        visibility=validate_visibility(nodes,refs,objects,bounds)
    report=compact(source,output,{0x50:meshes,0x51:bounds,0x4f:indices,0x0e:world,0x7b:level,
        0x77:nodes,0x78:refs,0x79:objects})
    status=json.loads(source.with_name('source-build.json').read_text())
    status['portal_surface_filter']=dict(old_portal_triangles_removed=removed,
        exact_position_normal_uv_match=True,other_triangles_retained=True,collision_unchanged=True)
    status['visibility_rebuild']=visibility;status['portal_filter_compaction']=report
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    for ent in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(ent,output.parent/ent.name)
    print(json.dumps(status['portal_surface_filter'],indent=2))


if __name__ == '__main__':
    filter_old(*stage())
