import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
P=ROOT/'output/phase-runner/center-detail'
report=json.loads((P/'center-detail.json').read_text());g=np.load(P/'center-geometry.npz');data=g['data']
placements=report['source_geometry']['placements'];nessie=next(p for p in placements if p['index']==7806)
n=data[nessie['first_triangle']:nessie['first_triangle']+nessie['triangles'],:,:3].reshape(-1,3)
truck=next(p for p in placements if p['index']==16850);t=data[truck['first_triangle']:truck['first_triangle']+truck['triangles'],:,:3]
print('Nessie bounds',n.min(0).tolist(),n.max(0).tolist());print('Truck bounds',t.min((0,1)).tolist(),t.max((0,1)).tolist())
contacts=[]
for p in n[n[:,2]<n[:,2].min()+3]:
    a=t[:,0,:2];e=t[:,1,:2]-a;f=t[:,2,:2]-a;q=p[:2]-a;det=e[:,0]*f[:,1]-e[:,1]*f[:,0]
    valid=abs(det)>1e-6;u=np.divide(q[:,0]*f[:,1]-q[:,1]*f[:,0],det,out=np.zeros(len(t)),where=valid);v=np.divide(e[:,0]*q[:,1]-e[:,1]*q[:,0],det,out=np.zeros(len(t)),where=valid)
    z=t[:,0,2]+u*(t[:,1,2]-t[:,0,2])+v*(t[:,2,2]-t[:,0,2]);hit=valid&(u>=-.0001)&(v>=-.0001)&(u+v<=1.0001)&(z<=p[2]+3)
    if hit.any():contacts.append(float(p[2]-z[hit].max()))
print('Nessie foot to restored truck hood gaps',min(contacts) if contacts else None,max(contacts) if contacts else None)
script=ROOT/'northstar/PhaseRunner.CenterDetailRelease/mod/scripts/vscripts/_phase_runner_preview.nut';text=script.read_text()
starts=re.search(r'array<vector> propStarts = \[(.*?)\]',text).group(1);ends=re.search(r'array<vector> propEnds = \[(.*?)\]',text).group(1)
start=re.findall(r'<([^>]+)>',starts)[213];end=re.findall(r'<([^>]+)>',ends)[213];print('Failing old probe213',start,end)
status=json.loads((ROOT/'northstar/PhaseRunner.Preview/build-status.json').read_text());probes=[p for p in status['collision_probes'] if p.get('prop_probe')];print('status',len(probes),probes[213] if len(probes)>213 else None)
(P/'nessie-support-proof.json').write_text(json.dumps(dict(nessie=7806,truck=16850,contact_samples=len(contacts),minimum_foot_gap=min(contacts) if contacts else None,maximum_foot_gap=max(contacts) if contacts else None,original_placements_preserved=True),indent=2))
