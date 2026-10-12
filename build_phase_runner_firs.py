"""Stage twenty full-size authored firs over the working 0.1.44, with native cutout leaves."""
import collections,io,json,os,shutil,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from PIL import Image
from read_vg_static import load
from read_prop_physics import read_phy,plane
from build_center_detail import placement_sections,add_texture_rows,active
from build_phase_runner_catwalks import mesh_faces,shadows
import build_phase_runner_catwalks as lighting
from prepare_dev_materials import stage
import prepare_dev_materials
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from build_phase_runner_presentation import guid
from bake_terrain_transitions import save_mips
from repair_preview_index_padding import read_lumps,validate_index_padding
from compact_preview_bsp import compact
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from apply_baked_lighting import tangents
from native_triangle_collision import encode
from repair_tunnel_passages import remap_grid
from audit_world_draw_budget import enforce_camera_bypass_budget,WORLD_INDEX_CAPACITY
from finalize_lighting_release import digest
P=ROOT/'output/phase-runner';BASE=ROOT/'northstar/PhaseRunner.ArtSupportsLoadingRelease'
SOURCE=ROOT/'northstar/PhaseRunner.ArtSupportsLoadingRelease/mod/maps/mp_phase_runner.bsp'
OUT=P/'firs';TARGET=OUT/'mp_phase_runner.bsp'
MATERIALS=P/'fir-materials';PACKAGE=ROOT/'northstar/PhaseRunner.FirsRelease'
MODEL='tree_fir_large_arenas_01';LEAVES='tree_fir_large_leaves_01';LOD=2
VERSION='0.1.46'

def select():
    missing=json.loads((ROOT/'logs/art-supports-remaining-objects.json').read_text())['remaining_placements']
    candidates=[p for p in missing if Path(p['model']).stem==MODEL and sum(v*v for v in p['origin'][:2])<=4000**2]
    # Some authored trees intersect a solid rock in the imported collision.
    # Prefer source placements with exposed trunks; keep every existing rock.
    l=read_lumps(SOURCE,(1,0x5c,0x57,0x59));live=active(l);planes=np.frombuffer(l[1],'<f4').reshape(-1,4)
    brushes=[r for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])) if (0,i) in live]
    local,_=tree_physics();eligible=[];excluded=[]
    from stage_prop_geometry import rotation
    for p in candidates:
        tri=(local@np.asarray(rotation(p['angles'])).T*p['scale']+p['origin']).astype('<f4')
        probes=trunk_probe_pair(p,tri);blocked=False
        for probe in probes:
            point=np.asarray(probe['start'])
            for r in brushes:
                if np.any(point<np.asarray(r[:3])-r[6:9]-.01) or np.any(point>np.asarray(r[:3])+r[6:9]+.01):continue
                cuts=planes[1+r[9]:1+r[9]+r[4]]
                if np.all(cuts[:,:3]@point<=cuts[:,3]+.01):blocked=True;break
            if blocked:break
        (excluded if blocked else eligible).append(p)
    candidates=eligible
    (OUT/'selection.json').write_text(json.dumps(dict(excluded_inside_existing_brush=[p['index'] for p in excluded],eligible_original_placements=len(eligible)),indent=2))
    assert len(candidates)>=20
    chosen=[min(candidates,key=lambda p:sum(v*v for v in p['origin'][:2]))]
    while len(chosen)<20:
        chosen.append(max((p for p in candidates if p not in chosen),key=lambda p:min(sum((p['origin'][i]-q['origin'][i])**2 for i in range(2)) for q in chosen)))
    return sorted(chosen,key=lambda p:p['index'])

def geometry(props):
    sections,slots,skins=load(ROOT/'tools/legion/exported_files/models'/MODEL,LOD)
    arrays=[];mats=[];proof=[]
    for p in props:
        start=sum(len(a) for a in arrays)
        for mat,a in placement_sections(p,sections,slots,skins):arrays.append(a);mats.extend([mat]*len(a))
        proof.append(dict(index=p['index'],model=p['model'],origin=p['origin'],angles=p['angles'],scale=p['scale'],skin=p['skin'],solid_mode=p['solid_mode'],source_lod=LOD,first_triangle=start,triangles=sum(len(a) for a in arrays)-start))
    data=np.concatenate(arrays).astype('<f4');assert len(data)==20280
    return data,np.array(mats),proof

