"""Read-only comparison of native MP menu stages, world lights and shadow sets."""
import sys,json,struct,re,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.branches import shared
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3,WorldLightv2,ShadowEnvironment
from repair_preview_index_padding import read_lumps

def inspect(path):
    l=read_lumps(path,[0,5,0x36,0x37,0x53,0x63,0x64,0x7a,0x7b]);entities=[]
    for data in [l[0]]+[p.read_bytes() for p in path.parent.glob(path.stem+'_*.ent')]:
        if b'{' not in data:continue
        data=data[data.index(b'{'):]
        entities.extend(shared.Entities.from_bytes(data))
    with path.open('rb') as f:h=f.read(2064)
    v=struct.unpack_from('<I',h,16+0x36*16+8)[0];cls=WorldLightv3 if v==3 else WorldLightv2;size=112 if v==3 else 108
    lights=[]
    for i in range(0,len(l[0x36]),size):
        a=cls.from_bytes(l[0x36][i:i+size])
        if a.type.name not in ('SKY_LIGHT','SKY_AMBIENT'):continue
        lights.append(dict(index=i//size,**{k:str(getattr(a,k)) for k in a.__slots__}))
    selected=[e for e in entities if any('menu_' in str(v) for v in e.values()) or e.get('classname') in ('worldspawn','light_environment','shadow_control','env_cascade_light','env_projectedtexture')]
    return dict(path=str(path),menu_and_light_entities=selected,global_lights=lights,
        shadow_environments=[str(ShadowEnvironment.from_bytes(l[5][i:i+36])) for i in range(0,len(l[5]),36)],
        csm_node_bytes=len(l[0x63]),csm_ref_bytes=len(l[0x64]),level_info=list(struct.unpack('<4I3f',l[0x7b])),
        lightmap_headers=list(struct.iter_unpack('<I2H',l[0x53])),
        light_page_first_entries=[list(x[:8]) for x in struct.iter_unpack('<63h',l[0x7a])],
        parent_info_bytes=len(l[0x37]))

if __name__=='__main__':
    paths=[ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',ROOT/'inputs/titanfall2-colony/maps/mp_colony02.bsp',
        ROOT/'inputs/titanfall2-coliseum/maps/mp_coliseum.bsp',ROOT/'output/phase-runner/preview-material-repaired/mp_phase_runner_preview.bsp']
    result=[inspect(p) for p in paths if p.is_file()]
    (ROOT/'logs/menu-lighting-audit.json').write_text(json.dumps(result,indent=2))
    for r in result:print(json.dumps({k:v for k,v in r.items() if k not in ('lightmap_headers','light_page_first_entries')},indent=2))
