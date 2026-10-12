"""Plan source-physics coverage at reported gaps before allocating native brushes."""
import collections,json,struct
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P,POINTS
from read_prop_physics import read_phy,plane
from extend_prop_collision import area,slab
from stage_prop_geometry import rotation,transform
def plan():
 props=json.loads((P/'static-props.json').read_text());owned=set();restored=set();cache={};targets=[]
 for path in P.glob('*-geometry/report.json'):restored.update(r['index'] for r in json.loads(path.read_text()).get('restored',[]))
 for folder,file in [('preview-prop-physics','prop-collision-placements.json'),('preview-structure-physics','structure-collision-placements.json'),('preview-prop-coverage','prop-coverage-repair.json')]:
  d=json.loads((P/folder/file).read_text());owned.update(r['index'] for r in d.get('restored',d.get('added_props',[])))
 for p in props:
  name=Path(p['model']).stem
  if p['index'] in owned or p['index'] not in restored or p['solid_mode'] not in (2,6,7) or not any(w in name for w in ('stair','container','crate','box','railing','guard_rail')):continue
  base=ROOT/'tools/legion/exported_files/models'/name/name
  if not base.with_suffix('.phy').exists():continue
  if name not in cache:
   try:cache[name]=len(read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]))
   except ValueError as e:cache[name]=str(e)
  if isinstance(cache[name],int):targets.append(dict(index=p['index'],model=p['model'],pieces=cache[name]))
 portals=[]
 for p in [p for p in props if p['index'] in (16729,16730)]:
  name=Path(p['model']).stem;fs=json.loads((P/'prop-physics'/(name+'.json')).read_text())['polygons'];fs.sort(key=area,reverse=True);walk=[];matrix=rotation(p['angles'])
  for rank,face in enumerate(fs):
   placed=[transform(v,matrix,p['origin'],p['scale']) for v in face];q=plane(placed)
   if q is not None and abs(q[2])>=.7 and slab(placed) is not None:walk.append(rank)
  oldwalk=[i for i in walk if i>=259][:64];remaining=[i for i in walk if i>=259 and i not in oldwalk]
  distances={}
  for label in ('pipe','pipe_fall','pipe_section'):
   pt=np.array(POINTS[label]);nearest=[]
   for rank in remaining:
    pts=np.array([transform(v,matrix,p['origin'],p['scale']) for v in fs[rank]])
    lo,hi=pts.min(axis=0),pts.max(axis=0);dist=float(np.linalg.norm(np.maximum(np.maximum(lo-pt,pt-hi),0)))
    nearest.append((dist,rank,pts.mean(axis=0).tolist()))
   distances[label]=sorted(nearest)[:5]
  portals.append(dict(index=p['index'],total_polygons=len(fs),walkable=len(walk),remaining_walkable_ranks=remaining,nearest=distances))
 report=dict(targets=targets,model_pieces=cache,total_convex_brushes=sum(p['pieces'] for p in targets),portals=portals)
 (P/'coordinate-collision-plan.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(dict(target_placements=len(targets),total_convex_brushes=report['total_convex_brushes'],models=cache,portals=[{k:v for k,v in p.items() if k!='remaining_walkable_ranks'} for p in portals]),indent=2))
if __name__=='__main__':plan()