def dds_image(path):
    raw=bytearray(Path(path).read_bytes())
    if raw[84:88]==b'DX10':
        fmt=struct.unpack_from('<I',raw,128)[0]
        if fmt in (72,75,78,99):struct.pack_into('<I',raw,128,fmt-1)
    return Image.open(io.BytesIO(raw)).convert('RGBA')

def save_leaf_mips(image,path):
    """Keep needle coverage when minification selects a smaller foliage mip."""
    current=image;parts=[];target=float(np.mean(np.asarray(image)[:,:,3]>=128));first=True
    while True:
        a=np.array(current)
        if not first:
            alpha=a[:,:,3].astype(float)
            candidates=[1.]+[128./v for v in np.unique(alpha) if v>0]
            scale=min(candidates,key=lambda s:(abs(np.mean(np.minimum(255,np.rint(alpha*s))>=128)-target),abs(s-1.)))
            a[:,:,3]=np.minimum(255,np.rint(alpha*scale)).astype(np.uint8)
        b=io.BytesIO();Image.fromarray(a).save(b,format='DDS',pixel_format='DXT5');parts.append(b.getvalue()[128:])
        if current.size==(1,1):break
        # Downsample the unscaled coverage; scaling is local to each level.
        current=current.resize((max(1,current.width//2),max(1,current.height//2)),Image.Resampling.BOX);first=False
    b=io.BytesIO();image.save(b,format='DDS',pixel_format='DXT5');header=bytearray(b.getvalue()[:128])
    struct.pack_into('<I',header,8,struct.unpack_from('<I',header,8)[0]|0x20000)
    struct.pack_into('<I',header,28,len(parts));struct.pack_into('<I',header,108,0x401008)
    Path(path).write_bytes(header+b''.join(parts))

def embed_shader(pak,shader_guid,manifest,cache):
    if shader_guid in cache:return cache[shader_guid]
    asset=next(a for a in pak.assets if a['guid']==shader_guid);h=pak.address(asset['header'])
    vs,ps=struct.unpack_from('<2Q',pak.data,h+72);vtex,ptex,samplers=struct.unpack_from('<3H',pak.data,h+24);first,resources=struct.unpack_from('<2H',pak.data,h+30)
    def bytecode(g):
        found=next((a for a in pak.assets if a['guid']==g),None)
        if found is not None:return shader(pak,found)
        common=NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak')
        return shader(common,next(a for a in common.assets if a['guid']==g))
    pixel,pp=bytecode(ps);vertex,vp=bytecode(vs)
    name=f'phase_runner_fir_{shader_guid:x}';path=f'shaderset/{name}.rpak';target=(MATERIALS/'assets'/path).with_suffix('.msw');target.parent.mkdir(parents=True,exist_ok=True)
    newps=guid(f'shader/{name}_pixel.rpak');newvs=guid(f'shader/{name}_vertex.rpak')
    target.write_bytes(b'MSW\x03\x01'+struct.pack('<2Q3H2B2I',newps,newvs,ptex,vtex,samplers,first,resources,37,37+len(pixel))+pixel+vertex)
    manifest['files'].append(dict(_type='shds',_path=path));cache[shader_guid]=path
    return path

def materials(names):
    MATERIALS.mkdir(parents=True,exist_ok=True);prepare_dev_materials.PROJECT=MATERIALS
    assets=MATERIALS/'assets';manifest=dict(version=7,name='phase_runner_firs',keepDevOnly=True,assetsDir=str(assets),outputDir=str(MATERIALS/'build'),compressLevel=0,hasDynamicLibrary=False,files=[]);mapping={}
    neutral=MATERIALS/'neutral_spec.dds';save_mips(Image.new('RGBA',(4,4),(8,8,8,255)),neutral)
    flat=MATERIALS/'neutral_gloss.dds';save_mips(Image.new('RGBA',(4,4),(30,30,30,255)),flat)
    def channel(name,semantic):
        folder=ROOT/'tools/legion/exported_files/materials'/name
        aliases=dict(albedo='col',normal='nml',gloss='gls',spec='spc')
        for p in (folder/(name+'_'+semantic+'Texture.dds'),folder/(name+'_'+aliases[semantic]+'.dds')):
            if p.exists():return p
        if semantic=='spec':return neutral
        if semantic=='gloss':
            recovered=ROOT/'tools/legion/exported_files/materials'/LEAVES/'30_gloss_flat_gls.dds'
            return recovered if recovered.exists() else flat
        raise ValueError('Missing tree channel '+name+' '+semantic)
    for name in names:
        if name.startswith(LEAVES):continue
        stage(name,{s:channel(name,s) for s in ('albedo','normal','gloss','spec')},'Recovered fir bark PBR channels',manifest,mapping)
    native=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak');shaders={}
    for name in names:
        if not name.startswith(LEAVES):continue
        folder=ROOT/'tools/legion/exported_files/materials'/name
        albedo=np.array(dds_image(channel(name,'albedo')))
        opacity=np.array(dds_image(folder/(name+'_opacityMultiplyTexture.dds')))[:,:,0]
        assert albedo.shape[:2]==opacity.shape
        albedo[:,:,3]=((albedo[:,:,3].astype(np.uint16)*opacity.astype(np.uint16)+127)//255).astype(np.uint8)
        assert albedo[:,:,3].min()==0 and albedo[:,:,3].max()==255
        combined=MATERIALS/(name+'_cutout.dds');save_leaf_mips(Image.fromarray(albedo),combined)
        textures={}
        for i,semantic in enumerate(('albedo','normal','gloss','spec')):
            source=combined if i==0 else channel(name,semantic)
            path=f'texture/phase_runner_firs/{name}_{semantic}.rpak';dest=(assets/path).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            textures[str(i)]=path;manifest['files'].append(dict(_type='txtr',_path=path,**{'$disableStreaming':True}))
        paths={};pending=[]
        def emit(g):
            if not g:return '0x0'
            if g in paths:return paths[g]
            asset=next(a for a in native.assets if a['guid']==g);spec,uber=native.material(asset)
            suffix=spec['name'].rsplit('/',1)[-1].replace('rope_net',name)
            world='world/phase_runner_preview/'+suffix;path='material/'+world+'_wld.rpak';paths[g]=path
            spec['name']=world;spec['width'],spec['height']=albedo.shape[1],albedo.shape[0];spec['surfaceProp']='wood_solid'
            spec['blendStates']+=['0x0']*4
            spec['rasterizerFlags']=hex(int(spec['rasterizerFlags'],16)&~4)
            spec['shaderSet']=embed_shader(native,int(spec['shaderSet'],16),manifest,shaders)
            spec['$textures']={slot:textures[slot] for slot in spec['$textures']}
            for field in ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
                spec[field]=emit(int(spec[field],16))
            target=assets/path;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(spec,indent=2));target.with_suffix('.uber').write_bytes(uber)
            pending.append(dict(_type='matl',_path=path))
            return path
        emit(0x77559dca514b790f);manifest['files']+=pending
        mapping[name]=dict(name='world/phase_runner_preview/'+name,width=albedo.shape[1],height=albedo.shape[0],provenance='Native two-sided world cutout; local native shader/depth dependencies; recovered opacity and source leaf skin')
    (MATERIALS/'build.json').write_text(json.dumps(manifest,indent=2));(MATERIALS/'mapping.json').write_text(json.dumps(mapping,indent=2))
    r=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(MATERIALS/'build.json')],capture_output=True,text=True);(MATERIALS/'build.log').write_text(r.stdout+r.stderr)
    if r.returncode:raise ValueError('Tree asset package failed')
    pak=NativePak(MATERIALS/'build/phase_runner_firs.rpak');own={a['guid'] for a in pak.assets};known=set(own)
    for name in ('common','coliseum'):known.update(a['guid'] for a in NativePak(ROOT/f'inputs/tf2-rpak-work/{name}.raw.rpak').assets)
    for a in pak.assets:
        if a['type']!='matl':continue
        spec,_=pak.material(a)
        for value in list(spec['$textures'].values())+[spec[k] for k in ('shaderSet','$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial')]:
            g=int(value,16)
            if g and g not in known:raise ValueError('Unresolved material dependency '+value)
        if '/'+LEAVES in spec['name']:
            for field in ('shaderSet','$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial'):
                g=int(spec[field],16)
                if g and g not in own:raise ValueError('Leaf pipeline depends on another map package')
    return mapping,pak

def tree_physics():
    pieces=read_phy(ROOT/f'tools/legion/exported_files/models/{MODEL}/{MODEL}.phy');stats=dict(source='IRPS',convex_pieces=len(pieces))
    local=np.asarray([[f[0],f[i],f[i+1]] for piece in pieces for f in piece for i in range(1,len(f)-1)],'<f4')
    assert len(local)==34
    return local,stats

def trunk_probe_pair(p,tri):
    # Intersect an actual trunk triangle at pilot height. Fir side triangles
    # extend hundreds of units, so their centroids do not lie near the root.
    z=p['origin'][2]+80.;cuts=[]
    for t in tri:
        crossings=[]
        for a,b in zip(t,np.roll(t,-1,axis=0)):
            if (a[2]<z)!=(b[2]<z):crossings.append(a+(b-a)*(z-a[2])/(b[2]-a[2]))
        if len(crossings)==2:
            q=plane(t.tolist())
            if q is not None:cuts.append((np.mean(crossings,axis=0),np.asarray(q[:3])))
    assert cuts,'No trunk surface at pilot height'
    c,n=max(cuts,key=lambda x:np.linalg.norm(x[1][:2]));n[2]=0;n/=np.linalg.norm(n)
    projected=(tri.reshape(-1,3)-c)@n;lo,hi=projected.min()-24,projected.max()+24
    return [dict(index=p['index'],start=(c+n*a).tolist(),end=(c+n*b).tolist()) for a,b in ((lo,hi),(hi,lo))]

def collision(l,props):
    local,stats=tree_physics()
    owners=[];groups=[];probes=[];old=active(l);first_header=len(l[0x45])//44
    from stage_prop_geometry import rotation
    for p in props:
        matrix=np.asarray(rotation(p['angles']));tri=(local@matrix.T*p['scale']+p['origin']).astype('<f4')
        good=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>1e-5;tri=tri[good]
        first=first_header+len(groups)
        for i in range(0,len(tri),96):groups.append(tri[i:i+96])
        owners.append(dict(index=p['index'],first_header=first,headers=first_header+len(groups)-first,triangles=len(tri),method='original_trunk_IRPS_surface'))
        # Probe a trunk face from each side. The radius is deliberately small
        # because this tree has a thin trunk, unlike a pilot-wide box collider.
        probes.extend(trunk_probe_pair(p,tri))
    enc,bounds=encode(groups,len(l[3])//12)
    for at in range(0,len(enc[0x45]),44):
        struct.pack_into('<i',enc[0x45],at+16,struct.unpack_from('<i',enc[0x45],at+16)[0]+len(l[0x42])//4)
        struct.pack_into('<i',enc[0x45],at+20,struct.unpack_from('<i',enc[0x45],at+20)[0]+len(l[0x44])//16)
    bb=[];bi=[]
    for i,r in enumerate(struct.iter_unpack('<3f2BH3fI',l[0x5c])):
        if (0,i) in old:c=np.array(r[:3]);e=np.array(r[6:9]);bb.append(((c-e).tolist(),(c+e).tolist()));bi.append(i)
    positions=np.frombuffer(l[3],'<f4').reshape(-1,3);tb=[];ti=[]
    for i,h in enumerate(struct.iter_unpack('<6h4i4f',l[0x45])):
        if (0x40,i) in old:
            v=positions[h[6]:h[6]+h[3]];tb.append((v.min(0).tolist(),v.max(0).tolist()));ti.append(i)
    grid=remap_grid(bb,tb+bounds,bi,ti+list(range(first_header,first_header+len(bounds))))
    if active(grid)!=old|{(0x40,i) for i in range(first_header,first_header+len(bounds))}:raise ValueError('Existing collision changed')
    changes={i:l[i]+enc[i] for i in (0x42,0x44,0x45,0x60)};changes.update(grid)
    return changes,enc[3],dict(owners=owners,probes=probes,new_headers=len(bounds),new_triangles=len(enc[0x42])//4,source_bvh_stats=stats,existing_active_collision_preserved=True,no_leaf_box_colliders=True)

def sidecar(pak):
    raw=SOURCE.with_suffix('.stbsp').read_bytes();offs=[struct.unpack_from('<2Q',raw,168+i*16) for i in range(6)];blocks=[bytearray(raw[o:o+n*(24 if i in (1,4) else 1)]) for i,(o,n) in enumerate(offs)]
    added=[]
    for a in pak.assets:
        if a['type']!='matl':continue
        spec,_=pak.material(a)
        if spec['name'].endswith('_colpass') or spec['name'].endswith(('_shadow','_prepass','_vsm')):continue
        blocks[1].extend(struct.pack('<2IQ2I',len(blocks[0]),0,a['guid'],0,0));blocks[0].extend(spec['name'].encode()+b'\0');added.append(spec['name'])
    header=bytearray(raw[:392]);at=392
    for i in (1,2,3,0,4,5):struct.pack_into('<2Q',header,168+i*16,at,len(blocks[i])//24 if i in (1,4) else len(blocks[i]));at+=len(blocks[i])
    TARGET.with_suffix('.stbsp').write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)));return added

def build():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    assert json.loads((BASE/'mod.json').read_text())['Version']=='0.1.44'
    props=select();data,mats,placements=geometry(props);np.savez(OUT/'source-geometry.npz',data=data,materials=mats)
    mapping,pak=materials(sorted(set(mats)));print('Prepared 20 full-size firs, 20280 triangles, resident native cutout assets.',flush=True)
    ids=(1,2,3,5,0xe,0x1e,0x2b,0x2c,0x49,0x4f,0x50,0x51,0x52,0x53,0x62,0x64,0x69,0x7b,0x42,0x44,0x45,0x60,0x5c,0x5d,0x5e,0x5f,0x57,0x59,0x7c,0x7e,0x7f)
    l=read_lumps(SOURCE,ids);scene=[];casters=[]
    for mi,r,raw,vi,tri in mesh_faces(l):
        si=r[-2];tex=struct.unpack_from('<h',l[0x52],si*12)[0]
        from optimize_portalfree_render import material_name
        name=material_name(l,tex);scene.append(tri[:,[0,2,1]]);casters.extend([not (r[-1]&0x10 or name.endswith('/phase_runner_sky'))]*len(tri))
    lighting.BAKE=P/'fir-lighting';new_casters=np.asarray([not m.startswith(LEAVES) for m in mats],np.uint8)
    lightuv,page,norm,light,lightreport=lighting.bake_catwalks(np.concatenate(scene),np.asarray(casters,np.uint8),data[:,:,:3],corner_normals=data[:,:,3:6],new_casters=new_casters)
    texchanges,texids=add_texture_rows(l,mapping);buffers={i:bytearray(l[i]) for i in (3,0x1e,0x49,0x4f,0x50,0x51,0x52,0xe,0x7b)};buffers.update(texchanges)
    tan,mirror=tangents(data[:,:,:3],data[:,:,3:6],data[:,:,6:8]);oldpages=len(l[0x53])//8;first_new=len(l[0x50])//28
    for mat in np.unique(mats):
        for pg in np.unique(page[mats==mat]):
            selection=np.flatnonzero((mats==mat)&(page==pg))
            for begin in range(0,len(selection),10000):
                sel=selection[begin:begin+10000];base=len(buffers[0x49])//44;si=len(buffers[0x52])//12
                for ti in sel:
                    for j in range(3):
                        pi=len(buffers[3])//12;ni=len(buffers[0x1e])//12;buffers[3].extend(data[ti,j,:3].tobytes());buffers[0x1e].extend(np.array([data[ti,j,3:6],tan[ti,j]],'<f4').tobytes());buffers[0x49].extend(struct.pack('<2I2f4B4f2I',pi,ni,*data[ti,j,6:8],255,255,255,255,*lightuv[ti,j],0,0,(ni+1)|(int(mirror[ti,j])<<31),0))
                buffers[0x52].extend(struct.pack('<3hHI',texids[mat],oldpages+int(pg),-1,len(sel)*3-1,base))
                for at in range(0,len(sel),256):
                    chosen=sel[at:at+256];raw=np.arange(at*3,(at+len(chosen))*3,dtype='<u2').reshape(-1,3)[:,[0,2,1]];first=len(buffers[0x4f])//2;buffers[0x4f].extend(raw.tobytes())
                    if len(chosen)&1:buffers[0x4f].extend(struct.pack('<3H',*[int(raw[-1,-1])]*3))
                    record=bytearray(l[0x50][:28]);struct.pack_into('<I3H',record,0,first,len(chosen),int(raw.min()),int(raw.max()-raw.min()));struct.pack_into('<H',record,22,si);struct.pack_into('<I',record,24,0x100a00);buffers[0x50].extend(record)
                    xyz=data[chosen,:,:3];lo=xyz.min((0,1))-.02;hi=xyz.max((0,1))+.02;c=(lo+hi)/2;e=(hi-lo)/2;buffers[0x51].extend(struct.pack('<8f',*c,float(np.linalg.norm(e))+.02,*e,0))
    buffers.update({i:l[i]+light[i] for i in (0x53,0x62,0x69)})
    coll,pos,cproof=collision({**l,**buffers},props);buffers[3].extend(pos);buffers.update(coll)
    schanges,sproof=shadows(l,collections.Counter(),data[new_casters.astype(bool),:,:3]);buffers.update(schanges)
    count=len(buffers[0x50])//28;struct.pack_into('<I',buffers[0xe],28,count);nodes,refs,obj=build_camera_visibility(buffers[0x51],struct.pack('<'+'H'*count,*range(count)));buffers.update({0x77:nodes,0x78:refs,0x79:obj})
    ordered,order,inverse=reorder({**l,**buffers});buffers.update(ordered);validate_index_padding(buffers[0x50],buffers[0x4f],buffers[0x52]);compact(SOURCE,TARGET,buffers);budget=enforce_camera_bypass_budget(TARGET)
    if budget['static_batch_runs']>=512 or budget['native_padded_indices']>WORLD_INDEX_CAPACITY*.95:raise ValueError('Draw margin exceeded')
    added=sidecar(pak);report=dict(version=VERSION,source_version='0.1.44',source_bsp_sha256=digest(SOURCE),restored_placements=20,new_triangles=len(data),source_placements=placements,new_meshes=[inverse[i] for i in range(first_new,count)],retained_meshes=[inverse[i] for i in range(first_new)],budget=budget,collision=cproof,light_bake=lightreport,shadow=sproof,resident_added_materials=added,new_connected_portals=0,original_positions_rotations_scales_and_uvs_preserved=True,existing_lightmaps_and_character_lighting_preserved=True,canopy_shadow_cards_excluded=True,client_appearance_verified=False,elapsed_seconds=time.monotonic()-start)
    (OUT/'trees.json').write_text(json.dumps(report,indent=2))
    for f in BASE.rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(BASE);dest=PACKAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True);actual=TARGET if rel.as_posix()=='mod/maps/mp_phase_runner.bsp' else TARGET.with_suffix('.stbsp') if rel.as_posix()=='mod/maps/mp_phase_runner.stbsp' else f
        if dest.exists():dest.unlink()
        if actual.stat().st_size>10*1024*1024 and actual.suffix in ('.bsp','.stbsp','.rpak'):os.link(actual,dest)
        else:shutil.copy2(actual,dest)
    shutil.copy2(MATERIALS/'build/phase_runner_firs.rpak',PACKAGE/'paks/phase_runner_firs.rpak');cfg=json.loads((PACKAGE/'paks/rpak.json').read_text());cfg['Postload']['phase_runner_firs.rpak']='mp_coliseum.rpak';(PACKAGE/'paks/rpak.json').write_text(json.dumps(cfg,indent=2))
    mod=json.loads((PACKAGE/'mod.json').read_text());mod.update(Version=VERSION,Description='Phase Runner with 20 original full-size fir trees, native cutout leaves and source trunk collision.');(PACKAGE/'mod.json').write_text(json.dumps(mod,indent=2));shutil.copy2(OUT/'trees.json',PACKAGE/'trees.json')
    status=json.loads((PACKAGE/'build-status.json').read_text());status['tree_release']=report;status['render_triangles']=budget['real_triangles'];status['render_repair']['world_meshes']=count;status['world_draw_budget_repair']['after']=budget;(PACKAGE/'build-status.json').write_text(json.dumps(status,indent=2))
    script=PACKAGE/'mod/scripts/vscripts/_phase_runner_preview.nut';s=script.read_text();s=s.replace('\t\tPhaseRunner_ArtSupportChecks()','\t\tPhaseRunner_ArtSupportChecks()\n\t\tPhaseRunner_TreeChecks()',1)
    def vec(p):return '< '+', '.join(f'{v:.6f}' for v in p)+' >'
    probes=cproof['probes'];s+='\nvoid function PhaseRunner_TreeChecks()\n{\n\tarray<vector> starts = [ '+', '.join(vec(p['start']) for p in probes)+' ]\n\tarray<vector> ends = [ '+', '.join(vec(p['end']) for p in probes)+' ]\n\tint hits = 0\n\tfor ( int i = 0; i < starts.len(); i++ )\n\t{\n\t\tTraceResults r = TraceLine( starts[i], ends[i], null, TRACE_MASK_SOLID_BRUSHONLY, TRACE_COLLISION_GROUP_NONE )\n\t\tif ( r.fraction < 1.0 && !r.startSolid )\n\t\t\thits++\n\t}\n\tprintl( "Phase Runner tree checks: " + hits + "/" + starts.len() + " passed" )\n}\n';script.write_text(s)
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_placements','new_meshes','retained_meshes','collision')},indent=2),flush=True)

if __name__=='__main__':build()
