"""Restore four source supports/containers and repair isolated chart gutters."""
import json,os,struct,sys,subprocess
from pathlib import Path
import recover_composite_details as recovery
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from repair_composite_source_layout import canon
from compact_preview_bsp import compact
np=recovery.np
ROOT=recovery.ROOT;OUT=recovery.OUT;MAP=recovery.MAP
WORK=OUT/'local-repair';BACKUP=ROOT/'output/repair-backups/20261007-before-local-repair'
recovery.WORK=WORK;recovery.BACKUP=BACKUP
LODS={2914:3,2916:3,5287:3,5288:3}

def write_json(path,value):
 temp=path.with_suffix('.new.json');temp.write_text(json.dumps(value,indent=2));os.replace(temp,path)

def plan():
 WORK.mkdir(exist_ok=True);audit=json.loads((OUT/'asset-audit.json').read_text());source=json.loads((OUT/'source-inventory.json').read_text())['props'];scene=json.loads((OUT/'scene.json').read_text())
 present={p['index'] for p in scene['placements']};parts=[];rows=[]
 for p in source:
  if p['index'] not in LODS:continue
  if p['index'] in present:raise ValueError('Already restored')
  folder=Path(audit['model_paths'][p['model']]);lod=LODS[p['index']];secs,slots,skins=load(folder,lod);skin=skins[min(p['skin'],len(skins)-1)];mat=np.array(rotation(p['angles']));count=0
  for sec,slot in zip(secs,slots):
   t=np.asarray(sec,'<f4').reshape(-1,3,8).copy();t[:,:,:3]=t[:,:,:3]@mat.T*p['scale']+p['origin'];t[:,:,3:6]=t[:,:,3:6]@mat.T;t[:,:,7]=1-t[:,:,7]
   parts.append((skin[slot],t));count+=len(t)
  rows.append(dict(p,folder=str(folder),lod=lod,triangles=count,collision_triangles=0,collision_recovery='Existing source world collision retained',recovery='Complete source VG author LOD3'))
 names=list(dict.fromkeys(n for n,t in parts));tri=np.concatenate([t for n,t in parts]);mi=np.concatenate([np.full(len(t),names.index(n),'i4') for n,t in parts])
 assert len(tri)==910 and len(rows)==4
 np.savez(WORK/'addition.npz',triangles=tri,material=mi,names=np.array(names),collision=np.empty((0,3,3),'f4'))
 write_json(WORK/'plan.json',dict(version='0.6.0',added_props=len(rows),added_triangles=len(tri),placements=rows,policy='Original transforms and complete source LOD3; retain existing world collision, no duplicate collider'))
 print('Restoring four source objects, 910 triangles',flush=True)

def materials():
 recovery.snapshot()
 # The catalogue and status writer also overwrite these text files in place.
 for name in ('source-build.json',):
  path=OUT/name;temp=path.with_suffix('.detached.json');temp.write_bytes(path.read_bytes());os.replace(temp,path)
 recovery.stage_materials()

