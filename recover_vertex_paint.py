"""Recover authored RGB paint on existing native world/prop vertices.

Match material, position, normal and UV; reject ambiguous source colours.
Source alpha is layer/shader data, not native opaque opacity. Restore RGB only.
This is an incremental repair; collision, lightmaps, UVs and draw budgets stay
byte-identical. Never overwrite a previous receipt or a historical snapshot.
"""
import argparse, collections, hashlib, json, os, shutil, struct, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import numpy as np
from read_vg_static import load
from stage_prop_geometry import rotation
from repair_preview_index_padding import read_lumps
from optimize_portalfree_render import DT,material_name
from compact_preview_bsp import compact
from audit_world_draw_budget import audit
CONFIG={
 'drop-off':('ArenaComposite','mp_arena_composite','inputs/composite/client/maps/mp_rr_arena_composite.bsp',[0,0,0]),
 'phase-runner':('PhaseRunner','mp_phase_runner','inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp',[26000,19000,0])}

def eligible(name):
    return any(s in name.lower() for s in ('_vc','vert_color','v_color','underbelly_cargo_containers'))

def keys(data):
    """Conservative quantization; matched attributes also get a distance check."""
    scales=np.array([20,20,20,1000,1000,1000,1000,1000])
    q=np.rint(np.asarray(data[:,:8],float)*scales).astype('<i4')
    return np.ascontiguousarray(q).view(np.dtype([(str(i),'<i4') for i in range(8)])).ravel()

def unique_source(data):
    k=keys(data);order=np.argsort(k);k=k[order];d=data[order]
    unique,first,counts=np.unique(k,return_index=True,return_counts=True)
    bad=np.zeros(len(k),bool)
    # Adjacent distinct RGB values mark the entire key ambiguous.
    conflict=(k[1:]==k[:-1])&np.any(d[1:,8:11]!=d[:-1,8:11],axis=1)
    bad[1:]=conflict;bad[:-1]|=conflict
    groups=np.repeat(np.arange(len(unique)),counts);badgroups=np.unique(groups[bad]);keep=np.ones(len(unique),bool);keep[badgroups]=False
    return unique[keep],d[first[keep]],len(badgroups)

def source_props(map_id):
    if map_id=='drop-off':
        return json.loads((ROOT/'output/composite/scene.json').read_text())['placements']
    plan=json.loads((ROOT/'logs/tunnel-detail-model-plan.json').read_text())
    lods={p['model']:p['lod_index'] for p in plan['models_detail']}
    return [dict(p,lod=lods[Path(p['model']).stem],folder=str(ROOT/'tools/legion/exported_files/models'/Path(p['model']).stem))
            for p in json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
            if p['in_arena'] and Path(p['model']).stem in lods]

def sources(map_id):
    parts=collections.defaultdict(list);cache={};errors=[]
    for p in source_props(map_id):
        key=(p.get('folder'),p['lod'])
        try:
            if key not in cache:
                sec,slots,skins=load(p['folder'],p['lod'],True)
                cache[key]=([np.asarray(s,'<f4').reshape(-1,12) for s in sec],slots,skins)
            sec,slots,skins=cache[key];skin=skins[min(p['skin'],len(skins)-1)]
            for s,slot in zip(sec,slots):
                name=skin[slot].lower()
                if not len(s) or not eligible(name):continue
                if np.all(s[:,8:11]==255):continue
                a=s.copy();m=np.asarray(rotation(p['angles']));a[:,:3]=s[:,:3]@m.T*p['scale']+p['origin']
                a[:,3:6]=s[:,3:6]@m.T;a[:,3:6]/=np.maximum(np.linalg.norm(a[:,3:6],axis=1,keepdims=True),1e-10);a[:,7]=1-s[:,7]
                parts[name].append(a)
        except (ValueError,OSError,struct.error) as e:errors.append({'index':p['index'],'error':str(e)})
    # World BSP carries its own RGBA paint. The OBJ path previously dropped it.
    import bsp_tool
    source=ROOT/CONFIG[map_id][2];b=bsp_tool.load_bsp(str(source));g=b.external
    delta=np.asarray(CONFIG[map_id][3])
    for mesh in g.MESHES:
        if int(mesh.flags)&0x600!=0x200:continue
        sort=g.MATERIAL_SORTS[mesh.material_sort];name=g.texture_data_surface_name(sort.texture_data).rsplit('/',1)[-1].lower()
        if not eligible(name):continue
        first=mesh.first_mesh_index;ids=sorted(set(sort.vertex_offset+i for i in g.MESH_INDICES[first:first+mesh.num_triangles*3]))
        rows=[]
        for i in ids:
            v=g.VERTEX_LIT_BUMP[i]
            if not hasattr(v,'colour'):continue
            rows.append([*(np.asarray(list(g.VERTICES[v.position_index]))-delta),*list(g.VERTEX_NORMALS[v.normal_index]),*list(v.albedo_uv),*list(v.colour)])
        if rows:parts[name].append(np.asarray(rows,'<f4'))
    print('Source paint materials',len(parts),'models',len(cache),'unavailable exports',len(errors),flush=True)
    return {name:np.concatenate(a) for name,a in parts.items()},errors

