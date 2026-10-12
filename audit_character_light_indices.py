"""Compare shipped probe links with native light positions and radii."""
import json,struct
from audit_character_lighting import PATHS,ROOT
from repair_environment_lighting import WorldLightv3,np
from repair_preview_index_padding import read_lumps
out={}
for name in ('homestead','colony'):
    l=read_lumps(PATHS[name],(0x36,0x65,0x68));lights=[WorldLightv3.from_bytes(l[0x36][i:i+112]) for i in range(0,len(l[0x36]),112)]
    filtered=[a for a in lights if a.type.name!='SKY_AMBIENT'];results={key:[] for key in ('raw','filtered')}
    for x,y,z,probe,unknown in struct.iter_unpack('<3fIi',l[0x68]):
        record=l[0x65][probe*48:(probe+1)*48];weights=record[32:36];ids=struct.unpack_from('<4h',record,36)
        for weight,index in zip(weights,ids):
            if not weight or index<0:continue
            for key,table in (('raw',lights),('filtered',filtered)):
                if index>=len(table):continue
                a=table[index]
                if a.radius>0:results[key].append(float(np.linalg.norm(np.array([x,y,z])-np.array(list(a.origin)))/a.radius))
        if len(results['raw'])>1000:break
    out[name]={key:dict(links=len(v),within_radius=int((np.array(v)<1.01).sum()),median_distance_to_radius=float(np.median(v))) for key,v in results.items()}
(ROOT/'logs/character-light-index-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
