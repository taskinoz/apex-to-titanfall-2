import json,struct,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from build_center_detail import placement_sections
from plan_budget_model_geometry import model_sections
from simplify_preview_draw import simplifier
from build_phase_runner_catwalks import mesh_faces,face_key
from repair_preview_index_padding import read_lumps
from optimize_portalfree_render import DT,material_name

def source():
    props=json.loads((ROOT/'output/phase-runner/static-props.json').read_text());cache={};faces={};fn=simplifier()
    for p in props:
        if p['index'] not in (5816,5817,5818,5819,16840,16841,16843,16844):continue
        n=Path(p['model']).stem
        if n not in cache:cache[n]=model_sections(p,0,fn,.25,2.)
        for mat,data in placement_sections(p,*cache[n][:3]):
            for t in data:
                k=face_key(t[:,:3])
                if k in faces:raise ValueError('Duplicate console source face')
                faces[k]=(mat,t,p['index'])
    return faces

def main():
    expected=source();l=read_lumps(ROOT/'output/phase-runner/center-detail/mp_phase_runner.bsp',(2,3,0x2b,0x2c,0x49,0x4f,0x50,0x52));v=np.frombuffer(l[0x49],DT)
    counts=collections.Counter();errors=collections.defaultdict(list);unmatched=set(expected)
    for mi,r,raw,ids,tri in mesh_faces(l):
        for t,vi in zip(tri,ids):
            k=face_key(t)
            if k not in expected:continue
            mat,data,p=expected[k];unmatched.discard(k);counts[mat]+=1
            uv={bytes(q[:3]):q[6:8] for q in data}
            wanted=np.array([uv[bytes(q)] for q in t]);got=v['uv'][vi]
            errors[mat].append((float(abs(got-wanted).max()),float(abs(got-(wanted*[1,-1]+[0,1])).max())))
    print('counts',dict(counts),'unmatched',len(unmatched),'UVerrors', {m:np.max(a,axis=0).tolist() for m,a in errors.items()})
if __name__=='__main__':main()
