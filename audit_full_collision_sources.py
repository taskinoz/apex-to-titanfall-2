"""Check every installed source-model collider against its recovered physics."""
import json,struct,collections
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P
from read_prop_physics import read_phy,read_bvh,convex_planes
from repair_preview_index_padding import read_lumps
from stage_prop_geometry import rotation,load_mesh
from rebuild_complete_collision import triangles

def audit():
 src=P/'preview-full-collision/mp_phase_runner_preview.bsp';l=read_lumps(src,(1,3,0x45,0x5c));report=json.loads(src.with_name('collision-ownership.json').read_text());rows=list(struct.iter_unpack('<3f2BH3fI',l[0x5c]));q=np.frombuffer(l[1],dtype='<f4').reshape(-1,4);v=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);heads=list(struct.iter_unpack('<6h4i4f',l[0x45]));props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};cache={};errors=[];checked=collections.Counter()
 for owner in report['owners']:
  p=props[owner['index']];name=Path(p['model']).stem;method=owner['method'];base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in cache:
   if method=='IRPS':pieces=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]);cache[name]=[convex_planes(piece) for piece in pieces]
   elif method=='BVH':pieces,_=read_bvh(base.with_suffix('.rmdl'));cache[name]=triangles([f for piece in pieces for f in piece])
   else:mesh,_=load_mesh(p['source_qc']);cache[name]=np.array([[v[:3] for v in vs] for _,vs in mesh],dtype='<f4')
  matrix=np.array(rotation(p['angles']));origin=np.array(p['origin'])
  if method=='IRPS':
   if len(cache[name])!=owner['brushes']:errors.append((owner['index'],'Lost convex pieces'))
   for j,(points,planes) in enumerate(cache[name]):
    r=rows[owner['first_brush']+j];pts=np.array(points)@matrix.T*p['scale']+origin;qs=np.array(planes);normals=qs[:,:3]@matrix.T;distances=qs[:,3]*p['scale']+normals@origin;expected=np.column_stack((normals,distances));expected=expected[~np.any(abs(abs(expected[:,:3])-1)<1e-7,axis=1)];actual=q[1+r[9]:1+r[9]+r[4]]
    if len(expected)!=r[3] or not np.allclose(expected,actual[:r[3]],atol=.003,rtol=1e-7):errors.append((owner['index'],j,'Original planes changed'))
    if np.any(pts<np.array(r[:3])-r[6:9]-.003) or np.any(pts>np.array(r[:3])+r[6:9]+.003) or np.any(pts@actual[:,:3].T>actual[:,3]+.09):errors.append((owner['index'],j,'Source vertex removed'))
    checked['convex_pieces']+=1
  else:
   expected=(cache[name]@matrix.T*p['scale']+origin).astype('<f4');normals=np.cross(expected[:,1]-expected[:,0],expected[:,2]-expected[:,0]);expected=expected[np.linalg.norm(normals,axis=1)>1e-5]
   selected=heads[owner['first_header']:owner['first_header']+owner['headers']];first=selected[0][6];count=sum(h[4] for h in selected);actual=v[first:first+count*3].reshape(-1,3,3)
   # Preserve each triangle's vertex order; canonicalize only triangle order.
   def ordered(t):
    flat=t.reshape(-1,9);return t[np.lexsort(tuple(flat[:,k] for k in range(8,-1,-1)))]
   if actual.shape!=expected.shape or not np.allclose(ordered(actual),ordered(expected),atol=.003,rtol=1e-7):errors.append((owner['index'],'Triangle geometry differs from source physics'))
   checked['model_triangles']+=count
  checked['placements']+=1
 proof=dict(all_source_model_physics_verified=not errors,checked=dict(checked),errors=errors,visual_fallback_placements=report['summary']['visual_fallback_placements'])
 src.with_name('source-physics-audit.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2));
 if errors:raise ValueError('Source physics audit failed')
if __name__=='__main__':audit()
