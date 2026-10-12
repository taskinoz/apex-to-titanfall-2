import json,collections,struct
from pathlib import Path
from read_prop_physics import read_phy
restored=set()
for a in Path('output/phase-runner').glob('*-geometry/report.json'):restored.update(v['index'] for v in json.loads(a.read_text()).get('restored',[]))
c=collections.Counter()
for p in json.loads(Path('output/phase-runner/static-props.json').read_text()):
 if p['index'] in restored and p['solid_mode'] in (2,6,7):c[p['model']]+=1
for model,n in c.items():
 name=Path(model).stem;b=Path('tools/legion/exported_files/models')/name/name
 if ('/rocks/' in model or 'pipe' in name) and b.with_suffix('.phy').exists():
  try:
   f=read_phy(b.with_suffix('.phy'),struct.unpack_from('<I',b.with_suffix('.rmdl').read_bytes(),8)[0]);print(name,n,len(f),n*len(f))
  except Exception as e:print(name,repr(e))
