"""Restore source clips and suppress temporary arena covers without rebaking."""
import collections,json,os,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from native_triangle_collision import encode,collision_grid
OUT=ROOT/'output/composite';MAP=OUT/'mp_arena_composite.bsp'

def source_clip_kind(points,contents):
    a=np.asarray(points);lo=a.min(0);hi=a.max(0)
    if contents==0xb10000 and lo[1]>=5000 and lo[2]>=1095 and np.max(abs(a[:,0]))<4300:return 'upper_platform_exclusion'
    if contents!=0xa30000:return None
    if np.all((a[:,0]>=-385)&(a[:,0]<=374)&(a[:,1]>=5640)&(a[:,1]<=5648)&(a[:,2]>=-62)&(a[:,2]<=273)):return 'north_room_boundary'
    for sign in (1,-1):
        xy=a[:,:2].copy();xy[:,0]*=sign
        anchor=np.array([1339.6901855,2926.0852051]);edge=np.array([1924.645752,2475.912598])-anchor
        normal=np.array([-edge[1],edge[0]])/np.linalg.norm(edge)
        if np.all(abs((xy-anchor)@normal)<4.0) and lo[1]>=2470 and hi[1]<=2930 and lo[2]>=-218 and hi[2]<=118:return 'diagonal_room_boundary'

def canon(tris):
    a=np.ascontiguousarray(tris,dtype='<f4').reshape(-1,3,3).view('V12').reshape(-1,3).copy()
    a.sort(axis=1)
    return a.reshape(-1).view('V36')

def repair():
    receipt=OUT/'source-layout-repair.json'
    if receipt.exists():raise ValueError('Source-layout repair already recorded; restore its backup before reapplying')
    backup=ROOT/'output/repair-backups/20261007-source-layout';backup.mkdir(parents=True,exist_ok=True)
    for name in ('mp_arena_composite.bsp','physics.npz','physics.json'):
        dest=backup/name
        if dest.exists():raise ValueError('Backup already exists: '+name)
        os.link(OUT/name,dest)
    lumps=read_lumps(MAP,(1,2,3,0x2b,0x2c,0x42,0x44,0x45,0x49,0x4f,0x50,0x51,0x52,0x5c,0x5d,0x5e,0x5f,0x7c,0x7e,0x7f))
    positions=np.frombuffer(lumps[3],'<f4').reshape(-1,3);words=np.frombuffer(lumps[0x42],'<u4');groups=[]
    for h in struct.iter_unpack('<6h4i4f',lumps[0x45]):
        w=words[h[7]:h[7]+h[4]];ix=w&1023
        groups.append(positions[h[6]+np.stack((ix,ix+(w>>10&127),ix+(w>>17&127)),1)])
    restored=collections.Counter();faces=[];points=[];contents=0
    for line in (OUT/'collision/world-collision-regular.obj').open():
        if line.startswith('g '):points=[];contents=int(line.split()[1].split('_')[1],16)
        elif line.startswith('v '):points.append(list(map(float,line.split()[1:4])))
        elif line.startswith('f '):
            reason=source_clip_kind(points,contents)
            if reason:
                restored[reason]+=len(points)-2
                faces.extend([points[0],points[i],points[i+1]] for i in range(1,len(points)-1))
    assert sum(restored.values())==70,restored
    groups.append(np.asarray(faces,'<f4'));canonical,bounds=encode(groups)
    headers=bytearray(canonical[0x45]);prefix=len(lumps[3])//12
    for at in range(0,len(headers),44):struct.pack_into('<i',headers,at+12,struct.unpack_from('<i',headers,at+12)[0]+prefix)
    brushes=[]
    for row in struct.iter_unpack('<3f2BH3fI',lumps[0x5c]):
        c=np.asarray(row[:3]);e=np.asarray(row[6:9]);brushes.append(((c-e).tolist(),(c+e).tolist()))
    grid=collision_grid(brushes,bounds)
    changes={**canonical,**grid,3:lumps[3]+canonical[3],0x45:headers}
    # Keep all render positions, lightmap charts, materials and probes intact.
    # Suppress only mesh indices bound to the source start-barrier material.
    indices=bytearray(lumps[0x4f]);covered=0
    for at in range(0,len(lumps[0x50]),28):
        first,n=struct.unpack_from('<IH',lumps[0x50],at);sort=struct.unpack_from('<H',lumps[0x50],at+22)[0]
        texture=struct.unpack_from('<h',lumps[0x52],sort*12)[0];string=struct.unpack_from('<I',lumps[2],texture*36+12)[0]
        off=struct.unpack_from('<I',lumps[0x2c],string*4)[0];name=lumps[0x2b][off:lumps[0x2b].index(0,off)].decode().lower()
        if 'start_barrier' in name:
            for ti in range(n):
                i=struct.unpack_from('<H',indices,(first+ti*3)*2)[0];struct.pack_into('<3H',indices,(first+ti*3)*2,i,i,i)
            covered+=n
    assert covered==108,covered
    validate_index_padding(lumps[0x50],indices,lumps[0x52]);changes[0x4f]=indices
    scene=np.load(OUT/'scene.npz');names=scene['names'];ids=scene['material'];src=scene['triangles'][np.array(['start_barrier' in str(n) for n in names])[ids],:,:3];scene.close()
    shadow=np.frombuffer(lumps[0x7c],'<f4').reshape(-1,3,3);mask=np.isin(canon(shadow),canon(src));shadow_indices=bytearray(lumps[0x7e])
    for ti in np.flatnonzero(mask):
        i=struct.unpack_from('<H',shadow_indices,int(ti)*6)[0];struct.pack_into('<3H',shadow_indices,int(ti)*6,i,i,i)
    assert int(mask.sum())==108;changes[0x7e]=shadow_indices
    temp=MAP.with_suffix('.source-layout.bsp');compact(MAP,temp,changes);os.replace(temp,MAP)
    cache={**{k:lumps[k] for k in (1,0x5c,0x5d,0x5e,0x5f)},**canonical,**grid,0x5b:struct.pack('<I',1),0x55:struct.pack('<f6i',32768.,-1,-1,2,2,0,1)}
    tmp=OUT/'physics.source-layout.npz';np.savez(tmp,**{str(k):np.frombuffer(v,np.uint8) for k,v in cache.items()});os.replace(tmp,OUT/'physics.npz')
    report=json.loads((OUT/'physics.json').read_text());report.update(world_triangles=report['world_triangles']+70,triangle_headers=len(groups),triangles=sum(len(g) for g in groups),removed_obsolete_clip_triangles={},restored_source_clip_triangles=dict(restored))
    tmp=OUT/'physics.source-layout.json';tmp.write_text(json.dumps(report,indent=2));os.replace(tmp,OUT/'physics.json')
    proof=dict(restored_source_clip_triangles=dict(restored),temporary_spawn_cover_triangles=covered,temporary_shadow_triangles=int(mask.sum()),spawn_cover_collision_note='Six native crossing traces already clear; covers were visual barriers, not matching collision triangles',render_positions_preserved=True,lightmap_charts_preserved=True,backup=str(backup))
    receipt.write_text(json.dumps(proof,indent=2));print(json.dumps(proof,indent=2))

if __name__=='__main__':repair()
