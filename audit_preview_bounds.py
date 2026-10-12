"""Check actual world vertex positions against every existing mesh bound."""
import json,struct
from pathlib import Path
p=Path('output/phase-runner/preview-compact/mp_phase_runner_preview.bsp')
with p.open('rb') as f:
 h=f.read(2064)
 def lump(i):
  o,n,_,_=struct.unpack_from('<4I',h,16+i*16);f.seek(o);return f.read(n)
 meshes,bounds,sorts,lit,positions=[lump(i) for i in [0x50,0x51,0x52,0x49,3]]
problems=[];checked=0
for mi in range(len(meshes)//28):
 m=meshes[mi*28:(mi+1)*28];start,tri,first,last=struct.unpack_from('<I3H',m);sortidx=struct.unpack_from('<H',m,22)[0];base=struct.unpack_from('<i',sorts,sortidx*12+8)[0];b=struct.unpack_from('<8f',bounds,mi*32);worst=0.
 for vi in range(first,last+1):
  pi=struct.unpack_from('<I',lit,(base+vi)*44)[0];point=struct.unpack_from('<3f',positions,pi*12)
  worst=max(worst,max(abs(point[k]-b[k])-b[k+4] for k in range(3)));checked+=1
 if worst>.1:problems.append(dict(mesh=mi,outside_bounds_by=worst))
r=dict(meshes=len(meshes)//28,vertices_checked=checked,incorrect_bounds=problems,actual_vertex_bounds_verified=not problems)
Path('output/phase-runner/portal-bounds-audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
