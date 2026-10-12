from read_prop_physics import read_bvh
from merge_collision import merge
from pathlib import Path
import json
base=Path('output/phase-runner/prop-physics');base.mkdir(exist_ok=True)
for name in ('phase_runner_tunnel','phase_runner_tunnel_02'):
 pieces,s=read_bvh(Path('tools/legion/exported_files/models')/name/(name+'.rmdl'));path=base/(name+'.obj')
 with path.open('w') as stream:
  vi=1
  for fs in pieces:
   for face in fs:
    stream.write('g contents_1\n')
    for p in face:stream.write('v '+' '.join(str(p[k]+(26000,19000,0)[k]) for k in range(3))+'\n')
    stream.write('f '+' '.join(str(vi+i) for i in range(len(face)))+'\n');vi+=len(face)
 fs,count=merge(path);(base/(name+'.json')).write_text(json.dumps(dict(polygons=fs,merged=count,original_polygons=sum(len(p) for p in pieces))))
 print(name,len(fs),count,flush=True)
