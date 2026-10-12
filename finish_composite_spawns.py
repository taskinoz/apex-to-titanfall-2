"""Finalize six native Titan starts from successful engine floor/hull probes."""
import json,os
from light_composite import OUT,SOURCE
from build_composite_map import entity_bytes
from repair_environment_lighting import entities
from compact_preview_bsp import compact
def finish():
    rows=[e for e in entities(SOURCE) if not e.get('classname','').startswith('info_spawnpoint_titan')]
    proof=json.loads((OUT/'spawn-probes-corrected.json').read_text())['data']
    safe=[p['origin'] for p in proof if p['floor'] and p['pilot'] and p['titan'] and abs(p['origin'][0])>=2000]
    for p in safe:
        team=2 if p[0]<0 else 3
        for kind,number in (('info_spawnpoint_titan_start',team),('info_spawnpoint_titan',0)):
            rows.append(dict(classname=kind,origin=' '.join(map(str,p)),angles=f'0 {0 if team==2 else 180} 0',teamnumber=str(number),gamemode_tdm='1',gamemode_ffa='1'))
    target=OUT/'mp_arena_composite-spawns.bsp';compact(SOURCE,target,{0:entity_bytes(rows)});os.replace(target,SOURCE)
    report=json.loads((OUT/'lighting.json').read_text());report['titan_starts']=len(safe);report['limitations']=['No bounced GI or new reflection cubemaps','Source spot lights approximated as points','Native alpha approximation; multilayer glass and source vertex colours not yet reproduced'];(OUT/'lighting.json').write_text(json.dumps(report,indent=2))
    print('Finalized',len(safe),'hull-verified Titan starts')
if __name__=='__main__':finish()
