"""Replace broad material batches with spatial draw sections; keep exact vertices."""
import json,math,mmap,struct,shutil,time
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import build_visibility,validate_visibility
ROOT=Path(__file__).resolve().parent

def partition(centers,ids,limit=512):
 import numpy as np
 if len(ids)<=limit:return [ids]
 axis=int(np.argmax(np.ptp(centers[ids],axis=0)))
 order=ids[np.argsort(centers[ids,axis],kind='stable')];middle=len(order)//2
 return partition(centers,order[:middle],limit)+partition(centers,order[middle:],limit)

def build():
 import numpy as np
 source=ROOT/'output/phase-runner/preview-draw-restored/mp_phase_runner_preview.bsp';out=ROOT/'output/phase-runner/preview-spatial/mp_phase_runner_preview.bsp'
 start=time.monotonic();meshes=bytearray();bounds=bytearray();indices=bytearray();sorts=bytearray();before=[];after=[];proof=[]
 with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as d:
  h=[struct.unpack_from('<4I',d,16+16*i) for i in range(128)]
  def lump(i):o,n,_,_=h[i];return d[o:o+n]
  positions=np.frombuffer(lump(3),dtype='<f4').reshape(-1,3);lit_pi=np.frombuffer(lump(0x49),dtype=np.dtype([('pi','<u4'),('rest','V40')]))['pi'];all_indices=np.frombuffer(lump(0x4f),dtype='<u2');old=lump(0x50);oldsort=lump(0x52);oldbounds=lump(0x51)
  for mi in range(len(old)//28):
   record=old[mi*28:mi*28+28];first,count=struct.unpack_from('<IH',record);si=struct.unpack_from('<H',record,22)[0];sort=oldsort[si*12:si*12+12];base=struct.unpack_from('<i',sort,8)[0]
   tris=all_indices[first:first+count*3].reshape(-1,3);corners=positions[lit_pi[base+tris.astype("<u4")]];centers=corners.mean(axis=1)
   chunks=partition(centers,np.arange(count));seen=np.concatenate(chunks)
   if not np.array_equal(np.sort(seen),np.arange(count)):raise ValueError('Spatial partition changes triangle membership')
   # Existing local indices and native sort base preserve every 44-byte attribute record.
   before.append(struct.unpack_from('<f',oldbounds,mi*32+12)[0]);begin=len(meshes)//28
   for ids in chunks:
    selected=tris[ids];p=corners[ids].reshape(-1,3);low=p.min(axis=0).astype(float)-.02;high=p.max(axis=0).astype(float)+.02;c=(low+high)*.5;e=(high-low)*.5;radius=float(np.linalg.norm(e))+.02
    mesh=bytearray(record);struct.pack_into('<IH',mesh,0,len(indices)//2,len(ids));struct.pack_into('<H',mesh,22,si)
    indices.extend(selected.astype('<u2').tobytes());meshes.extend(mesh);bounds.extend(struct.pack('<8f',*c,radius,*e,0.));after.append(radius)
   proof.append(dict(source_mesh=mi,first_new_mesh=begin,sections=len(chunks),triangles=count))
   if mi%100==0:print(f'Spatially partitioned {mi+1}/{len(old)//28} meshes',flush=True)
  sorts=bytearray(oldsort)
  world=bytearray(lump(0x0e));total=len(meshes)//28;struct.pack_into('<I',world,28,total);level=bytearray(lump(0x7b));struct.pack_into('<3I',level,0,total,total,total)
 nodes,refs,objects=build_visibility(bounds,leaf_size=16);vis=validate_visibility(nodes,refs,objects,bounds)
 compact_report=compact(source,out,{0x50:meshes,0x51:bounds,0x52:sorts,0x4f:indices,0x0e:world,0x7b:level,0x77:nodes,0x78:refs,0x79:objects})
 status=json.loads(source.with_name('source-build.json').read_text());status['spatial_draw_sections']=dict(before_meshes=len(old)//28,after_meshes=total,max_triangles_per_section=512,
  exact_triangle_membership_verified=True,vertex_buffers_materials_and_physics_byte_unchanged=True,
  material_sort_records_shared=True,material_sorts=len(sorts)//12,
  median_radius_before=float(np.median(before)),median_radius_after=float(np.median(after)),visibility=vis,visual_verified=False,elapsed_seconds=time.monotonic()-start)
 status['render_repair']['world_meshes']=total;status['visibility_rebuild']=vis;status['final_compaction']=compact_report
 out.with_name('source-build.json').write_text(json.dumps(status,indent=2));out.with_name('partition-proof.json').write_text(json.dumps(proof,indent=2))
 for p in source.parent.glob(source.stem+'_*.ent'):shutil.copy2(p,out.parent/p.name)
 shutil.copy2(source.with_suffix('.stbsp'),out.with_suffix('.stbsp'));print(json.dumps(status['spatial_draw_sections'],indent=2))
if __name__=='__main__':build()

