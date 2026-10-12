"""Identify exact source placements at the six reported problem locations."""
import json,struct
from pathlib import Path
import numpy as np
from stage_prop_geometry import rotation,transform
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'
POINTS={'stairs':[-4176.4,-1463.9,-1014.6],'pipe':[-2163.4,3016.3,-974.4],'crate':[-1330.3,3043.2,-928.0],'pipe_fall':[3587.7,2513.7,-1152.9],'pipe_section':[4484.,474.,-1152.1],'rocks':[1839.9,-782.,-1200.7]}
def audit():
 props=json.loads((P/'static-props.json').read_text());cache={};placements=[];owned={}
 for folder,file in [('preview-prop-physics','prop-collision-placements.json'),('preview-structure-physics','structure-collision-placements.json'),('preview-prop-coverage','prop-coverage-repair.json')]:
  data=json.loads((P/folder/file).read_text())
  for r in data.get('restored',data.get('added_props',[])):owned[r['index']]=r
 restored=set()
 for path in P.glob('*-geometry/report.json'):restored.update(r['index'] for r in json.loads(path.read_text()).get('restored',[]))
 for p in props:
  name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in cache:
   if not base.with_suffix('.rmdl').exists():cache[name]=None
   else:
    b=base.with_suffix('.rmdl').read_bytes();cache[name]=struct.unpack_from('<6f',b,496)
  bounds=cache[name]
  if bounds is None:continue
  matrix=rotation(p['angles']);corners=np.array([transform([bounds[k+3*((i>>k)&1)] for k in range(3)],matrix,p['origin'],p['scale']) for i in range(8)])
  placements.append((p,corners.min(axis=0),corners.max(axis=0)))
 report={}
 for label,point in POINTS.items():
  pt=np.array(point);near=[]
  for p,lo,hi in placements:
   distance=float(np.linalg.norm(np.maximum(np.maximum(lo-pt,pt-hi),0)))
   if distance<400:near.append(dict(**p,distance=distance,bounds=[lo.tolist(),hi.tolist()],restored_geometry=p['index'] in restored,collision=owned.get(p['index']),phy=(ROOT/'tools/legion/exported_files/models'/Path(p['model']).stem/(Path(p['model']).stem+'.phy')).exists()))
  near.sort(key=lambda p:(p['distance'],np.linalg.norm(np.subtract(p['origin'],point))))
  report[label]=dict(point=point,nearby=near)
 (P/'user-coordinates-0.1.25.json').write_text(json.dumps(report,indent=2))
 for label,r in report.items():
  print(label,r['point'])
  for p in r['nearby'][:12]:print(p['index'],Path(p['model']).stem,round(p['distance'],1),'origin',p['origin'],'collision',p['collision'] and p['collision'].get('method'),'PHY',p['phy'])
if __name__=='__main__':audit()
