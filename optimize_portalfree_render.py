"""Exact render sharing and local PVS safety on the confirmed portal-free build.

All collision and normal/position buffers stay byte-identical. Re-indexing
only aliases bit-identical values already in those buffers; it never averages
tangents, changes lightmap UVs, simplifies geometry or imports portal data.
"""
import collections,json,struct,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit,WORLD_INDEX_CAPACITY
from rebuild_local_visibility import make_tree

SOURCE=ROOT/'output/phase-runner/preview-interior-lighting/mp_phase_runner_preview.bsp'
TARGET=ROOT/'output/phase-runner/preview-portalfree-optimized/mp_phase_runner_preview.bsp'
DT=np.dtype([('pi','<u4'),('ni','<u4'),('uv','<f4',2),('color','u1',4),('light','<f4',4),('tangent','<u4'),('extra','<u4')])
LOCAL_PAD=384.
CAMERA_MIN=(-12288.,-12288.,-4096.)
CAMERA_MAX=(12288.,12288.,4096.)


def canonical_ids(values,ids):
    """Alias equal bytes to an existing index; preserve signed zero/NaN bits."""
    ids=np.unique(ids)
    _,first,inverse=np.unique(values[ids],return_index=True,return_inverse=True)
    return ids,ids[first][inverse]