def orphan():
 if (WORK/'orphan.json').exists():raise ValueError('Orphan already removed')
 scene=json.loads((OUT/'scene.json').read_text());p=next(p for p in scene['placements'] if p['index']==5093);secs,slots,skins=load(p['folder'],p['lod']);mat=np.array(rotation(p['angles']));faces=np.concatenate([np.asarray(s,'<f4').reshape(-1,3,8)[:,:,:3]@mat.T*p['scale']+p['origin'] for s in secs]).astype('<f4')
 lids=(3,0x49,0x4f,0x50,0x52,0x7c,0x7e);l=read_lumps(MAP,lids);pos=np.frombuffer(l[3],'<f4').reshape(-1,3);v=np.frombuffer(l[0x49],recovery.DT);ix=np.frombuffer(l[0x4f],'<u2');indices=bytearray(l[0x4f]);removed=0
 keys=canon(faces)
 for at in range(0,len(l[0x50]),28):
  first,n=struct.unpack_from('<IH',l[0x50],at);sort=struct.unpack_from('<H',l[0x50],at+22)[0];base=struct.unpack_from('<I',l[0x52],sort*12+8)[0];local=ix[first:first+n*3].reshape(-1,3);t=pos[v['pi'][base+local.astype('u4')]];mask=np.isin(canon(t),keys)
  for ti in np.flatnonzero(mask):
   offset=(first+int(ti)*3)*2;i=struct.unpack_from('<H',indices,offset)[0];struct.pack_into('<3H',indices,offset,i,i,i)
  removed+=int(mask.sum())
 shadow=np.frombuffer(l[0x7c],'<f4').reshape(-1,3,3);mask=np.isin(canon(shadow),keys);six=bytearray(l[0x7e])
 for ti in np.flatnonzero(mask):
  at=int(ti)*6;i=struct.unpack_from('<H',six,at)[0];struct.pack_into('<3H',six,at,i,i,i)
 assert removed==24 and mask.sum()==24
 temp=MAP.with_suffix('.orphan.bsp');compact(MAP,temp,{0x4f:indices,0x7e:six});os.replace(temp,MAP)
 # Preserve original caster IDs and clear the orphan for this/future bakes.
 base=WORK/'base-bake';base.mkdir();old=OUT/'screen-repair';os.link(old/'bake-triangles.bin',base/'bake-triangles.bin');t=np.fromfile(base/'bake-triangles.bin','<f4').reshape(-1,3,3);c=np.fromfile(old/'bake-casters.bin','u1');cm=np.isin(canon(t),keys);assert cm.sum()==24;c[cm]=0;c.tofile(base/'bake-casters.bin')
 write_json(WORK/'orphan.json',dict(index=5093,disabled_render_triangles=removed,disabled_shadow_triangles=int(mask.sum()),reason='Light at (-8,2273,66) attached to previously removed wind shield 4924; no wall at its source position',collision='Source non-solid; collision streams unchanged'))
 print('Removed 24 orphan lamp triangles',flush=True)

def append():
 # All four props already have source world collision at these positions.
 # Avoid regenerating any collision grid or adding a duplicate prop hull.
 def retain_collision(buf,col):
  if len(col):raise ValueError('Unexpected extra collider')
 recovery.append_collision=retain_collision
 recovery.append(WORK/'base-bake')
 scene=json.loads((OUT/'scene.json').read_text());scene['placements']=[p for p in scene['placements'] if p['index']!=5093];scene['omitted'].append(dict(index=5093,model='mdl/lamps/industrial_wall_light_on.rmdl',reason='Orphan lamp removed with missing wind shield attachment'));scene['props']=len(scene['placements']);scene['disabled_prop_triangles']=24
 write_json(OUT/'scene.json',scene)

def gutters():
 """Extend valid samples within each chart, never from an adjacent triangle."""
 if (WORK/'gutters.json').exists():raise ValueError('Chart gutters already repaired')
 from scipy.ndimage import distance_transform_edt
 l=read_lumps(MAP,(0x49,0x4f,0x50,0x52,0x62,0x69));v=np.frombuffer(l[0x49],recovery.DT);ix=np.frombuffer(l[0x4f],'<u2');used=np.zeros((4,512,512),bool)
 for at in range(0,len(l[0x50]),28):
  first,n=struct.unpack_from('<IH',l[0x50],at);si=struct.unpack_from('<H',l[0x50],at+22)[0];_,page,_,_,base=struct.unpack_from('<3hHI',l[0x52],si*12);j=v[base+ix[first:first+n*3].reshape(-1,3).astype('u4')];tile=np.floor(j['light'][:,0,:2]*512).astype(int);used[page,tile[:,1],tile[:,0]]=True
 valid=np.array([[1,1,1,0],[1,1,0,0],[1,0,0,0],[0,0,0,0]],bool);nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True);a=bytearray(l[0x62]);b=bytearray(l[0x69]);stride=2048**2*8+1024**2*4;changed={}
 def fix(array,label):
  tiles=array.reshape(512,4,512,4,4).transpose(0,2,1,3,4);sel=tiles[used[page]].copy();new=sel[:,nearest[0],nearest[1]];changed[label]=int(np.any(new!=sel,axis=(1,2,3)).sum());tiles[used[page]]=new
 for page in range(4):
  sky=np.ndarray((2,2048,2048,4),'u1',buffer=a,offset=page*2*2048**2*4)
  for channel in range(2):fix(sky[channel],f'sky{page}_{channel}')
  for channel in range(2):fix(np.ndarray((2048,2048,4),'u1',buffer=b,offset=page*stride+channel*2048**2*4),f'rtl{page}_{channel}')
 np.savez(WORK/'gutter-scope.npz',used=used,valid=valid,nearest=nearest)
 temp=MAP.with_suffix('.gutters.bsp');compact(MAP,temp,{0x62:a,0x69:b});os.replace(temp,MAP)
 write_json(WORK/'gutters.json',dict(charts=int(used.sum()),changed_charts=changed,valid_samples_preserved=True,method='Nearest of six own raster samples, within each 4x4 triangle chart; no geometry, textures, lights, probes or collision changed'))
 print(json.dumps(changed),flush=True)

