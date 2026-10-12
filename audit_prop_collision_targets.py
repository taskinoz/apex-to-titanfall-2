import json,struct,collections
from pathlib import Path
p=Path('output/phase-runner/preview-draw-restored/mp_phase_runner_preview.bsp');d=p.read_bytes()
def l(i):
 o,n=struct.unpack_from('<2I',d,16+i*16);return d[o:o+n]
b=l(0x5c);planes=l(1);keys=set()
for r in struct.iter_unpack('<3f2BH3fI',b):
 key=r[:3]+r[6:9]+tuple(sorted(tuple(round(x,4) for x in q) for q in struct.iter_unpack('<4f',planes[16+r[9]*16:16+(r[9]+r[4])*16])))
 keys.add(key)
print('Original brushes / unique',len(b)//32,len(keys))
restored=set()
for a in Path('output/phase-runner').glob('*-geometry/report.json'):
 restored.update(v['index'] for v in json.loads(a.read_text()).get('restored',[]))
props=json.loads(Path('output/phase-runner/static-props.json').read_text());groups=collections.Counter()
for v in props:
 if v['index'] not in restored or v['solid_mode'] not in (2,6,7):continue
 name=Path(v['model']).stem
 if '/rocks/' not in v['model'] and not any(w in name for w in ('pipe','tunnel')):continue
 phy=Path('tools/legion/exported_files/models')/name/(name+'.phy')
 groups[(name,phy.exists())]+=1
print(json.dumps([dict(model=k[0],phy=k[1],placements=n) for k,n in groups.items()],indent=2))
