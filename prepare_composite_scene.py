"""Recover a renderer-neutral, source-positioned Composite arena scene."""
import collections,json,struct,sys,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from stage_prop_geometry import rotation,material_basename
from read_vg_static import load
OUT=ROOT/'output/composite'

def sky_dome():
    """Opaque photographic sky, separate from collision and shadow casters."""
    faces=[]
    def vertex(a,b):
        normal=np.array([math.sin(a)*math.cos(b),math.sin(a)*math.sin(b),math.cos(a)])
        radial=.5*math.sin(a/2)
        return [*(normal*22000),*(-normal),.5+radial*math.cos(b),.5-radial*math.sin(b)]
    for y in range(16):
        for x in range(32):
            corners=[vertex(math.pi*a/16,2*math.pi*b/32) for a,b in ((y,x),(y+1,x),(y+1,x+1),(y,x+1))]
            for ids in ((0,1,2),(0,2,3)):
                if y==0 and ids==(0,2,3) or y==15 and ids==(0,1,2):continue
                faces.append([corners[i] for i in ids])
    return np.array(faces,'<f4')

def world():
    path=OUT/'world.npz'
    if path.exists():
        cached=np.load(path);names=cached['names'];mi=cached['material'];tri=cached['triangles'];cached.close()
        keep=~np.array(['start_barrier' in str(n).lower() for n in names])[mi]
        return dict(triangles=tri[keep],material=mi[keep],names=names)
    points=[];normals=[];uvs=[];faces=[];materials=[];names=[];name='';active=False
    with (OUT/'mp_rr_arena_composite.obj').open() as f:
        for line in f:
            if line.startswith('v '):points.append(tuple(map(float,line.split()[1:4])))
            elif line.startswith('vn '):normals.append(tuple(map(float,line.split()[1:4])))
            elif line.startswith('vt '):uvs.append(tuple(map(float,line.split()[1:3])))
            elif line.startswith('usemtl '):
                name=line.split()[1];active=not name.lower().startswith('tools/') and 'start_barrier' not in name.lower()
                if active and name not in names:names.append(name)
            elif line.startswith('g '):active=False
            elif line.startswith('f ') and active:
                # OBJ negative indices refer to the stream length at this face,
                # not the final length of the file. The exporter uses them for
                # every triangle, so resolve them before reading the next face.
                lengths=(len(points),len(uvs),len(normals))
                ids=[tuple(int(v)-1 if int(v)>0 else lengths[k]+int(v)
                           for k,v in enumerate(x.split('/'))) for x in line.split()[1:]]
                for i in range(1,len(ids)-1):faces.append([ids[0],ids[i],ids[i+1]]);materials.append(names.index(name))
    faces=np.array(faces,np.int32);p=np.array(points,'<f4')[faces[:,:,0]]
    keep=np.all(abs(p[:,:,:2])<=12000,axis=(1,2))&np.all(abs(p[:,:,2])<=12000,axis=1)
    # Exclude remote menu/backdrop geometry, retaining local arena surfaces.
    faces=faces[keep];p=p[keep];n=np.array(normals,'<f4')[faces[:,:,2]];uv=np.array(uvs,'<f4')[faces[:,:,1]]
    data=np.concatenate((p,n,uv),axis=2);mi=np.array(materials,np.int32)[keep]
    np.savez(path,triangles=data,material=mi,names=np.array(names));print('Local world triangles',len(data),flush=True)
    return np.load(path)

