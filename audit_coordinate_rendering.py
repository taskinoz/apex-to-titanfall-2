"""Locate render meshes at reported positions without changing their draw state."""
import json,struct
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P,POINTS
from repair_preview_index_padding import read_lumps
from read_vg_static import load
from stage_prop_geometry import rotation,transform
def audit():
 l=read_lumps(P/'preview-coordinate-physics/mp_phase_runner_preview.bsp',(3,0x49,0x4f,0x50,0x51,0x52,0x78,0x79));positions=np.frombuffer(l[3],dtype='<f4').reshape(-1,3);pi=np.frombuffer(l[0x49],dtype=np.dtype([('pi','<u4'),('rest','V40')]))['pi'];indices=np.frombuffer(l[0x4f],dtype='<u2');bounds=np.frombuffer(l[0x51],dtype='<f4').reshape(-1,8);refs=np.frombuffer(l[0x78],dtype='<u2');obs=np.frombuffer(l[0x79],dtype='<f4').reshape(-1,8);props={p['index']:p for p in json.loads((P/'static-props.json').read_text())};report=[]
 for index in (12791,116,117,118):
  p=props[index];name=Path(p['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name;sections,_,_=load(base);expected=np.array([[transform(v[:3],rotation(p['angles']),p['origin'],p['scale']) for v in face] for section in sections for face in section]);lo=expected.min(axis=(0,1))-.01;hi=expected.max(axis=(0,1))+.01
  selected=np.flatnonzero(np.all(bounds[:,:3]+bounds[:,4:7]>=lo,axis=1)&np.all(bounds[:,:3]-bounds[:,4:7]<=hi,axis=1));keys=set();near=[]
  def signature(face):return tuple(sorted(tuple(int(x) for x in v) for v in np.rint(face).astype(np.int64)))
  for mi in selected:
   record=l[0x50][mi*28:mi*28+28];first,count=struct.unpack_from('<IH',record);si=struct.unpack_from('<H',record,22)[0];base=struct.unpack_from('<i',l[0x52],si*12+8)[0];tri=positions[pi[base+indices[first:first+count*3].astype(np.int64)]].reshape(-1,3,3);mask=np.all(tri.min(axis=1)>=lo-.1,axis=1)&np.all(tri.max(axis=1)<=hi+.1,axis=1)
   if mask.any():
    at=np.flatnonzero(refs==mi);near.append(dict(mesh=int(mi),in_target_bounds_triangles=int(mask.sum()),visibility_references=at.tolist(),mesh_bounds=bounds[mi].tolist(),object_bounds=obs[at].tolist()))
    keys.update(signature(face) for face in tri[mask])
  matched=sum(signature(face) in keys for face in expected);result=dict(source_prop=index,model=p['model'],source_lod0_triangles=len(expected),position_signature_matches=matched,signature_tolerance='Coordinates rounded to one unit; a coarse membership diagnostic, not exact topology proof',meshes=near,missing_geometry_cause_established=False,camera_angle_visibility_cause_established=False)
  report.append(result);print(index,name,'source triangles',len(expected),'coarse matches',matched,'meshes',len(near),flush=True)
 (P/'coordinate-render-audit-0.1.26.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':audit()