def walls(small=False):
 """Use spare atlas space for large flat panels at both control entrances."""
 receipt_name='walls-small' if small else 'walls'
 if (WORK/(receipt_name+'.json')).exists():raise ValueError('Wall charts already upgraded')
 from scipy.ndimage import distance_transform_edt
 from light_composite import LOCAL
 ids=(2,3,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x52,0x62,0x69)
 l=read_lumps(MAP,ids);pos=np.frombuffer(l[3],'<f4').reshape(-1,3);norm=np.frombuffer(l[0x1e],'<f4').reshape(-1,3);vertices=np.frombuffer(l[0x49],recovery.DT).copy();indices=np.frombuffer(l[0x4f],'<u2');jobs=[];casters=[];selected=[];vertex_ids=[];cursor=0
 for at in range(0,len(l[0x50]),28):
  first,n=struct.unpack_from('<IH',l[0x50],at);si=struct.unpack_from('<H',l[0x50],at+22)[0];material,page,_,_,base=struct.unpack_from('<3hHI',l[0x52],si*12);vi=base+indices[first:first+n*3].reshape(-1,3).astype('u4');v=vertices[vi];j=np.zeros(n,recovery.JOB);j['p']=pos[v['pi']];j['n']=norm[v['ni']];j['uv']=-10;jobs.append(j)
  st=struct.unpack_from('<I',l[2],material*36+12)[0];off=struct.unpack_from('<I',l[0x2c],st*4)[0];name=l[0x2b][off:l[0x2b].index(0,off)].decode();flag=struct.unpack_from('<I',l[0x50],at+24)[0];cast=np.full(n,not bool(flag&0x10) and not name.endswith('\\sky'),'u1');area=np.linalg.norm(np.cross(j['p'][:,1]-j['p'][:,0],j['p'][:,2]-j['p'][:,0]),axis=1)/2;cast[area<1e-5]=0;casters.append(cast)
  if name.endswith('research_station_painted_metal_01_vc'):
   p=j['p'].mean(1);distance=np.minimum(np.linalg.norm(p-[-1917,631,600],axis=1),np.linalg.norm(p-[1917,631,600],axis=1));mask=(distance<1200)&(abs(j['n'][:,:,2].mean(1))<.1)&((area>100)&(area<=1000) if small else area>1000)
   take=np.flatnonzero(mask);selected.extend((cursor+take).tolist());vertex_ids.extend(vi[take].tolist())
  cursor+=n
 jobs=np.concatenate(jobs);casters=np.concatenate(casters);chosen=np.array(selected,'i4');vi=np.array(vertex_ids,'u4');count=len(chosen)
 assert count==(948 if small else 1302),count
 size=16 if small else 32;start_y=1920 if small else 1248;pad=1.25 if small else 3.25;columns=2048//size;coords=np.array([[pad,pad],[size-pad,pad],[pad,size-pad]],'<f4');origins=np.array([[i%columns*size,start_y+i//columns*size] for i in range(count)],'<f4')
 if origins[:,1].max()+size>2048:raise ValueError('Not enough unused atlas rows')
 uv=origins[:,None,:]+coords;vertices['light'][vi,:2]=uv/2048;jobs['uv'][chosen]=uv;jobs['page'][chosen]=0
 # Allocation starts beyond every existing 4x4 chart on page three.
 scope=np.load(WORK/'gutter-scope.npz');used=scope['used'];scope.close()
 for x,y in origins.astype(int):
  if used[3,y//4:(y+size)//4,x//4:(x+size)//4].any():raise ValueError('New chart overlaps existing lighting')
 jobs['p'].astype('<f4').tofile(WORK/'wall-triangles.bin');jobs.tofile(WORK/'wall-jobs.bin');casters.tofile(WORK/'wall-casters.bin')
 for exe,args in [('bake_phase_environment.exe',[WORK/'wall-triangles.bin',WORK/'wall-jobs.bin',WORK/'wall-sun.bin',2048,2048,1,WORK/'wall-casters.bin']),('bake_interior_lighting.exe',[WORK/'wall-triangles.bin',WORK/'wall-jobs.bin',OUT/'fixtures.bin',WORK/'wall-local.bin',2048,2048,1,WORK/'wall-casters.bin'])]:
  subprocess.run([str(ROOT/'tools'/exe),*map(str,args)],check=True)
 sun=np.fromfile(WORK/'wall-sun.bin','<f4').reshape(2048,2048,5);local=np.fromfile(WORK/'wall-local.bin',LOCAL).reshape(2048,2048);mask=np.fromfile(WORK/'wall-sun.bin.mask','u1').reshape(2048,2048);a=bytearray(l[0x62]);b=bytearray(l[0x69]);sky=np.ndarray((2,2048,2048,4),'u1',buffer=a,offset=3*2*2048**2*4);stride=2048**2*8+1024**2*4;lightids=np.ndarray((2048,2048),'<u4',buffer=b,offset=3*stride);vis=np.ndarray((2048,2048,4),'u1',buffer=b,offset=3*stride+2048**2*4)
 for x,y in origins.astype(int):
  valid=mask[y:y+size,x:x+size].astype(bool);nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True);v=sun[y:y+size,x:x+size][tuple(nearest)];loc=local[y:y+size,x:x+size][tuple(nearest)];ambient=np.array([.09,.10,.12])*(.65+.35*np.maximum(v[...,1,None],0))+loc['fill'];sky[0,y:y+size,x:x+size]=recovery.encode_rgbm(ambient);bent=np.empty((size,size,4),'u1');bent[...,:3]=np.rint(np.clip((v[...,2:5]+1)/2.007874,0,1)*255).astype('u1');bent[...,3]=255;sky[1,y:y+size,x:x+size]=bent;lightids[y:y+size,x:x+size]=loc['ids'];vis[y:y+size,x:x+size]=loc['vis'];vis[y:y+size,x:x+size,0]=np.rint(v[...,0]*255).astype('u1')
 if small:
  s=np.load(WORK/'wall-scope.npz');old={k:s[k] for k in s.files};s.close();vi_all=np.concatenate((old['vertices'],vi));uv_all=np.concatenate((old['uv'],uv));origins_all=np.concatenate((old['origins'],origins));sizes=np.concatenate((old['sizes'],np.full(count,size,'i4')))
 else:vi_all=vi;uv_all=uv;origins_all=origins;sizes=np.full(count,size,'i4')
 np.savez(WORK/'wall-scope.npz',vertices=vi_all,origins=origins_all,uv=uv_all,sizes=sizes)
 temp=MAP.with_suffix('.walls.bsp');compact(MAP,temp,{0x49:vertices.tobytes(),0x62:a,0x69:b});os.replace(temp,MAP)
 write_json(WORK/(receipt_name+'.json'),dict(charts=count,size=size,allocation_page=3,allocation_start_y=start_y,scope='Vertical painted metal panels within 1200 units of both control entrances; '+('area 100..1000' if small else 'area >1000'),receiver_samples_per_triangle=int(valid.sum()),old_charts_preserved=True,lights_and_probes_preserved=True,method='Full-scene sun, sky and local-light ray bake; own-chart gutters; inset receiver samples avoid zero-area vertex-edge rays'))
 print('Rebaked',count,str(size)+'x'+str(size),'wall charts',flush=True)