def prepare():
    worlddata=world();audit=json.loads((OUT/'asset-audit.json').read_text());cache={};failures={};lods={}
    counts=collections.Counter(p['model'] for p in audit['props']);available={}
    for model,folder in audit['model_paths'].items():
        if not folder:continue
        try:
            raw=(Path(folder)/(Path(folder).name+'.vg')).read_bytes();h=struct.unpack_from('<18Q',raw,16);count=h[13]
            candidates=[]
            for lod in range(min(count,5)):
                sections,slots,skins=load(Path(folder),lod)
                sections=[np.array(x,dtype='<f4').reshape(-1,3,8) for x in sections]
                candidates.append((sections,slots,skins,lod))
            available[model]=candidates
        except Exception as e:failures[model]=str(e)
    # Author-made source LODs preserve topology. Advance the most expensive
    # repeated model until the conservative all-visible native budget fits.
    levels={m:0 for m in available};world_count=len(worlddata['triangles']);budget=900000-world_count-len(sky_dome())
    def tris(c):return sum(len(s) for s in c[0])
    total=sum(tris(cs[0])*counts[m] for m,cs in available.items())
    while total>budget:
        options=[((tris(cs[levels[m]])-tris(cs[levels[m]+1]))*counts[m],m) for m,cs in available.items() if levels[m]+1<len(cs)]
        if not options:break
        saving,model=max(options);levels[model]+=1;total-=saving
    omitted=[];selected=[];batch=collections.defaultdict(list);physics=[]
    # Structural solids take precedence over repeated decorative furnishings.
    # A staircase is often SOLID_NONE because its collision is in the world
    # mesh. It must not lose its visual budget to tiny solid furnishings.
    reported={3153,5292,5278,3282}
    props=sorted(audit['props'],key=lambda p:(
        not ('stair' in p['model'].lower() or p['index'] in reported),
        p['solid'] not in (2,6,7),
        not any(w in p['model'].lower() for w in ('levels_terrain','wall','floor','railing','pipe')),p['index']))
    used=0
    for p in props:
        if p['index']==4924:
            omitted.append(dict(index=p['index'],model=p['model'],reason='Detached wind shield at reported floating geometry location; removed with collider'))
            continue
        cs=available.get(p['model'])
        if cs is None:omitted.append(dict(index=p['index'],model=p['model'],reason=failures.get(p['model'],'Asset not recovered')));continue
        sec,slots,skins,lod=cs[levels[p['model']]];n=tris(cs[levels[p['model']]])
        if used+n>budget:omitted.append(dict(index=p['index'],model=p['model'],reason='Native all-visible draw budget'));continue
        mat=np.array(rotation(p['angles']),float);org=np.array(p['origin']);skin=skins[min(p['skin'],len(skins)-1)];actual=0
        for s,slot in zip(sec,slots):
            if not len(s):continue
            name=skin[slot]
            if any(w in name for w in ('godray','ambient_occlusion','start_barrier','atmosphere','glow_overlay')):continue
            data=s.copy();data[:,:,:3]=s[:,:,:3]@mat.T*p['scale']+org;data[:,:,3:6]=s[:,:,3:6]@mat.T;data[:,:,7]=1-s[:,:,7]
            if not np.isfinite(data).all():raise ValueError('Nonfinite placed geometry')
            batch[name].append(data);actual+=len(data)
        if actual:
            used+=actual;selected.append({**p,'lod':lod,'triangles':actual,'folder':audit['model_paths'][p['model']]})
    materials=list(worlddata['names']);arrays=[worlddata['triangles']];ids=[worlddata['material']]
    materials.append('sky');arrays.append(sky_dome());ids.append(np.full(len(sky_dome()),len(materials)-1,np.int32))
    for name,parts in batch.items():
        if name not in materials:materials.append(name)
        a=np.concatenate(parts);arrays.append(a);ids.append(np.full(len(a),materials.index(name),np.int32))
    data=np.concatenate(arrays);mi=np.concatenate(ids)
    surface_repairs={}
    for i,name in enumerate(materials):
        if any(w in name.lower() for w in ('decal','btt_wld')):
            # Native world meshes lack Apex's decal depth bias. Keep authored
            # UVs and lighting, but separate successive decorative layers.
            amount=.24 if 'btt_wld' in name.lower() else .16 if 'stripes' in name.lower() else .08
            mask=mi==i;data[mask,:,:3]+=data[mask,:,3:6]*amount
            surface_repairs[name]=dict(triangles=int(mask.sum()),offset=amount)
    placeholder=np.array(['dev_gray_512_v_color' in materials[i] for i in mi])
    if placeholder.any():
        data=data[~placeholder];mi=mi[~placeholder]
    np.savez(OUT/'scene.npz',triangles=data,material=mi,names=np.array(materials))
    report=dict(source_map='mp_rr_arena_composite',target_map='mp_arena_composite',world_triangles=world_count,
        triangles=len(data),props=len(selected),source_playable_props=len(audit['props']),placements=selected,
        model_decode_failures=failures,omitted=omitted,materials={m:int((mi==i).sum()) for i,m in enumerate(materials)},
        bounds=[data[:,:,:3].min(axis=(0,1)).tolist(),data[:,:,:3].max(axis=(0,1)).tolist()],
        surface_repairs=surface_repairs,removed_door_placeholder_triangles=int(placeholder.sum()),
        source_lod_policy='Author-made lower LODs within 900,000 world triangles; no triangle decimation')
    (OUT/'scene.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('placements','omitted','materials','model_decode_failures')},indent=2),flush=True)
if __name__=='__main__':prepare()
