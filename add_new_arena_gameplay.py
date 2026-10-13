"""Translate authored safety volumes and rope endpoints without guessed boxes."""
import collections
import json
import os
import sys
from new_arena_ports import CONFIG,folder
from decode_source_trigger_volumes import native
from apply_arena_boundaries import rope
from repair_environment_lighting import entities,text_entities
from compact_preview_bsp import compact


def build(ident):
    c=CONFIG[ident];out=folder(ident);source=out/(c['target']+'.bsp');scene=json.loads((out/'scene.json').read_text())
    prefix=ident.replace('-','_')+'_source_';additions=[];omissions=[];shifts=tuple(-v for v in c['offset'])
    for i,e in enumerate(scene['source_entities']):
        if e['classname'] not in ('trigger_hurt','trigger_out_of_bounds') or not any(k.startswith('*coll') for k in e):continue
        n=native(e,shifts,prefix+'boundary_'+str(i))
        if n is not None:additions.append(n)
        else:omissions.append(dict(source_entity=i,reason='Outside native safe trigger domain'))
    endpoints={e.get('link_guid'):e for e in scene['source_entities']
               if e.get('classname') in ('zipline_end','zipline') and e.get('link_guid')}
    routes=[]
    for i,e in enumerate(scene['source_entities']):
        if e['classname']!='zipline':continue
        if not e.get('link_to_guid_0'):continue
        endpoint=endpoints.get(e.get('link_to_guid_0'))
        if not endpoint:
            omissions.append(dict(source_entity=i,reason='Zipline endpoint not resolved'));continue
        a=[float(v)+d for v,d in zip(e['origin'].split(),c['offset'])]
        b=[float(v)+d for v,d in zip(endpoint['origin'].split(),c['offset'])]
        if all(-16000<v<16000 for v in a+b):
            additions.extend(rope(a,b,prefix+'zipline_'+str(i)));routes.append(dict(source_entity=i,start=a,end=b))
    rows=[e for e in entities(source) if not e.get('targetname','').startswith(prefix)]
    target=source.with_suffix('.gameplay.bsp');compact(source,target,{0:text_entities(rows+additions),0x18:b''});os.replace(target,source)
    (out/'source-gameplay.json').write_text(json.dumps(dict(added_counts=dict(collections.Counter(e['classname'] for e in additions)),
        native_trigger_planes=True,source_signed_collision_preserved=True,ropes=routes,omissions=omissions),indent=2))
    print(ident,'source gameplay',collections.Counter(e['classname'] for e in additions),flush=True)


if __name__=='__main__':
    for ident in CONFIG if sys.argv[1]=='all' else [sys.argv[1]]:build(ident)
