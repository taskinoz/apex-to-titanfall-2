"""Replace unrelated prototype lights with recovered Phase Runner globals."""
import json
import shutil
import struct
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def build():
    sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    apex=bsp_tool.load_bsp(str(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp')).external
    source=ROOT/'output/phase-runner/preview-structures/mp_phase_runner_preview.bsp'
    output=ROOT/'output/phase-runner/preview-lighting/mp_phase_runner_preview.bsp'
    original=source.read_bytes()
    def lump(i):
        o,n,_,_=struct.unpack_from('<4I',original,16+i*16)
        return original[o:o+n]
    lights=bytearray()
    recovered=[]
    for light in apex.WORLD_LIGHTS:
        if light.type.name not in ('SKY_LIGHT','SKY_AMBIENT'):continue
        record=bytearray(light.as_bytes())
        if len(record)!=112:raise ValueError('Unexpected global light layout')
        origin=tuple(light.origin)
        struct.pack_into('<3f',record,0,origin[0]-26000,origin[1]-19000,origin[2])
        # No light texture or entity parent is carried across from Apex.
        struct.pack_into('<2i',record,92,-1,0)
        lights.extend(record)
        recovered.append(dict(type=light.type.name,intensity=list(light.intensity),normal=list(light.normal)))
    if len(recovered)!=2:raise ValueError('Expected one sun and one ambient light')
    sun=tuple(apex.LEVEL_INFO.sun_normal)
    level=bytearray(lump(0x7b));struct.pack_into('<3f',level,16,*sun)
    # No static caster geometry has been converted yet. Use an explicitly empty
    # environment instead of the compiler's unrelated small placeholder bounds.
    maximum=3.4028234663852886e38
    nodes=struct.pack('<3f2BH3f2H',maximum,maximum,maximum,0,0,0,-maximum,-maximum,-maximum,0,0)
    changes={0x36:(lights,3),0x7b:(level,0),0x63:(nodes,0)}
    data=bytearray(original)
    for i,(payload,version) in changes.items():
        data.extend(bytes((-len(data))%16));o=len(data);data.extend(payload)
        struct.pack_into('<4I',data,16+i*16,o,len(payload),version,0)
    for i in range(128):
        if i in changes:continue
        o,n,_,_=struct.unpack_from('<4I',data,16+i*16)
        if data[o:o+n]!=lump(i):raise ValueError(f'Unintended change in lump {i}')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    for ent in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(ent,output.parent/ent.name)
    status=json.loads(source.with_name('source-build.json').read_text())
    status['lighting_repair']=dict(recovered_globals=recovered,sun_normal=list(sun),
        removed_prototype_lights=len(lump(0x36))//112,geometry_and_physics_unchanged=True,
        original_static_shadow_casters_converted=False,original_lightmaps_baked=False,
        visual_verified=False,limitation='Source sun/ambient only; temporary native lightmap illumination remains.')
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status['lighting_repair'],indent=2))


if __name__=='__main__':build()
