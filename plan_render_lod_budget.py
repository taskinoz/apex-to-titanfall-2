"""Estimate a full-placement lower-detail diagnostic from original Apex LODs."""
import collections,json,struct
from pathlib import Path
from repair_preview_index_padding import read_lumps
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

def main():
    selected=set()
    for folder in ('prop-geometry','phase-structure-geometry','support-geometry',
                   'area-detail-geometry','broad-geometry','portal-geometry','landscape-geometry'):
        selected.update(q['index'] for q in json.loads((P/folder/'report.json').read_text())['restored'])
    props=[q for q in json.loads((P/'static-props.json').read_text()) if q['index'] in selected]
    lods={q['model']:q['lods'] for q in json.loads((ROOT/'logs/available-vg-lods.json').read_text())}
    totals=collections.Counter();missing=[];models=collections.Counter()
    for prop in props:
        name=Path(prop['model']).stem
        if name not in lods:missing.append(prop);continue
        levels=lods[name];models[name]+=1
        totals['highest']+=levels[0]['triangles'];totals['lowest']+=levels[-1]['triangles']
        totals['second_lowest']+=levels[max(0,len(levels)-2)]['triangles']
    world={}
    for name in ('preview-sky','preview-draw-restored'):
        l=read_lumps(P/name/'mp_phase_runner_preview.bsp',(0x50,))
        rows=list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))
        world[name]=dict(meshes=len(rows),first_94_triangles=sum(r[1] for r in rows[:94]))
    report=dict(placements=len(props),available_placements=sum(models.values()),model_count=len(models),
        prop_triangles=dict(totals),unavailable=missing,world=world,
        model_contributions=sorted([dict(model=n,placements=count,highest=lods[n][0]['triangles']*count,
                                        lowest=lods[n][-1]['triangles']*count) for n,count in models.items()],
                                    key=lambda q:q['lowest'],reverse=True))
    (ROOT/'logs/render-lod-budget-plan.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('unavailable','model_contributions')},indent=2))
    print('Missing models:',dict(collections.Counter(q['model'] for q in missing)))
    print(json.dumps(report['model_contributions'][:10],indent=2))
if __name__=='__main__':main()
