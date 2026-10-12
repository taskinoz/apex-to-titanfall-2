from pathlib import Path
import json,struct,itertools
from stage_prop_geometry import rotation,transform
ps=json.loads(Path('output/phase-runner/static-props.json').read_text());portals=[]
for p in ps:
 if p['index'] not in (16729,16730):continue
 name=Path(p['model']).stem;d=(Path('tools/legion/exported_files/models')/name/(name+'.rmdl')).read_bytes();lo=struct.unpack_from('<3f',d,496);hi=struct.unpack_from('<3f',d,508);v=[transform(c,rotation(p['angles']),p['origin'],p['scale']) for c in itertools.product(*zip(lo,hi))];portals.append(([min(q[k] for q in v)-48 for k in range(3)],[max(q[k] for q in v)+48 for k in range(3)]))
d=Path('output/phase-runner/preview-prop-physics/mp_phase_runner_preview.bsp').read_bytes();o,n=struct.unpack_from('<2I',d,16+0x5c*16);records=list(struct.iter_unpack('<3f2BH3fI',d[o:o+n]));r=json.loads(Path('output/phase-runner/preview-prop-physics/prop-collision-placements.json').read_text());count=0
for p in r['restored']:
 if p['method']!='bounded-rock-hull':continue
 q=records[p['first_brush']];lo=[q[k]-q[k+6] for k in range(3)];hi=[q[k]+q[k+6] for k in range(3)]
 if any(all(hi[k]>=a[k] and lo[k]<=b[k] for k in range(3)) for a,b in portals):count+=1
print('portal boxes',portals,'overlapping approximate rocks',count)
