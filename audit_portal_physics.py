from read_prop_physics import read_bvh,plane
from pathlib import Path
import math
for name in ('phase_runner_tunnel','phase_runner_tunnel_02'):
 ps,s=read_bvh(Path('tools/legion/exported_files/models')/name/(name+'.rmdl'));points=[p for fs in ps for f in fs for p in f]
 print(name,'bounds',[min(p[k] for p in points) for k in range(3)],[max(p[k] for p in points) for k in range(3)])
 areas=[]
 for fs in ps:
  for f in fs:
   q=plane(f)
   if q:
    from build_preview_source import cross,subtract
    area=math.sqrt(sum(v*v for v in cross(subtract(f[1],f[0]),subtract(f[2],f[0]))))*.5
    areas.append((area,f,q))
 print('area top 5',[(a,sum(v[2] for v in f)/len(f),q) for a,f,q in sorted(areas,reverse=True)[:5]])
 print('top400 area fraction',sum(a[0] for a in sorted(areas,reverse=True)[:400])/sum(a[0] for a in areas))
