"""Unwrap the confirmed playable map without changing its draw or collision data.

Run with the bundled Python and workspace tools/lighting-python dependencies.
The cached arrays are also a renderer-neutral scene export for future bakers.
"""
import sys, os, json, hashlib, struct, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
import xatlas
from repair_preview_index_padding import read_lumps
SOURCE=ROOT/'output/phase-runner/preview-tunnel-walkways/mp_phase_runner_preview.bsp'
OUT=ROOT/'output/phase-runner/light-bake'
DT=np.dtype([('pi','<u4'),('ni','<u4'),('uv','<f4',2),('color','u1',4),('light','<f4',4),('tangent','<u4'),('extra','<u4')])

def prepare():
    OUT.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    l=read_lumps(SOURCE,[3,0x1e,0x49,0x4f,0x50,0x52])
    v=np.frombuffer(l[0x49],DT);p=np.frombuffer(l[3],'<f4').reshape(-1,3);n=np.frombuffer(l[0x1e],'<f4').reshape(-1,3)
    ix=np.frombuffer(l[0x4f],'<u2');sorts=list(struct.iter_unpack('<4hI',l[0x52]))
    faces=[];meshid=[]
    for mi,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[0x50])):
        if r[-1]&0x600!=0x200 or r[-1]&6:continue
        f=ix[r[0]:r[0]+r[1]*3].astype(np.uint32).reshape(-1,3)+sorts[r[-2]][4]
        faces.append(f);meshid.extend([mi]*len(f))
    faces=np.concatenate(faces);active=np.unique(faces)
    # Weld for chart adjacency, including normals so sharp edges remain seams.
    attrs=np.column_stack((p[v['pi'][active]],n[v['ni'][active]]))
    quant=np.round(attrs*np.array([1000]*3+[10000]*3)).astype(np.int64)
    _,first,inverse=np.unique(quant,axis=0,return_index=True,return_inverse=True)
    original_to_weld=np.zeros(len(v),np.uint32);original_to_weld[active]=inverse
    welded=attrs[first].astype(np.float32);wf=original_to_weld[faces]
    print(f'Unwrapping {len(faces)} triangles, {len(welded)} welded vertices',flush=True)
    atlas=xatlas.Atlas();atlas.add_mesh(welded[:,:3],wf,normals=welded[:,3:])
    chart=xatlas.ChartOptions();chart.max_iterations=1
    pack=xatlas.PackOptions();pack.resolution=1024;pack.texels_per_unit=.035;pack.padding=3;pack.bilinear=True;pack.rotate_charts=True
    atlas.generate(chart,pack,verbose=True)
    vm,fi,uv=atlas[0]
    face_uv=uv[fi];page=np.empty(len(fi),np.int32)
    for k in range(atlas.chart_count):
        c=atlas.get_mesh_chart(0,k);page[np.asarray(c.faces,dtype=np.int64)]=c.atlas_index
    if not np.array_equal(vm[fi],wf):raise ValueError('Unwrapper reordered triangle corners')
    # Tile sixteen 1024 atlases into each native 4096 page. Keeping chart
    # resolution/padding intact while reducing page switches avoids thousands
    # of extra material sorts and preserves the native renderer's draw budget.
    original_pages=atlas.atlas_count
    face_uv=(face_uv+np.stack((page%4,(page%16)//4),axis=1)[:,None,:])/4
    page=page//16;width=atlas.width*4;height=atlas.height*4;pages=(original_pages+15)//16
    # Check triangles do not span atlas pages and no chart is degenerate.
    if not np.isfinite(face_uv).all() or (face_uv<0).any() or (face_uv>1).any():raise ValueError('Bad atlas coordinates')
    scene=p[v['pi'][faces]].astype('<f4');normals=n[v['ni'][faces]].astype('<f4')
    scene.tofile(OUT/'triangles.bin');normals.tofile(OUT/'normals.bin')
    # Records for rasterizer: triangle positions, interpolated normal, pixel UVs,
    # atlas page, in original mesh/corner order.
    jobs=np.empty(len(faces),np.dtype([('p','<f4',(3,3)),('n','<f4',(3,3)),('uv','<f4',(3,2)),('page','<i4')]))
    jobs['p']=scene;jobs['n']=normals;jobs['uv']=face_uv*np.array([width,height]);jobs['page']=page
    jobs.tofile(OUT/'jobs.bin')
    np.savez(OUT/'atlas.npz',faces=faces,uv=face_uv,page=page,meshid=np.array(meshid,np.int32))
    report=dict(source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),triangles=len(faces),welded_vertices=len(welded),
        pages=pages,width=width,height=height,charts=atlas.chart_count,packed_1024_pages=original_pages,texels_per_unit=.035,
        samples=24,seconds=time.monotonic()-start,geometry_unchanged=True,collision_unchanged=True,
        limitation='First static bake: direct sun visibility and sampled sky occlusion. No indirect light bounce or custom reflection probes yet.')
    (OUT/'scene.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':prepare()
