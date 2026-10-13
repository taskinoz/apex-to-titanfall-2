"""Preserve tested RTL slots and bake omitted source fixtures into surfaces and character SH."""
import json,math,os,struct,subprocess,sys
from new_arena_ports import CONFIG,ROOT,WORK,folder
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from apply_baked_lighting import encode_rgbm

FIXTURE=np.dtype([('p','<f4',3),('radius','<f4'),('colour','<f4',3),('shadow','<f4'),
                  ('direction','<f4',3),('inner','<f4'),('outer','<f4'),('spot','<f4')])

def bake(ident):
 out=folder(ident);receipt=out/'source-fill.json'
 if receipt.exists():raise ValueError('Already applied; restore the backed-up BSP before rebaking')
 source=out/(CONFIG[ident]['target']+'.bsp');scene=json.loads((out/'scene.json').read_text())
 selected={e['source_entity'] for e in json.loads((out/'interior-lights.json').read_text())['lights']}
 low,high=np.asarray(CONFIG[ident]['bounds']);offset=np.asarray(CONFIG[ident]['offset']);rows=[]
 for i,e in enumerate(scene['source_entities']):
  if e['classname'] not in ('light','light_spot') or i in selected:continue
  p=np.asarray(list(map(float,e['origin'].split())))+offset
  if not np.all((p>=low)&(p<=high)):continue
  v=list(map(float,e.get('_light','255 255 255 300').split()));colour=(np.asarray(v[:3])/255)**2.2*min(4,max(.02,v[3]/1500))
  radius=min(4000,max(64,float(e.get('_zero_percent_distance',e.get('_distance','800')))))
  pitch,yaw=[math.radians(v) for v in list(map(float,e.get('angles','0 0 0').split()))[:2]]
  direction=[math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),-math.sin(pitch)]
  rows.append(dict(source_entity=i,origin=p.tolist(),colour=colour.tolist(),radius=radius,
    direction=direction,inner=math.cos(math.radians(float(e.get('_inner_cone','20')))),
    outer=math.cos(math.radians(float(e.get('_cone','45')))),spot=e['classname']=='light_spot',shadow=e.get('shadow','0')!='0'))
 fixtures=np.zeros(len(rows),FIXTURE)
 for i,r in enumerate(rows):fixtures[i]=(r['origin'],r['radius'],r['colour'],r['shadow'],r['direction'],r['inner'],r['outer'],r['spot'])
 fixtures.tofile(out/'source-fill-fixtures.bin');cfg=json.loads((out/'bake.json').read_text());w,h,pages=cfg['width'],cfg['height'],cfg['pages']
 probes=np.fromfile(out/'probe-positions.bin','<f4').reshape(-1,3)
 with (out/'source-fill.log').open('w') as log:
  subprocess.run([str(WORK/'tools/bake_source_light_fill.exe'),str(out/'bake-triangles.bin'),str(out/'bake-jobs.bin'),
    str(out/'source-fill-fixtures.bin'),str(out/'source-fill.bin'),str(w),str(h),str(pages),str(out/'bake-casters.bin'),str(out/'probe-positions.bin')],stdout=log,stderr=log,check=True)
 print((out/'source-fill.log').read_text(),flush=True)
 fill=np.memmap(out/'source-fill.bin','<f4','r',shape=(pages*w*h+len(probes),3));l=read_lumps(source,(0x62,0x65))
 sky=np.frombuffer(l[0x62],'u1').reshape(pages,2,h,w,4).copy();valid=np.memmap(out/'sun.bin.mask','u1','r',shape=(pages,h,w))
 for page in range(pages):
  add=np.asarray(fill[page*w*h:(page+1)*w*h]).reshape(h,w,3).copy()
  # Fill padding within each individual triangle chart, never across a seam.
  for y in range(0,h,4):
   for x in range(0,w,4):
    mask=valid[page,y:y+4,x:x+4].astype(bool)
    if not mask.any():continue
    ys,xs=np.nonzero(mask)
    for yy,xx in zip(*np.nonzero(~mask)):
     k=int(((ys-yy)**2+(xs-xx)**2).argmin());add[y+yy,x+xx]=add[y+ys[k],x+xs[k]]
  rgb=sky[page,0,:,:,:3]/255*(sky[page,0,:,:,3,None]/255*3.984375+.015625)
  sky[page,0]=encode_rgbm(rgb+add)
 records=np.frombuffer(l[0x65],np.dtype([('sh','<i2',16),('rest','V16')])).copy()
 for channel in range(3):
  at=channel*4+3;records['sh'][:,at]=np.rint(np.clip(records['sh'][:,at].astype('f4')+fill[pages*w*h:,channel]*8192,-32768,32767)).astype('<i2')
 target=source.with_suffix('.source-fill.bsp');compact(source,target,{0x62:sky.tobytes(),0x65:records.tobytes()});os.replace(target,source)
 receipt.write_text(json.dumps(dict(native_rtl_fixtures=len(selected),additional_baked_fixtures=len(rows),fixtures=rows,
  method='Shadow-aware diffuse bake with source spot cones; character SH constant terms. Native RTL slots unchanged.',
  limitation='Additional fixtures have static diffuse contributions, not independent native specular light slots'),indent=2))
 print(ident,'additional source lights',len(rows),flush=True)

if __name__=='__main__':bake(sys.argv[1])
