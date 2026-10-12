"""Separate native decal layers without changing any collision or lightmap UVs."""
import hashlib,json,os,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from optimize_portalfree_render import DT,material_name
from repair_preview_index_padding import read_lumps
from build_phase_runner_catwalks import mesh_faces
from compact_preview_bsp import compact

def render_digest(path):
    data=read_lumps(path,(3,0x49,0x51))
    return hashlib.sha256(b''.join(data[k] for k in (3,0x49,0x51))).hexdigest()

def apply():
    path=ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'
    receipt=ROOT/'output/phase-runner/decal-layer-repair.json'
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    if receipt.exists():
        previous=json.loads(receipt.read_text())
        if previous.get('output_render_sha256')==render_digest(path) or previous.get('output_sha256')==before:
            print('Phase Runner decal separation already applied');return
        raise ValueError('Existing decal receipt does not match render geometry; rebuild from an unmodified source before applying again')
    l=read_lumps(path,(2,3,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52))
    v=np.frombuffer(l[0x49],DT).copy();p=np.frombuffer(l[3],'<f4').reshape(-1,3)
    normals=np.frombuffer(l[0x1e],'<f4').reshape(-1,3)
    new=bytearray(l[3]);changes={};touched=set();bounds=bytearray(l[0x51])
    for mi,r,raw,ids,tri in mesh_faces(l):
        ti=struct.unpack_from('<h',l[0x52],r[-2]*12)[0];name=material_name(l,ti)
        if 'decal' not in name.lower():continue
        offset=.16 if 'stripes' in name.lower() else .08
        ids=np.unique(ids);ids=ids[np.array([int(i) not in touched for i in ids])]
        xyz=p[v['pi'][ids]]+normals[v['ni'][ids]]*offset
        first=len(new)//12;new.extend(xyz.astype('<f4').tobytes())
        v['pi'][ids]=np.arange(first,first+len(ids));touched.update(map(int,ids))
        changes.setdefault(name,dict(vertices=0,offset=offset))['vertices']+=len(ids)
        row=list(struct.unpack_from('<8f',bounds,mi*32));row[3]+=.2
        for k in (4,5,6):row[k]+=.2
        struct.pack_into('<8f',bounds,mi*32,*row)
    temp=path.with_suffix('.decals.bsp')
    compact(path,temp,{3:new,0x49:v.tobytes(),0x51:bounds})
    # Only render positions are appended. Existing collision position indices
    # and all collision buffers retain their original bytes and references.
    assert read_lumps(temp,[3])[3][:len(l[3])]==l[3]
    collision=(1,0x42,0x44,0x45,0x54,0x55,0x5b,0x5c,0x5d,0x5e,0x5f)
    assert read_lumps(path,collision)==read_lumps(temp,collision)
    os.replace(temp,path)
    report=dict(input_sha256=before,output_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),output_render_sha256=render_digest(path),materials=changes,collision_preserved=True)
    receipt.write_text(json.dumps(report,indent=2));print('Phase Runner decal materials',len(changes),'render vertices',len(touched))

if __name__=='__main__':apply()