def share_render(l,max_vertices=60000):
    if not 1536<=max_vertices<=65535:raise ValueError('Native local vertex cap invalid')
    if any(l[i] for i in range(0x47,0x4e) if i!=0x49):raise ValueError('Other vertex formats require separate remapping')
    if any(not r[2] or r[3]!=-1 for r in struct.iter_unpack('<2I2h',l[0x7f])):
        raise ValueError('Alpha shadow material-sort references need explicit preservation')
    rows=list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))
    if any(r[4]!=2 or r[-1]&0x600!=0x200 for r in rows):raise ValueError('Non-lit mesh needs separate remapping')
    original=np.frombuffer(l[0x49],DT);v=original.copy()
    positions=np.frombuffer(l[3],'V12');normals=np.frombuffer(l[0x1e],'V12')
    pids,paliases=canonical_ids(positions,v['pi'])
    tangent=v['tangent']&0x7fffffff
    nids,naliases=canonical_ids(normals,np.concatenate((v['ni'],tangent)))
    v['pi']=paliases[np.searchsorted(pids,v['pi'])]
    v['ni']=naliases[np.searchsorted(nids,v['ni'])]
    v['tangent']=naliases[np.searchsorted(nids,tangent)]|(v['tangent']&0x80000000)
    oldix=np.frombuffer(l[0x4f],'<u2');sorts=list(struct.iter_unpack('<3hHI',l[0x52]))
    bybinding=collections.OrderedDict()
    for mi,r in enumerate(rows):bybinding.setdefault(sorts[r[-2]][:3],[]).append(mi)
    meshes=bytearray(l[0x50]);indices=oldix.copy();packed=bytearray();news=bytearray()
    def flush(binding,vertices):
        if not vertices:return
        news.extend(struct.pack('<3hHI',*binding,len(vertices)-1,len(packed)//44))
        packed.extend(b''.join(vertices))
    for binding,group in bybinding.items():
        vertices=[]
        for mi in group:
            r=rows[mi];first,count=r[:2];base=sorts[r[-2]][4]
            raw=v[base+oldix[first:first+count*3].astype('<u4')]
            keys=[bytes(key) for key in raw.view('V44')]
            if vertices and len(vertices)+len(set(keys))>max_vertices:
                flush(binding,vertices);vertices=[]
            if len(set(keys))>max_vertices:raise ValueError('A mesh exceeds native vertex capacity')
            # Keep each mesh's vertices in one contiguous block. Sharing across
            # meshes could increase its native CPU clipping span to tens of
            # thousands of vertices despite containing only 512 triangles.
            cache={};block_start=len(vertices);local=[]
            for key in keys:
                index=cache.get(key)
                if index is None:index=len(vertices);cache[key]=index;vertices.append(key)
                local.append(index)
            indices[first:first+count*3]=local
            if count&1:indices[first+count*3:first+count*3+3]=local[-1]
            struct.pack_into('<2H',meshes,mi*28+6,min(local),max(local)-min(local))
            if max(local)-min(local)>r[3]:raise ValueError('Native per-mesh clipping span increased')
            struct.pack_into('<H',meshes,mi*28+22,len(news)//12)
        flush(binding,vertices)
    if len(news)//12>=8192:raise ValueError('Native sort capacity exceeded')
    proof=validate_index_padding(meshes,indices.tobytes(),news)
    return {0x49:packed,0x4f:indices.tobytes(),0x50:meshes,0x52:news},dict(
        old_vertices=len(original),new_vertices=len(packed)//44,old_vertex_bytes=len(l[0x49]),new_vertex_bytes=len(packed),
        old_material_sorts=len(sorts),new_material_sorts=len(news)//12,unique_material_lightmap_bindings=len(bybinding),
        vertex_bytes_saved=len(l[0x49])-len(packed),normal_and_position_buffers_preserved=True,
        exact_values_only=True,tangents_not_averaged=True,max_local_vertices=max_vertices,index_padding=proof)


def material_name(l,tex):
    ni=struct.unpack_from('<I',l[2],tex*36+12)[0];offset=struct.unpack_from('<I',l[0x2c],ni*4)[0]
    return l[0x2b][offset:l[0x2b].index(0,offset)].decode().replace('\\','/')


def local_visibility(l,routes):
    ms=list(struct.iter_unpack('<8f',l[0x51]));rows=list(struct.iter_unpack('<I3H6b2h2BHI',l[0x50]))
    sorts=list(struct.iter_unpack('<3hHI',l[0x52]));envelopes=[]
    for route in routes:
        p=np.asarray(route['points']);lo=p.min(0)-[320,320,512];hi=p.max(0)+[320,320,384]
        envelopes.append((lo.tolist(),hi.tolist()))
    boxes=[];sky=[];protected=[[] for _ in envelopes]
    for mi,m in enumerate(ms):
        low=[m[k]-m[k+4]-LOCAL_PAD for k in range(3)]
        high=[m[k]+m[k+4]+LOCAL_PAD for k in range(3)]
        name=material_name(l,sorts[rows[mi][-2]][0])
        if name.endswith('/phase_runner_sky'):
            sky.append(mi);low=[min(low[k],CAMERA_MIN[k]) for k in range(3)];high=[max(high[k],CAMERA_MAX[k]) for k in range(3)]
        else:
            # Select against the original geometric box, not another expanded
            # envelope, so protection cannot cascade across the whole map.
            original_low=[m[k]-m[k+4] for k in range(3)];original_high=[m[k]+m[k+4] for k in range(3)]
            for j,(lo,hi) in enumerate(envelopes):
                if all(original_high[k]>=lo[k] and original_low[k]<=hi[k] for k in range(3)):
                    protected[j].append(mi);low=[min(low[k],lo[k]) for k in range(3)];high=[max(high[k],hi[k]) for k in range(3)]
        boxes.append((low,high))
    if not sky:raise ValueError('Decorative sky not found')
    nodes,refs,objects=make_tree(boxes,leaf_size=64)
    changes={0x77:b''.join(nodes),0x78:struct.pack('<'+'H'*len(refs),*refs),0x79:objects}
    validation=validate_visibility(changes[0x77],changes[0x78],changes[0x79],l[0x51])
    return changes,dict(**validation,sky_meshes=sky,tunnel_envelopes=envelopes,tunnel_protected_meshes=protected,
        local_padding=LOCAL_PAD,portal_graph_restored_version='0.1.34',new_portal_connections=0,
        sky_camera_domain=[CAMERA_MIN,CAMERA_MAX],real_mesh_bounds_preserved=True,
        limitation='Conservative nearby/tunnel object bounds; far geometry remains spatially bounded. Client PVS and frame rate need a visual check.')


def build():
    start=time.monotonic()
    ids=(2,3,0x1e,0x2b,0x2c,*range(0x47,0x4e),0x4f,0x50,0x51,0x52,0x7f)
    l=read_lumps(SOURCE,ids)
    render,sharing=share_render(l)
    route=json.loads((ROOT/'output/phase-runner/preview-tunnel-walkways/tunnel-walkways.json').read_text())['routes']
    visibility,vis=local_visibility(l,route)
    compaction=compact(SOURCE,TARGET,{**render,**visibility});budget=audit(TARGET)
    if budget['native_padded_indices']>int(WORLD_INDEX_CAPACITY*.85):raise ValueError('Draw budget headroom lost')
    if budget['real_triangles']!=audit(SOURCE)['real_triangles']:raise ValueError('Triangle loss')
    status=json.loads(SOURCE.with_name('source-build.json').read_text())
    status.pop('local_visibility_rebuild',None)
    report=dict(version='0.1.36',withdrawn_version='0.1.35',source_version='0.1.34',render_sharing=sharing,
        visibility=vis,budget=budget,compaction=compaction,elapsed_seconds=time.monotonic()-start,
        original_positions_normals_collision_lights_lightmaps_shadow_geometry_walkways_preserved=True,
        client_rendering_verified=False,client_performance_verified=False)
    status['portalfree_optimization']=report;status['visibility_rebuild']=vis;status['final_compaction']=compaction
    status['world_draw_budget_repair']['after']=budget
    TARGET.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    TARGET.with_name('portalfree-optimization.json').write_text(json.dumps(report,indent=2))
    shutil.copy2(SOURCE.with_suffix('.stbsp'),TARGET.with_suffix('.stbsp'))
    print(json.dumps({k:v for k,v in report.items() if k!='visibility'},indent=2),flush=True)
    print(json.dumps({k:v for k,v in vis.items() if k!='tunnel_protected_meshes'},indent=2),flush=True)

if __name__=='__main__':build()
