"""Correct the initial sky-water proxy, preserving every gameplay collider."""
import json,os,struct,subprocess
from new_arena_ports import folder,ROOT,WORK
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT
import recover_composite_details as recovery
import numpy as np

def correct():
 out=folder('firing-range');work=out/'source-feature-recovery';path=out/'mp_apex_firing_range.bsp'
 l=read_lumps(path,(2,3,0x2b,0x2c,0x49,0x4f,0x50,0x52,0x51,0x62,0x69,0x7c));buf={k:bytearray(v) for k,v in l.items()};names=[]
 for at in range(0,len(l[2]),36):
  st=struct.unpack_from('<I',l[2],at+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0];names.append(l[0x2b][off:l[0x2b].index(0,off)].decode())
 material=next(i for i,n in enumerate(names) if n.endswith('d_skybox_water_01'))
 sorts=list(struct.iter_unpack('<3hHI',l[0x52]));records=np.frombuffer(l[0x49],DT);ids=[];meshes=[]
 for at in range(0,len(l[0x50]),28):
  m=struct.unpack_from('<I3H6b2h2BHI',l[0x50],at);sort=sorts[m[-2]]
  if sort[0]!=material:continue
  ix=np.frombuffer(l[0x4f],'<u2',m[1]*3,m[0]*2).astype('u4')+sort[-1];ids.extend(records['pi'][ix]);meshes.append(at//28)
 positions=np.frombuffer(buf[3],'<f4').reshape(-1,3);oldz=float(positions[np.unique(ids),2].max());delta=-1600-oldz
 if abs(delta)<.01:return
 positions[np.unique(ids),2]+=delta
 for m in meshes:
  at=m*32+8;struct.pack_into('<f',buf[0x51],at,struct.unpack_from('<f',buf[0x51],at)[0]+delta)
 plan=json.loads((work/'plan.json').read_text());n=plan['water_triangles'];shadow=np.frombuffer(buf[0x7c],'<f4').reshape(-1,3)
 if not np.allclose(shadow[-n*3:,2],oldz,atol=.01):raise ValueError('Unexpected water shadow range')
 shadow[-n*3:,2]+=delta
 src=np.load(out/'scene.npz');a={k:src[k].copy() for k in src.files};src.close();mi=list(a['names']).index('d_skybox_water_01')
 a['triangles'][a['material']==mi,:,2]+=delta;np.savez(out/'scene.npz',**a)
 t=np.fromfile(work/'bake-triangles.bin','<f4').reshape(-1,3,3);t[-n:,:,2]+=delta;t.tofile(work/'bake-triangles.bin')
 j=np.fromfile(work/'bake-jobs.bin',recovery.JOB);j['p'][-n:,:,2]+=delta;j.tofile(work/'bake-jobs.bin')
 direction=-np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
 for exe,args in [(WORK/'tools/bake_arena_environment.exe',[work/'bake-triangles.bin',work/'bake-jobs.bin',work/'sun.bin',2048,2048,1,work/'bake-casters.bin',*direction]),
                  (ROOT/'tools/bake_interior_lighting.exe',[work/'bake-triangles.bin',work/'bake-jobs.bin',out/'fixtures.bin',work/'local.bin',2048,2048,1,work/'bake-casters.bin'])]:
  subprocess.run([str(exe),*map(str,args)],check=True)
 recovery.WORK=work;recovery.patch_lightmaps(buf,j[-plan['added_triangles']:]);tmp=path.with_suffix('.water-height.bsp');compact(path,tmp,buf);os.replace(tmp,path)
 from light_new_arena_ports import glow
 glow('firing-range');(work/'water-height.json').write_text(json.dumps(dict(sea_level=-1600,collision_unchanged=True,
  method='Reanchored non-solid 3D-sky proxy below the weapon-lane floors; original wave shader is not reproduced'),indent=2))
 print('Water proxy below training floors; new receiver charts rebaked',flush=True)

if __name__=='__main__':correct()
