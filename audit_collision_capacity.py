"""Find redundant world brushes wholly enclosed by existing rock hulls."""
import json,struct
from pathlib import Path
import numpy as np
from repair_preview_index_padding import read_lumps
from read_prop_physics import read_phy
ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

def audit():
 l=read_lumps(P/'preview-signed-rocks/mp_phase_runner_preview.bsp',(1,0x5c))
 rows=np.array(list(struct.iter_unpack('<3f2BH3fI',l[0x5c])));planes=np.frombuffer(l[1],dtype='<f4').reshape(-1,4)
 owners=json.loads((P/'preview-prop-physics/prop-collision-placements.json').read_text())['restored'];protected=set()
 status=json.loads((P/'preview-signed-rocks/source-build.json').read_text())
 protected.update(p['brush_index'] for p in status['collision_probes'])
 redundant={}
 for owner in owners:
  if owner['method']!='bounded-rock-hull':continue
  rock=owner['first_brush']-424;r=rows[rock];c,e=r[:3],r[6:9];candidate=np.flatnonzero(np.all(abs(rows[:63436,:3]-c)+rows[:63436,6:9]<=e,axis=1))
  q=planes[1+int(r[9]):1+int(r[9])+int(r[4])];n=q[:,:3]
  contained=np.all(rows[candidate,:3]@n.T+rows[candidate,6:9]@abs(n).T<=q[:,3]-0.0005,axis=1)
  for i in candidate[contained]:
   if int(i) not in protected:redundant.setdefault(int(i),rock)
 props=json.loads((P/'static-props.json').read_text());restored=set()
 for path in P.glob('*-geometry/report.json'):restored.update(x['index'] for x in json.loads(path.read_text()).get('restored',[]))
 colliding={o['index'] for o in owners}
 colliding.update(o['index'] for o in json.loads((P/'preview-structure-physics/structure-collision-placements.json').read_text())['restored'])
 targets=[];cache={}
 for p in props:
  if p['index'] not in restored or p['index'] in colliding or p['solid_mode'] not in (2,6,7):continue
  name=Path(p['model']).stem
  if not any(s in name for s in ('crate','ring','pipe','stairs')):continue
  base=ROOT/'tools/legion/exported_files/models'/name/name
  if not base.with_suffix('.phy').exists():continue
  if name not in cache:
   try:cache[name]=len(read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]))
   except Exception as e:cache[name]=str(e)
  targets.append(dict(index=p['index'],model=p['model'],pieces=cache[name],origin=p['origin']))
 report={'redundant_world_brushes':redundant,'available_slots':len(redundant),'targets':targets}
 (P/'collision-capacity-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({'available_slots':len(redundant),'targets':len(targets),'models':cache},indent=2))
if __name__=='__main__':audit()
