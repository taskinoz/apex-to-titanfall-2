import struct,json
from pathlib import Path
base=Path('output/phase-runner/preview-prop-physics');d=(base/'mp_phase_runner_preview.bsp').read_bytes()
def lump(i):o,n=struct.unpack_from('<2I',d,16+16*i);return d[o:o+n]
rs=list(struct.iter_unpack('<3f2BH3fI',lump(0x5c)));planes=list(struct.iter_unpack('<4f',lump(1)));placements=json.loads((base/'prop-collision-placements.json').read_text());owners={i:p for p in placements['restored'] for i in range(p['first_brush'],p['first_brush']+p['brushes'])}
for probe in placements['probes']:
 point=probe['start'];hits=[]
 for i,r in enumerate(rs):
  if all(abs(point[k]-r[k])<=r[k+6]+.001 for k in range(3)) and all(sum(q[k]*point[k] for k in range(3))<=q[3]+.001 for q in planes[1+r[9]:1+r[9]+r[4]]):hits.append(i)
 print(probe['kind'],probe['source_prop'],[(i,owners[i]['model'] if i in owners else 'world') for i in hits][:8])
