"""Check active BSP material names against packaged native RPak material headers."""
import json,struct
from pathlib import Path
from extract_native_material import NativePak

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT/'output/phase-runner'

def audit():
    path=PROJECT/'preview-native-cells/mp_phase_runner_preview.bsp'
    with path.open('rb') as f:
        h=f.read(2064)
        def lump(i):o,n=struct.unpack_from('<2I',h,16+i*16);f.seek(o);return f.read(n)
        textures=list(struct.iter_unpack('<3f6I',lump(2)));strings=lump(0x2b);table=list(struct.iter_unpack('<I',lump(0x2c)));sorts=list(struct.iter_unpack('<3hHi',lump(0x52)));meshes=lump(0x50)
    used={struct.unpack_from('<H',meshes,at+22)[0] for at in range(0,len(meshes),28)}
    names={}
    for si in used:
        ti=sorts[si][0];row=textures[ti];at=table[row[3]][0];name=strings[at:strings.index(0,at)].decode().replace('\\','/').lower();names[name]=row[4:6]
    materials={}
    for p in (PROJECT/'world-materials/build/phase_runner_world.rpak',ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak'):
        pak=NativePak(p)
        for asset in pak.assets:
            if asset['type']!='matl' or asset['version']!=12:continue
            spec,uber=pak.material(asset);name=spec['name'].lower()
            materials[name]=dict(width=spec['width'],height=spec['height'],textures=len(spec['$textures']),
                rasterizer=spec['rasterizerFlags'],shader_set=spec['shaderSet'])
        del pak
    missing=sorted(set(names)-set(materials))
    if missing:raise ValueError('Unresolved active BSP materials: '+repr(missing))
    mismatches=[n for n,(w,h) in names.items() if materials[n]['width']!=w or materials[n]['height']!=h]
    if mismatches:raise ValueError('Material dimensions disagree: '+repr(mismatches))
    center_names=('beacon_industrial_floor_01','metal_worn_tileable_01','metal_corrugated_wall_grey_01','trim_metal_01','sleek_city_trims_clean_01')
    center={n:materials.get('world/phase_runner_preview/'+n) for n in center_names}
    if not all(center.values()):raise ValueError('Central structural material missing')
    report=dict(active_material_names=len(names),all_active_material_headers_present=True,
        dimensions_match=True,central_ring_materials=center,runtime_texture_visibility_verified=False,
        limitation='Name, dimensions and dependency checks cannot prove GPU shading or identify the user-reported invisible props without their location.')
    (PROJECT/'central-material-audit-0.1.21.json').write_text(json.dumps(report,indent=2))
    status=json.loads(path.with_name('source-build.json').read_text());status['central_material_audit']=report
    path.with_name('source-build.json').write_text(json.dumps(status,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':audit()
