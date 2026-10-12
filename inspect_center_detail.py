import json,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from read_vg_static import load
P=ROOT/'output/phase-runner'
def main():
    raw=json.loads((P/'static-props.json').read_text());print('static structure',type(raw).__name__,list(raw)[:12] if isinstance(raw,dict) else len(raw))
    props=raw['props'] if isinstance(raw,dict) else raw
    restored={}
    for group in ('prop','phase-structure','support','area-detail','broad','portal','landscape'):
        r=json.loads((P/(group+'-geometry')/'report.json').read_text())
        for p in r['restored']:restored[p['index']]=p
        print(group, {k:len(v) for k,v in r.items() if isinstance(v,list)})
    ness=[p for p in props if 'ness' in p['model'].lower()]
    print('NESSIE',json.dumps(ness,indent=2))
    plan=json.loads((ROOT/'logs/tunnel-detail-model-plan.json').read_text());print('plan keys',list(plan))
    for m in plan.get('models_detail',[]):
        if 'ness' in m['model'].lower():print('OLD_NESSIE_PLAN',json.dumps(m))
    for p in ness:
        folder=ROOT/'tools/legion/exported_files/models'/Path(p['model']).stem
        for i in range(8):
            try:
                sections,slots,skins=load(folder,i)
                print('NESSIE_LOD',i,'triangles',sum(len(s) for s in sections),'slots',slots,'skins',skins)
            except ValueError:break
    focus=np.array([2921.4,893.7,-1067.0])
    missing=[];near=[]
    for p in props:
        origin=np.array(p['origin']);dist=float(np.linalg.norm((origin-focus)[:2]));center=float(np.linalg.norm(origin[:2]))
        if dist<1200 or center<2200:
            row={k:p.get(k) for k in ('index','model','origin','angles','scale','skin','solid_mode','in_arena','source_qc')};row.update(nessie_distance=round(dist),center_distance=round(center),rendered=p['index'] in restored)
            if row['rendered']:near.append(row)
            else:missing.append(row)
    print('MISSING',json.dumps(missing,indent=2));print('NEAR_NESSIE',json.dumps(sorted([p for p in near if p['nessie_distance']<350],key=lambda p:p['nessie_distance']),indent=2))
    inv=json.loads((P/'entity-prop-inventory.json').read_text());print('entity keys',list(inv))
    ent=[]
    for p in inv['props']:
        o=np.array(p['preview_origin']);d=np.linalg.norm((o-focus)[:2]);c=np.linalg.norm(o[:2])
        if d<1200 or c<2200:ent.append(p)
    print('ENTITIES',json.dumps(ent,indent=2))
    (ROOT/'logs/center-detail-candidates.json').write_text(json.dumps(dict(nessie=ness,missing=missing,near_nessie=[p for p in near if p['nessie_distance']<350],entities=ent),indent=2))
if __name__=='__main__':main()