def wall_pages():
 """Split upgraded receivers into native page-three mesh/material sorts."""
 from repair_native_render_partitions import reorder
 from repair_camera_visibility import build_camera_visibility
 from repair_preview_index_padding import validate_index_padding
 from audit_world_draw_budget import enforce_camera_bypass_budget
 receipt=WORK/'wall-pages.json'
 if receipt.exists():
  s=np.load(WORK/'wall-scope.npz');expected=len(s['vertices']);s.close();prior=json.loads(receipt.read_text())
  if prior.get('processed_receivers',prior['reassigned_triangles'])>=expected:raise ValueError('Wall page partitions already repaired')
 lids=(2,3,0xe,0x49,0x4f,0x50,0x51,0x52,0x64,0x77,0x78,0x79,0x7b)
 b={k:bytearray(v) for k,v in read_lumps(MAP,lids).items()};p=np.frombuffer(b[3],'<f4').reshape(-1,3);v=np.frombuffer(b[0x49],recovery.DT);ix=np.frombuffer(b[0x4f],'<u2');s=np.load(WORK/'wall-scope.npz');wanted=np.zeros(len(v),bool);wanted[s['vertices'].ravel()]=True;s.close();indices=bytearray();meshes=bytearray();bounds=bytearray();sorts=bytearray(b[0x52]);newsorts={};changed=0
 for at in range(0,len(b[0x50]),28):
  first,n=struct.unpack_from('<IH',b[0x50],at);si=struct.unpack_from('<H',b[0x50],at+22)[0];material,page,unknown,span,base=struct.unpack_from('<3hHI',sorts,si*12);local=ix[first:first+n*3].reshape(-1,3);high=wanted[base+local.astype('u4')].all(1)
  for mask,target in ((~high,page),(high,3)):
   raw=local[mask]
   if not len(raw):continue
   targetsort=si
   if target!=page:
    if si not in newsorts:
     newsorts[si]=len(sorts)//12;sorts.extend(struct.pack('<3hHI',material,target,unknown,span,base))
    targetsort=newsorts[si];changed+=len(raw)
   rec=bytearray(b[0x50][at:at+28]);struct.pack_into('<I3H',rec,0,len(indices)//2,len(raw),int(raw.min()),int(raw.max()-raw.min()));struct.pack_into('<H',rec,22,targetsort);meshes.extend(rec);indices.extend(raw.tobytes())
   if len(raw)&1:indices.extend(struct.pack('<3H',*[int(raw[-1,-1])]*3))
   pts=p[v['pi'][base+raw.astype('u4')]].reshape(-1,3);lo=pts.min(0)-.02;hi=pts.max(0)+.02;c=(lo+hi)/2;e=(hi-lo)/2;bounds.extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
 b.update({0x4f:indices,0x50:meshes,0x51:bounds,0x52:sorts});count=len(meshes)//28;struct.pack_into('<2I',b[0xe],24,0,count);b[0x77],b[0x78],b[0x79]=map(bytearray,build_camera_visibility(bounds,np.arange(count,dtype='<u2').tobytes()));struct.pack_into('<3I',b[0x7b],0,count,count,count);b.update(reorder(b)[0]);validate_index_padding(b[0x50],b[0x4f],b[0x52]);temp=MAP.with_suffix('.wall-pages.bsp');compact(MAP,temp,b);proof=enforce_camera_bypass_budget(temp)
 if proof['native_padded_indices']>=3145728*.9:raise ValueError('Native padding budget exceeded')
 os.replace(temp,MAP);write_json(receipt,dict(reassigned_triangles=changed,processed_receivers=int(wanted.sum()//3),draw_budget=proof,reason='Native material sort stores atlas page per mesh; split high-resolution receivers from page-zero geometry'))
 print('Correct page-three wall meshes',changed,'triangles',proof['native_padded_indices'],'indices',flush=True)

if __name__=='__main__':
 {'plan':plan,'materials':materials,'orphan':orphan,'append':append,'gutters':gutters,'walls':walls,'walls-small':lambda:walls(True),'wall-pages':wall_pages}[sys.argv[1]]()
