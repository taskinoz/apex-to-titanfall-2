"""Inventory render props from Apex BSP entities and entity partitions."""
import collections,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def audit():
    folder=ROOT/'inputs/extracted-client/maps'
    sources=[folder/'mp_rr_arena_phase_runner.bsp.0000.bsp_lump',*sorted(folder.glob('mp_rr_arena_phase_runner_*.ent'))]
    preparation=json.loads((ROOT/'output/phase-runner/prepared-models/preparation.json').read_text())
    available={m['model']:m['staged_qc'] for m in preparation['models']}
    props=[];counts={}
    for source in sources:
        text=source.read_bytes().decode('utf-8',errors='replace').rstrip('\0')
        entities=[dict(re.findall(r'"([^"\n]+)"\s*"([^"\n]*)"',block)) for block in re.findall(r'\{([^{}]*)\}',text)]
        counts[source.name]=len(entities)
        for index,entity in enumerate(entities):
            model=entity.get('model','')
            if not entity.get('classname','').startswith('prop_') or not model.startswith(('mdl/','models/')):continue
            origin=[float(x)-d for x,d in zip(entity.get('origin','0 0 0').split(),(26000,19000,0))]
            props.append(dict(source=source.name,index=index,entity=entity,preview_origin=origin,source_qc=available.get(model)))
    report=dict(entity_counts=counts,render_entity_props=len(props),recovered_mesh_count=sum(bool(p['source_qc']) for p in props),model_counts=dict(collections.Counter(p['entity']['model'] for p in props)),props=props,static_placement_source='GAME_LUMP.sprp',static_placements=len(json.loads((ROOT/'output/phase-runner/static-props.json').read_text())),limitation='Inventory only. Dynamic behavior, animation and runtime entities are not converted. Editor markers are excluded.')
    (ROOT/'output/phase-runner/entity-prop-inventory.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='props'},indent=2))
if __name__=='__main__':audit()