def repair(map_id):
    package,map_name,_,_=CONFIG[map_id];base=ROOT/'northstar'/package;path=base/'mod/maps'/(map_name+'.bsp')
    work=ROOT/'output/comparison-repair'/map_id;work.mkdir(parents=True,exist_ok=True)
    receipt=work/'vertex-paint.json'
    if receipt.exists():raise ValueError('Repair already has a receipt; restore baseline before reapplying')
    backup=ROOT/'output/repair-backups/20261012-vertex-paint'/package
    if backup.exists():
        baseline=backup/'mod/maps'/(map_name+'.bsp')
        if hashlib.sha256(baseline.read_bytes()).digest()!=hashlib.sha256(path.read_bytes()).digest():
            raise ValueError('Existing snapshot does not match the unmodified input')
    else:shutil.copytree(base,backup,copy_function=os.link)
    # No operation writes through the snapshot links: replace, never truncate.
    src,errors=sources(map_id)
    l=read_lumps(path,(2,3,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x52))
    v=np.frombuffer(l[0x49],DT).copy();positions=np.frombuffer(l[3],'<f4').reshape(-1,3);normals=np.frombuffer(l[0x1e],'<f4').reshape(-1,3)
    ix=np.frombuffer(l[0x4f],'<u2');groups=collections.defaultdict(list)
    for r in struct.iter_unpack('<I3H6b2h2BHI',l[0x50]):
        mat,_,_,_,vb=struct.unpack_from('<3hHI',l[0x52],r[-2]*12)
        name=material_name(l,mat).replace('\\','/').rsplit('/',1)[-1].lower()
        if name in src and not r[-1]&0x10:groups[name].append(vb+ix[r[0]:r[0]+r[1]*3].astype('u4'))
    report={};changed=np.zeros(len(v),bool);planned={};conflicting=set()
    for name,arrays in groups.items():
        ids=np.unique(np.concatenate(arrays));data=np.column_stack((positions[v['pi'][ids]],normals[v['ni'][ids]],v['uv'][ids]))
        sk,sd,ambiguous=unique_source(src[name]);tk=keys(data);at=np.searchsorted(sk,tk);valid=at<len(sk)
        valid[valid]&=sk[at[valid]]==tk[valid];matched=np.flatnonzero(valid)
        if len(matched):
            sd0=sd[at[matched]];t=data[matched]
            close=np.all(abs(t[:,:3]-sd0[:,:3])<=.026,axis=1)&np.all(abs(t[:,3:8]-sd0[:,3:8])<=.0011,axis=1)
            for vi,c in zip(ids[matched[close]],sd0[close,8:11].astype('u1')):
                vi=int(vi);rgb=tuple(map(int,c))
                if vi in planned and planned[vi]!=rgb:conflicting.add(vi)
                else:planned[vi]=rgb
        report[name]={'target_vertices':len(ids),'matched_vertices':len(matched),'ambiguous_source_keys':ambiguous}
        print(name,'matched',len(matched),'/',len(ids),flush=True)
    for vi,rgb in planned.items():
        if vi in conflicting:continue
        if np.any(v['color'][vi,:3]!=rgb):v['color'][vi,:3]=rgb;changed[vi]=True
    if not changed.any():raise ValueError('No paint recovered')
    expected=np.frombuffer(l[0x49],DT).copy();expected['color']=v['color']
    assert expected.tobytes()==v.tobytes()
    assert np.array_equal(v['color'][:,3],np.frombuffer(l[0x49],DT)['color'][:,3])
    before=audit(path);temp=path.with_suffix('.paint.bsp');compact(path,temp,{0x49:v.tobytes()})
    # Compare every other lump directly, including collision and lighting.
    old=read_lumps(path,range(128));new=read_lumps(temp,range(128))
    diffs=[i for i in range(128) if old[i]!=new[i]]
    # Compact relocates absolute game-lump directory addresses; their payload is empty here.
    if diffs!=[0x49]:raise ValueError('Unexpected changed lumps '+str(diffs))
    after=audit(temp)
    assert {k:v for k,v in before.items() if k!='path'}=={k:v for k,v in after.items() if k!='path'}
    dest=work/(map_name+'.bsp');os.replace(temp,dest)
    # Source/current mod share links with prior packages; detach by replacement.
    stage=path.with_suffix('.replace.bsp');os.link(dest,stage);os.replace(stage,path)
    proof={'map':map_id,'source_reader':'Legion VG flags1 0x10; RGB bytes after packed normal',
           'changed_vertices':int(changed.sum()),'conflicting_target_vertices_skipped':len(conflicting),'materials':report,
           'missing_source_exports':errors,'changed_lumps':diffs,'collision_and_lightmaps_preserved':True,
           'native_alpha_preserved':True,'before_budget':before,'after_budget':after,
           'baseline_sha256':hashlib.sha256((backup/'mod/maps'/(map_name+'.bsp')).read_bytes()).hexdigest(),
           'repaired_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
           'limitation':'RGB paint restored; Apex vertex alpha layer blending is still approximated.'}
    receipt.write_text(json.dumps(proof,indent=2));np.savez(work/'paint-scope.npz',vertices=np.flatnonzero(changed),rgb=v['color'][changed,:3])
    print('Restored',proof['changed_vertices'],'painted vertices; collision/lightmaps/budget preserved',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=CONFIG);a=p.parse_args();repair(a.map)
