"""Audit every existing brush and every rendered solid source-model placement."""
import collections,json,struct
from pathlib import Path
import numpy as np
from audit_user_coordinates import ROOT,P
from repair_preview_index_padding import read_lumps
from read_prop_physics import read_phy,read_bvh

def audit():
 src=P/'preview-coordinate-physics/mp_phase_runner_preview.bsp';l=read_lumps(src,(1,0x55,0x56,0x57,0x59,0x5b,0x5c,0x5d,0x5e,0x5f));rows=np.array(list(struct.iter_unpack('<3f2BH3fI',l[0x5c])));q=np.frombuffer(l[1],dtype='<f4').reshape(-1,4);fail=[];no_bevel=[]
 if not np.isfinite(rows).all() or not np.isfinite(q).all():fail.append('Nonfinite brush/plane data')
 for i,r in enumerate(rows):
  count=int(r[4]);original=int(r[3]);offset=int(r[9]);first=6*int(r[5])+offset;cuts=q[1+offset:1+offset+count];flags=np.frombuffer(l[0x5e][first*2:(first+6+count)*2],dtype='<u2')
  if int(r[5])!=i or original>count or len(cuts)!=count or len(flags)!=6+count or np.any(r[6:9]<=0):fail.append(dict(brush=i,reason='Invalid brush extent/index/count'))
  if count and (np.any(abs(np.linalg.norm(cuts[:,:3],axis=1)-1)>.002) or np.any(flags[6:6+original]&0x4000) or np.any((flags[6+original:]&0x4000)==0)):fail.append(dict(brush=i,reason='Invalid plane normals or bevel flags'))
  if count and original==count:no_bevel.append(i)
 primitive=np.frombuffer(l[0x59],dtype='<u4');ids=(primitive>>8)&65535
 if len(set(ids.tolist()))!=len(rows) or np.any(primitive>>24):fail.append('Collision grid does not cover every brush exactly by valid primitives')
 restored=set();owned={};methods=collections.Counter()
 for path in P.glob('*-geometry/report.json'):restored.update(r['index'] for r in json.loads(path.read_text()).get('restored',[]))
 for folder,file,key in [('preview-prop-physics','prop-collision-placements.json','restored'),('preview-structure-physics','structure-collision-placements.json','restored'),('preview-prop-coverage','prop-coverage-repair.json','added_props'),('preview-coordinate-physics','coordinate-collision-repair.json','added_props')]:
  for owner in json.loads((P/folder/file).read_text())[key]:owned[owner['index']]=owner;methods[owner['method']]+=1
 props=json.loads((P/'static-props.json').read_text());models={};missing=[];solid=[];non_solid=0
 for prop in props:
  if prop['index'] not in restored:continue
  if prop['solid_mode'] not in (2,6,7):non_solid+=1;continue
  solid.append(prop);name=Path(prop['model']).stem;base=ROOT/'tools/legion/exported_files/models'/name/name
  if name not in models:
   try:
    if base.with_suffix('.phy').exists():pieces=read_phy(base.with_suffix('.phy'),struct.unpack_from('<I',base.with_suffix('.rmdl').read_bytes(),8)[0]);method='IRPS'
    else:pieces,stats=read_bvh(base.with_suffix('.rmdl'));method='BVH'
    models[name]=dict(method=method,pieces=len(pieces),faces=sum(len(p) for p in pieces),available=bool(pieces))
   except Exception as e:models[name]=dict(available=False,error=str(e))
  if prop['index'] not in owned:missing.append(dict(index=prop['index'],model=prop['model'],physics=models[name]))
 report=dict(source=str(src),brushes=len(rows),brush_errors=fail,brushes_without_bevels=no_bevel,rendered_source_placements=len(restored),source_solid_placements=len(solid),intentionally_nonsolid_placements=non_solid,owned_prop_placements=len(owned),collision_methods=dict(methods),missing_prop_placements=missing,models=models,complete=False)
 (P/'all-collision-audit-0.1.26.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(dict(brushes=len(rows),brush_errors=fail,no_bevel=len(no_bevel),rendered=len(restored),solid=len(solid),owned=len(owned),missing=len(missing),missing_models=dict(collections.Counter(Path(p['model']).stem for p in missing)),methods=dict(methods)),indent=2),flush=True)
 native=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',(3,0x42,0x44,0x45,0x60,0x61));heads=list(struct.iter_unpack('<6h4i4f',native[0x45]));print('Native tricoll sizes:',{hex(k):len(v) for k,v in native.items()})
 for i,h in [(i,h) for i,h in enumerate(heads) if h[4]<=3][:6]:
  words=list(struct.unpack_from('<'+'I'*h[4],native[0x42],h[7]*4));tris=[]
  for w in words:
   a=w&1023;b=a+((w>>10)&127);c=a+((w>>17)&127);tris.append([struct.unpack_from('<3f',native[3],(h[6]+j)*12) for j in (a,b,c)])
  print('Native small tricoll',i,'header',h,'triangle words',[hex(w) for w in words],'geometry',tris,'nodes',native[0x44][h[8]*16:h[8]*16+32].hex(),'bevel starts',native[0x60][h[7]*2:(h[7]+h[4])*2].hex())
if __name__=='__main__':audit()
