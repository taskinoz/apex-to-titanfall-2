"""Recover building fixture positions and space low-cost lights along both tunnels."""
import json,struct
from repair_environment_lighting import ROOT,np
OUT=ROOT/'output/phase-runner/interior-lighting'

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'logs/source-local-lights.json').read_text());byid={v['index']:v for v in source}
    result=[]
    for index in (79,83,88,98,85,82,115,89,93,80,92,94):
        row=byid[index];rgb=np.array(row['intensity']);rgb=rgb/rgb.max()*.85
        result.append(dict(kind='building',source_light_index=index,origin=row['origin'],colour=rgb.tolist(),radius=620,
            provenance='Original Apex interior POINT fixture; colour normalized for native preview exposure'))
    routes=json.loads((ROOT/'output/phase-runner/preview-tunnel-walkways/tunnel-walkways.json').read_text())['routes']
    for route_index,r in enumerate(routes):
        p=np.array(r['points']);distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
        for n,s in enumerate(np.arange(160,distance[-1]-100,560)):
            pos=np.array([np.interp(s,distance,p[:,k]) for k in range(3)]);pos[2]+=120
            colour=[.85,.92,1.05] if n%3 else [1.05,.78,.48]
            result.append(dict(kind='tunnel',route=route_index,distance=float(s),origin=pos.tolist(),colour=colour,radius=650,
                provenance='New traversal adaptation, 120 units above the confirmed walkway'))
    if len(result)>61:raise ValueError('Native one-page light-table capacity exceeded')
    for i,row in enumerate(result):row['hardware_index']=i+2
    with (OUT/'lights.bin').open('wb') as f:
        for row in result:f.write(struct.pack('<7fI',*row['origin'],row['radius'],*row['colour'],row['hardware_index']))
    (OUT/'lights.json').write_text(json.dumps(dict(lights=result,count=len(result),maximum_light_table_index=len(result)+1,
        sun_and_menu_indices_preserved=[0,1],no_runtime_dynamic_light_entities=True),indent=2))
    print('Interior fixtures:',len(result),'building:',sum(r['kind']=='building' for r in result),'tunnel:',sum(r['kind']=='tunnel' for r in result))
if __name__=='__main__':prepare()
