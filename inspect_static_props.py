"""Inventory missing static props and the recovered meshes available to restore them."""
import collections
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import bsp_tool


def inspect():
    bsp=bsp_tool.load_bsp(str(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp'))
    sprp=bsp.external.GAME_LUMP.sprp
    sources=json.loads((ROOT/'output/phase-runner/prepared-models/preparation.json').read_text())
    available={m['model']:m['staged_qc'] for m in sources['models']}
    counts=collections.Counter()
    placements=[]
    for index,prop in enumerate(sprp.props):
        name=sprp.model_names[prop.model_name]
        origin=[prop.origin[k]-(26000.,19000.,0.)[k] for k in range(3)]
        in_arena=abs(origin[0])<10000 and abs(origin[1])<10000 and -5000<origin[2]<10000
        if in_arena:
            counts[name]+=1
        placements.append(dict(index=index,model=name,origin=origin,
            angles=[prop.angles.y,prop.angles.z,prop.angles.x],scale=prop.scale,
            skin=prop.skin,solid_mode=int(prop.solid_mode.value),flags=int(prop.flags),
            in_arena=in_arena,source_qc=available.get(name)))
    output=ROOT/'output/phase-runner/static-props.json'
    output.write_text(json.dumps(placements,indent=2))
    report=dict(total=len(placements),arena=sum(counts.values()),
        arena_with_mesh=sum(p['in_arena'] and p['source_qc'] is not None for p in placements),
        arena_models=len(counts),common=counts.most_common(20))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    inspect()
