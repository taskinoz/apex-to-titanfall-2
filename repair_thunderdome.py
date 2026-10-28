"""Isolated Thunderdome collision/material repair, based on immutable 0.1.1."""
import argparse
import collections
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'output/thunderdome-repair-2026-10-29'
WORK = Path('D:/Games/ApexToTitanfallWork/new-arena-ports/thunderdome')
RETAIL = Path('D:/Games/ApexToTitanfallWork/apex-current/mp_rr_thunderdome')
BASE = OUT/'baseline/ArenaThunderdome'
CANDIDATE = OUT/'candidate/ArenaThunderdome'


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.writing')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def stage():
    spec = next(p for p in json.loads((ROOT/'thunderstore/packages.json').read_text()) if p['mod']=='ArenaThunderdome')
    source = ROOT/'output/releases'/spec['tag']/spec['asset']
    if digest(source) != spec['sha256']:
        raise ValueError('Published source archive changed')
    if not BASE.exists():
        BASE.mkdir(parents=True)
        with zipfile.ZipFile(source) as z:
            for item in z.infolist():
                p = PurePosixPath(item.filename)
                if p.parts[0]!='ArenaThunderdome' or '..' in p.parts or '\\' in item.filename:
                    raise ValueError('Unsafe source archive')
                if item.is_dir():
                    continue
                target = BASE.joinpath(*p.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, target.open('xb') as dest:
                    shutil.copyfileobj(src, dest)
    if not CANDIDATE.exists():
        shutil.copytree(BASE, CANDIDATE, copy_function=os.link)
    write(OUT/'baseline.json', dict(version=spec['version'], archive_sha256=spec['sha256'],
          runtime_sha256={p.relative_to(BASE).as_posix(): digest(p) for p in BASE.rglob('*')
                          if p.is_file() and (p.name=='mod.json' or p.relative_to(BASE).parts[0] in ('mod','paks'))}))
    print('Published 0.1.1 staged; candidate uses detach-before-write hardlinks', flush=True)


def shared_materials():
    mapping = json.loads((WORK/'materials/mapping.json').read_text())
    names = [n for n in mapping['missing'] if not n.isdecimal() and n not in ('_default','thunderdome_sky')]
    destination = (OUT/'shared-export').resolve()
    destination.mkdir(parents=True, exist_ok=True)
    inventory = destination/'all-assets.csv'
    if inventory.exists():
        wanted = {int(n): n for n in mapping['missing'] if n.isdecimal()}
        aliases = {}
        for row in csv.DictReader(inventory.open(encoding='utf-8-sig')):
            if row['type']=='matl' and int(row['guid'],16) in wanted:
                base = row['asset_name'].replace('\\','/').rsplit('/',1)[-1].removesuffix('.rpak')
                for shader in ('_wldc','_rgdp','_rgdc','_sknp','_wld'):
                    if base.endswith(shader):base=base[:-len(shader)];break
                aliases[wanted[int(row['guid'],16)]]=base
        write(OUT/'numeric-material-aliases.json', aliases)
        names = sorted(set(aliases.values()))
    packs = Path('D:/Games/Apex/paks/Win64')
    inputs = [packs/n for n in ('common_early.rpak','common.rpak','common(01).rpak',
                                'common_mp.rpak','common_mp(01).rpak','mp_rr_thunderdome.rpak')]
    tool = Path('D:/Games/ApexToTitanfallWork/rsx-latest/bin/Release_NoGui/rsx.exe')
    with (destination/'export.log').open('w') as log:
        result = subprocess.run([str(tool), '-nogui', '-nocachedb', '-export', '-matltextures',
            '--texnames','semantic','--exportformats','txtr=DDS (Highest Mip),matl=Uber (Raw)', '--exporttypes','matl',
            '--exportfilter', ','.join(names), '--exportthreads','4','--exportdir',str(destination),
            *map(str,inputs)], cwd=destination, stdout=log, stderr=subprocess.STDOUT)
    print('Shared material export exit:', result.returncode, flush=True)
    if result.returncode:
        raise RuntimeError('Shared export failed; inspect private export.log')
    with (destination/'list.log').open('w') as log:
        subprocess.run([str(tool),'-nogui','-nocachedb','--list',str(destination/'all-assets.csv'),
            '--listformat','csv',*map(str,inputs)],cwd=destination,stdout=log,stderr=subprocess.STDOUT,check=True)


def shared_shaders():
    destination=(OUT/'shared-shaders').resolve();destination.mkdir(parents=True,exist_ok=True)
    packs=Path('D:/Games/Apex/paks/Win64')
    inputs=[packs/n for n in ('common_early.rpak','common.rpak','common(01).rpak',
                             'common_mp.rpak','common_mp(01).rpak','mp_rr_thunderdome.rpak')]
    tool=Path('D:/Games/ApexToTitanfallWork/rsx-latest/bin/Release_NoGui/rsx.exe')
    with (destination/'export.log').open('w') as log:
        subprocess.run([str(tool),'-nogui','-nocachedb','-export','--exporttypes','shdr,shds',
            '--exportformats','shdr=Raw,shds=MSW',*map(str,inputs)],cwd=destination,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('Shared source shaders exported',flush=True)


def geometry(placement, cache):
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    import numpy as np
    from read_vg_static import load
    from stage_prop_geometry import rotation
    key=(placement['folder'],placement['lod'],placement['skin'],placement['triangles'])
    if key not in cache:
        sections,slots,skins=load(placement['folder'],placement['lod'],True)
        sections=[np.asarray(s,'f4').reshape(-1,3,12) for s in sections]
        skin=skins[min(placement['skin'],len(skins)-1)]
        def allowed(slot):
            n=skin[slot].lower()
            return n not in ('toolsblack','toolsskybox') and not any(w in n for w in ('godray','ambient_occlusion','atmosphere','start_barrier'))
        if sum(len(s) for s,k in zip(sections,slots) if allowed(k))!=placement['triangles']:
            simple=WORK/'simplified'/f'{Path(placement["folder"]).name}_lod{placement["lod"]}_e0.01.npz'
            if simple.exists():
                with np.load(simple) as z:sections=[z[str(i)] for i in range(len(z.files))]
        if sum(len(s) for s,k in zip(sections,slots) if allowed(k))!=placement['triangles']:
            raise ValueError('Cannot reproduce selected render geometry for '+placement['model'])
        cache[key]=np.concatenate([s[:,:,:3] for s,k in zip(sections,slots) if len(s) and allowed(k)])
    return cache[key]@np.asarray(rotation(placement['angles'])).T*placement['scale']+placement['origin']


def probe_plan():
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    import numpy as np
    scene=json.loads((WORK/'scene.json').read_text());physics=json.loads((WORK/'physics.json').read_text())
    missing={p['index'] for p in physics['missing']}
    groups=collections.defaultdict(list)
    for p in scene['placements']:
        if p.get('backdrop') or p['solid'] not in (2,6,7):continue
        groups[(p['index'] in missing,p['model'])].append(p)
    cache={};probes=[];failures=[]
    for (absent,model),placements in sorted(groups.items(),reverse=True):
        if not absent and not any(w in model for w in ('floor','stairs','wall','rail','pipe','crate','building','bridge','terrain')):continue
        placements.sort(key=lambda p:sum(v*v for v in p['origin'][:2]))
        for p in placements[:(6 if absent else 1)]:
            try:tri=geometry(p,cache)
            except ValueError as e:failures.append(str(e));continue
            normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);area=np.linalg.norm(normals,axis=1)
            valid=np.flatnonzero(area>4)
            if not len(valid):continue
            top=valid[np.abs(normals[valid,2])>.6*area[valid]]
            k=int(top[np.argmax(tri[top].mean(1)[:,2])] if len(top) else valid[np.argmax(area[valid])])
            n=normals[k]/area[k]
            if n[2]<0:n=-n
            point=tri[k].mean(0)
            probes.append(dict(index=p['index'],model=model,missing_exported_collider=absent,
                surface=point.tolist(),normal=n.tolist(),start=(point+n*24).tolist(),end=(point-n*24).tolist()))
    write(OUT/'probe-plan.json',dict(probes=probes,geometry_failures=failures))
    print('Planned native surface probes:',len(probes),'geometry failures:',len(failures),flush=True)


def native_probes(label):
    sys.path.insert(0,str(ROOT/'test-harness'))
    from harness import Controller
    c=Controller()
    if c.request('/status').get('contexts',{}).get('client',{}).get('level')!='mp_thunderdome':
        c.load('mp_thunderdome','ps',240)
    c.wait_map('mp_thunderdome',30)
    c.command('ui','console',command='script SetServerVar("gameEndTime", Time()+1800)')
    plan=json.loads((OUT/'probe-plan.json').read_text());rows=[]
    for p in plan['probes']:
        r=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),p['start']+p['end'])))['data']
        distance=sum((a-b)**2 for a,b in zip(r['end'],p['surface']))**.5
        rows.append(dict(p,native=r,distance=distance,contact=not r['startSolid'] and r['fraction']<1 and distance<8))
        if len(rows)%30==0:print(label,'native probes',len(rows),'/',len(plan['probes']),flush=True)
    write(OUT/(label+'-probes.json'),dict(probes=rows))
    print(label,'contacts',sum(r['contact'] for r in rows),'/',len(rows),flush=True)


def collision():
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    import numpy as np
    from repair_preview_index_padding import read_lumps
    from compact_preview_bsp import compact
    from native_triangle_collision import encode
    from extend_prop_collision import pack_grid
    from build_center_detail import active
    from analyse_visibility import render_triangles
    baseline=BASE/'mod/maps/mp_thunderdome.bsp'
    target=CANDIDATE/'mod/maps/mp_thunderdome.bsp'
    scene=json.loads((WORK/'scene.json').read_text());physics=json.loads((WORK/'physics.json').read_text())
    l=read_lumps(baseline,(1,3,0x42,0x44,0x45,0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x60))
    original=active(l);heads=list(__import__('struct').iter_unpack('<6h4i4f',l[0x45]))
    world_headers=len(heads)-sum(p['headers'] for p in physics['owners'])
    if sum(h[4] for h in heads[:world_headers])!=physics['world_triangles']:
        raise ValueError('Cannot establish original world/prop collision ownership')
    def keys(t):
        t=np.array(t,'<f4',copy=True);t[t==0]=0
        v=t.view('V12').reshape(-1,3);v.sort(axis=1)
        return v.copy().view('V36').reshape(-1)
    visible,_,_=render_triangles(baseline)
    visible_keys=set(bytes(k) for k in keys(visible))
    from scipy.spatial import cKDTree
    render_vertices=np.unique(visible.reshape(-1,3),axis=0);tree=cKDTree(render_vertices)
    face_tree=cKDTree(visible.mean(1))
    cache={};groups=[];owners=[];not_drawn=[]
    for p in scene['placements']:
        if p.get('backdrop') or p['solid'] not in (1,2,6,7):continue
        t=geometry(p,cache).astype('<f4')
        if not all(bytes(k) in visible_keys for k in keys(t)):
            distance,nearest=tree.query(t.reshape(-1,3))
            snapped=render_vertices[nearest].reshape(t.shape)
            # Earlier coplanar-surface repairs moved a few meshes by 0.12 units.
            # Snap only if the complete resulting face actually exists on disk.
            if distance.max()>.25 or not all(bytes(k) in visible_keys for k in keys(snapped)):
                _,faces=face_tree.query(t.mean(1));candidate=visible[faces]
                delta=np.linalg.norm(t[:,:,None,:]-candidate[:,None,:,:],axis=3)
                vertex=delta.argmin(2)
                snapped=np.take_along_axis(candidate,vertex[:,:,None],axis=1)
                if np.linalg.norm(t-snapped,axis=2).max()>.25 or not all(bytes(k) in visible_keys for k in keys(snapped)):
                    not_drawn.append(dict(index=p['index'],max_vertex_distance=float(distance.max())));continue
            t=snapped
        valid=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)>1e-5;t=t[valid]
        first=len(groups)
        groups.extend(t[i:i+96] for i in range(0,len(t),96))
        owners.append(dict(index=p['index'],model=p['model'],first_header=len(heads)+first,
                           headers=len(groups)-first,triangles=len(t),source_solid=p['solid']))
        if len(owners)%500==0:print('Render-matched colliders',len(owners),flush=True)
    if not_drawn:raise ValueError('Source model geometry differs from mounted visuals: '+str(not_drawn[:12]))
    encoded,new_bounds=encode(groups)
    import struct
    first_vertex=len(l[3])//12;first_word=len(l[0x42])//4;first_node=len(l[0x44])//16
    appended=bytearray()
    for h in struct.iter_unpack('<6h4i4f',encoded[0x45]):
        h=list(h);h[6]+=first_vertex;h[7]+=first_word;h[8]+=first_node;appended.extend(struct.pack('<6h4i4f',*h))
    if len(heads)+len(groups)>65535:raise ValueError('Native triangle-header capacity exceeded')
    changes={k:l[k]+encoded[k] for k in (3,0x42,0x44,0x60)}
    changes[0x45]=l[0x45]+appended
    pos=np.frombuffer(l[3],'<f4').reshape(-1,3);words=np.frombuffer(l[0x42],'<u4')
    keep_world=[i for i in range(world_headers) if (0x40,i) in original]
    bounds=[]
    for i in keep_world:
        h=heads[i];w=words[h[7]:h[7]+h[4]];a=w&1023
        tri=pos[h[6]+np.stack((a,a+(w>>10&127),a+(w>>17&127)),1)]
        bounds.append((tri.min((0,1)).tolist(),tri.max((0,1)).tolist()))
    # The sole pre-owner brush is the unreachable sentinel. Source prop hulls
    # remain serialized for provenance but are removed from the active grid.
    source_brushes=sum(p['brushes'] for p in physics['owners'])
    first_prop_brush=len(l[0x5c])//32-source_brushes
    if first_prop_brush!=1:raise ValueError('Unexpected source brush ownership prefix')
    brush_ids=[i for i in range(first_prop_brush) if (0,i) in original]
    brush_bounds=[]
    for i in brush_ids:
        h=struct.unpack_from('<3f2BH3fI',l[0x5c],32*i)
        brush_bounds.append(([h[k]-h[k+6] for k in range(3)],[h[k]+h[k+6] for k in range(3)]))
    bounds+=new_bounds
    grid=pack_grid(brush_bounds+bounds);sets=bytearray(grid[0x57]);prims=bytearray(grid[0x59])
    triangle_ids=keep_world+list(range(len(heads),len(heads)+len(groups)))
    def remap(word):
        i=(word>>8)&65535
        return ((brush_ids[i]<<8)|(word&255)) if i<len(brush_ids) else ((0x40<<24)|(triangle_ids[i-len(brush_ids)]<<8)|(word&255))
    for at in range(0,len(prims),4):struct.pack_into('<I',prims,at,remap(struct.unpack_from('<I',prims,at)[0]))
    for at in range(0,len(sets),8):
        if struct.unpack_from('<H',sets,at+2)[0]==1:struct.pack_into('<I',sets,at+4,remap(struct.unpack_from('<I',sets,at+4)[0]))
    grid[0x57]=sets;grid[0x59]=prims;changes.update(grid)
    temp=target.with_suffix('.collision.bsp');compact(baseline,temp,changes);temp.replace(target)
    expected={(0,i) for i in brush_ids}|{(0x40,i) for i in triangle_ids}
    if active(read_lumps(target,(0x57,0x59)))!=expected:raise ValueError('Active collision grid differs from intended ownership')
    write(OUT/'collision-repair.json',dict(owners=owners,physical_props=len(owners),
        solid_bsp_bridge_props=sum(p['source_solid']==1 for p in owners),
        collision_triangles=sum(p['triangles'] for p in owners),new_headers=len(groups),world_headers_preserved=len(keep_world),
        source_prop_headers_disabled=len(heads)-world_headers,source_prop_brushes_disabled=source_brushes,
        every_new_triangle_verified_in_native_render=True,world_collision_preserved=True,
        old_render_vertex_indices_preserved=True,candidate_bsp_sha256=digest(target)))
    print('Verified render-matched collision:',len(owners),'physical props;',len(groups),'new headers',flush=True)


def materials():
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    from optimize_preview_textures import dds,FORMATS
    source=WORK/'materials';out=OUT/'materials';assets=out/'assets'
    if digest(source/'build/thunderdome_world.rpak')!=digest(BASE/'paks/thunderdome_world.rpak'):
        raise ValueError('Working material project differs from the immutable released baseline')
    if not assets.exists():shutil.copytree(source/'assets',assets,copy_function=os.link)
    manifest=json.loads((source/'build.json').read_text())
    manifest.update(assetsDir=str(assets.resolve()),outputDir=str((out/'build').resolve()))
    mapping=json.loads((source/'mapping.json').read_text())
    aliases=json.loads((OUT/'numeric-material-aliases.json').read_text())
    exported=OUT/'shared-export/exported_files/material';index=collections.defaultdict(list)
    for path in exported.glob('*/*.json'):
        if path.stem!=path.parent.name or '_colpass_' in path.stem:continue
        spec=json.loads(path.read_text());name=spec.get('name','').rsplit('/',1)[-1].lower()
        index[name].append((path,spec))
    files={f['_path']:f for f in manifest['files']};rows=[];deferred={}
    converted={}
    for name,count in mapping['missing'].items():
        key=aliases.get(name,name).lower();choices=index.get(key,[])
        if not choices:deferred[name]='No original material found';continue
        path,spec=sorted(choices,key=lambda v:('_wldc' not in v[0].stem,'_rgdp' not in v[0].stem))[0]
        types=spec.get('$textureTypes',{});channels={}
        for slot,semantic in types.items():channels.setdefault(semantic,[]).append(slot)
        if any(s in key for s in ('transparent','_trans','stencil','decals','exhaust','objective_border')):
            deferred[name]='Requires separate coverage/emission shader conversion';continue
        if len(channels.get('_col',[]))!=1:
            deferred[name]='Layered material requires native blend conversion';continue
        textures={};proof=[]
        for semantic,slot,label in (('_col','0','albedo'),('_nml','1','normal'),('_gls','2','gloss'),('_spc','3','spec')):
            if semantic not in channels:continue
            ref=spec['$textures'][channels[semantic][0]]
            src=path.parent/(Path(ref).stem+'.dds')
            if not src.exists():raise ValueError('Missing resolved DDS '+str(src))
            identity=(digest(src),semantic)
            if identity not in converted:
                targetpath=f'texture/thunderdome/repair_{name.lower()}_{label}.rpak'
                dest=(assets/targetpath).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True)
                info=dds(src.read_bytes());scale=min(1,1024/max(info['width'],info['height']))
                size=[max(1,int(info[k]*scale)) for k in ('width','height')]
                temp=out/'conversion'/f'{name.lower()}_{label}';temp.mkdir(parents=True,exist_ok=True)
                fmt=FORMATS[info['format']][0]
                run=subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0',
                    '-f',fmt,'-dx10','-w',str(size[0]),'-h',str(size[1]),'-o',str(temp.resolve()),str(src.resolve())],capture_output=True,text=True)
                if run.returncode:raise ValueError(run.stdout+run.stderr)
                raw=bytearray((temp/(src.stem+'.dds')).read_bytes())
                if semantic=='_col':
                    import struct
                    f=struct.unpack_from('<I',raw,128)[0]
                    if f in (71,74,77,98):struct.pack_into('<I',raw,128,f+1)
                dest.write_bytes(raw);files[targetpath]={'_type':'txtr','_path':targetpath,'$disableStreaming':True}
                converted[identity]=targetpath
            textures[slot]=converted[identity]
            proof.append(dict(semantic=semantic,source=src.relative_to(OUT).as_posix(),source_sha256=identity[0],target=textures[slot]))
        if '0' not in textures:deferred[name]='No resolved base colour';continue
        paths=[f for f in files if f.startswith('material/') and f.endswith('.rpak') and
               json.loads((assets/f).with_suffix('.json').read_text()).get('name') in
               (mapping['materials'][name]['name'],mapping['materials'][name]['name']+'_colpass')]
        if len(paths)!=2:raise ValueError('Expected primary and colour pass for '+name+': '+str(paths))
        for f in paths:
            target=(assets/f).with_suffix('.json');native=json.loads(target.read_text())
            native['$textures'].update(textures);native['surfaceProp']=spec.get('surfaceProp','metal')
            write(target,native)
        rows.append(dict(material=name,source_material=spec['name'],triangles=count,textures=proof,paths=paths))
        mapping['materials'][name].update(recovered=True,textures=textures,source=aliases.get(name,name),
                                         native_source_channels='Shared-pack original PBR maps; neutral tint, no unverified DXIL constants')
        print('Recovered original material:',name,flush=True)
    # Keep existing dependency order, inserting new resident textures first.
    original={f['_path'] for f in manifest['files']}
    manifest['files']=[f for p,f in files.items() if p not in original]+manifest['files']
    write(out/'build.json',manifest);write(out/'mapping.json',mapping)
    write(OUT/'material-repair.json',dict(materials=rows,deferred=deferred,
        recovered_materials=len(rows),recovered_triangles=sum(r['triangles'] for r in rows),
        unique_new_textures=len(converted),unchanged_material_dependencies=True,
        limitation='Retail DXIL constant reflection, translucent and layered source shaders remain separate work.'))
    with (out/'build.log').open('w') as log:
        subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str((out/'build.json').resolve())],stdout=log,stderr=subprocess.STDOUT,check=True)
    sourcepak=out/'build/thunderdome_world.rpak'
    target=CANDIDATE/'paks/thunderdome_world.rpak'
    temp=target.with_suffix('.new.rpak');shutil.copy2(sourcepak,temp);temp.replace(target)
    print('Material pack built:',sourcepak.stat().st_size,flush=True)


def verify():
    import struct
    from extract_native_material import NativePak
    from build_phase_runner_presentation import guid
    from repair_preview_index_padding import read_lumps
    report=json.loads((OUT/'material-repair.json').read_text())
    altered={guid(p) for r in report['materials'] for p in r['paths']}
    before=NativePak(BASE/'paks/thunderdome_world.rpak');after=NativePak(CANDIDATE/'paks/thunderdome_world.rpak')
    index={a['guid']:a for a in after.assets};materials=textures=0
    for a in before.assets:
        assert a['guid'] in index,'Original asset absent'
        b=index[a['guid']];assert a['type']==b['type']
        if a['type']=='matl' and a['guid'] not in altered:
            assert before.material(a)==after.material(b),'Unrelated material changed';materials+=1
        elif a['type']=='txtr':
            x=before.address(a['header']);y=after.address(b['header']);n=struct.unpack_from('<I',before.data,x+24)[0]
            assert before.data[x+16:x+36]==after.data[y+16:y+36]
            u=before.address(a['cpu']);v=after.address(b['cpu'])
            assert before.data[u:u+n]==after.data[v:v+n],'Original texture changed';textures+=1
    for r in report['materials']:
        for texture in r['textures']:assert guid(texture['target']) in index,'Recovered texture not packed'
    lids=list(range(128));a=read_lumps(BASE/'mod/maps/mp_thunderdome.bsp',lids);b=read_lumps(CANDIDATE/'mod/maps/mp_thunderdome.bsp',lids)
    # Compaction relocates absolute pointers in the game-lump directory.
    from compact_preview_bsp import relocate_game_lump
    def lump_offset(path,index):
        with path.open('rb') as f:f.seek(16+index*16);return struct.unpack('<I',f.read(4))[0]
    assert relocate_game_lump(a[35],lump_offset(BASE/'mod/maps/mp_thunderdome.bsp',35),
        lump_offset(CANDIDATE/'mod/maps/mp_thunderdome.bsp',35))==b[35]
    changed={k for k in lids if k!=35 and a[k]!=b[k]}
    allowed={3,0x42,0x44,0x45,0x55,0x56,0x57,0x58,0x59,0x5a,0x60}
    assert changed<=allowed,('Noncollision lump changed',changed-allowed)
    assert b[3].startswith(a[3]),'Original render position indices changed'
    for relative,sha in json.loads((OUT/'baseline.json').read_text())['runtime_sha256'].items():
        assert digest(BASE/relative)==sha,'Baseline was modified'
    write(OUT/'offline-verification.json',dict(original_materials_unchanged=materials,
        original_textures_unchanged=textures,original_assets_preserved=len(before.assets),
        recovered_material_guids=len(altered),new_resident_texture_assets=len(after.assets)-len(before.assets),
        changed_collision_lumps=sorted(changed),render_geometry_and_lightmaps_unchanged=True,
        world_entities_spawns_safety_volumes_unchanged=True,published_baseline_hashes_verified=True))
    print('Offline material, geometry, safety and immutable baseline checks passed',flush=True)


def acceptance():
    import time
    sys.path.insert(0,str(ROOT/'tools/lighting-python'))
    sys.path.insert(0,str(ROOT/'test-harness'))
    import numpy as np
    from harness import Controller
    from validate_anniversary_native import postmatch
    c=Controller()
    if c.session['profile']!='R2Anniversary14':raise ValueError('Wrong isolated profile')
    c.wait_map('mp_thunderdome',60)
    mounted=next(p.parent for p in (Path(c.request('/status')['profile'])/'mods').glob('*/mod.json')
                 if json.loads(p.read_text(encoding='utf-8-sig')).get('Name')=='ArenaThunderdome')
    for p in CANDIDATE.rglob('*'):
        rel=p.relative_to(CANDIDATE)
        if p.is_file() and (p.name=='mod.json' or rel.parts[0] in ('mod','paks')):
            assert digest(p)==digest(mounted/rel),'Mounted runtime mismatch'
    def living():
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            s=c.request('/status');p=s.get('contexts',{}).get('client',{})
            if not s['game_running']:raise RuntimeError('Owned game exited')
            if p.get('level')=='mp_thunderdome' and p.get('alive') and p.get('health',0)>0:return
            time.sleep(.5)
        raise RuntimeError('No living native player')
    scene=json.loads((WORK/'scene.json').read_text());cache={};bridges=[]
    for p in scene['placements']:
        if p['solid']!=1 or p.get('backdrop'):continue
        t=geometry(p,cache);n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);area=np.linalg.norm(n,axis=1)
        valid=np.flatnonzero(area>1);k=int(valid[np.argmax(area[valid])]);normal=n[k]/area[k];point=t[k].mean(0)
        if normal[2]<0:normal=-normal
        values=(point+normal*.5).tolist()+(point-normal*.5).tolist()
        r=c.command('server','trace',**dict(zip(('px','py','pz','ex','ey','ez'),values)))['data']
        bridges.append(dict(index=p['index'],model=p['model'],native=r))
    assert len(bridges)==14 and all(p['native']['fraction']<1 for p in bridges),'Bridge contact missing'
    write(OUT/'bridge-contacts.json',bridges)
    reports=[]
    # This preview has no CTF flags / Hardpoint objectives. Do not certify
    # unsupported modes merely because their spawn markers load successfully.
    for mode in ('ps','ffa'):
        if mode!='ps':c.load('mp_thunderdome',mode,240)
        living();time.sleep(3);r=c.command('server','mode_check')['data']
        assert r['mode']==mode and len(r['liveSpawns'])==88
        assert all(p['clear'] and p['supported'] for p in r['liveSpawns']),'Invalid spawn'
        assert all(p['valid'] for p in r.get('objectives',[])),'Missing mode objective'
        for team in ((2,3) if mode!='ffa' else ()):
            c.command('server','respawn',team=team);living()
        c.command('ui','console',command='+attack');time.sleep(.35);c.command('ui','console',command='-attack');time.sleep(1);living()
        reports.append(r);print('Native mode passed:',mode,'88 supported and clear spawns',flush=True)
    postmatch(c,'Thunderdome collision/material repair')
    c.load('mp_coliseum','ps',240);time.sleep(3)
    c.load('mp_thunderdome','ps',240);living()
    logs=c.export_logs()
    assert not logs['script_errors'] and not logs['native_crashes'],'Native errors recorded'
    write(OUT/'runtime-validation.json',dict(passed=True,version='0.2.0',modes=reports,
        bridge_contacts=len(bridges),both_team_respawns=True,weapon_fire_exercised=True,
        postmatch_lobby=True,stock_and_converted_reload=True,mounted_runtime_hash_verified=True,
        logs=logs,single_client_only=True))
    print('Native bridge, PS/FFA, postmatch and stock/map reload acceptance passed',flush=True)


def finalize():
    from package_player_mods import RELEASES,runtime_files,write_player_zip
    release=ROOT/'output/ArenaThunderdome-0.2.0-Northstar.zip'
    if release.exists():raise ValueError('New release archive already exists; do not overwrite it')
    proof=json.loads((OUT/'runtime-validation.json').read_text())
    assert proof['passed'] and proof['postmatch_lobby'] and proof['stock_and_converted_reload']
    offline=json.loads((OUT/'offline-verification.json').read_text())
    col=json.loads((OUT/'collision-repair.json').read_text());mat=json.loads((OUT/'material-repair.json').read_text())
    assert digest(CANDIDATE/'mod/maps/mp_thunderdome.bsp')==col['candidate_bsp_sha256']
    package=ROOT/'northstar/ArenaThunderdome';backup=OUT/'working-metadata-before'
    backup.mkdir(exist_ok=True)
    for p in package.iterdir():
        if p.is_file() and not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
    mod=json.loads((BASE/'mod.json').read_text());mod['Version']='0.2.0'
    write(CANDIDATE/'mod.json',mod)
    def copy_atomic(src,dest):
        dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix(dest.suffix+'.repairing')
        shutil.copy2(src,temp);temp.replace(dest)
    for p in runtime_files(CANDIDATE):copy_atomic(p,package/p.relative_to(CANDIDATE))
    captures=json.loads((OUT/'candidate-captures.json').read_text())
    shot=next(r['capture']['path'] for r in captures if r['name']=='centre')
    copy_atomic(Path(shot),package/'screenshot.png')
    from package_player_mods import player_readme
    (package/'README.md').write_text(player_readme('ArenaThunderdome'),encoding='utf-8')
    status=json.loads((package/'build-status.json').read_text())
    status.update(version='0.2.0',bsp_sha256=col['candidate_bsp_sha256'],client_load_verified=True,
        client_verified=True,candidate=False,release_ready=True,release_channel='local-beta',
        lighting='Existing released lightmaps and character lighting preserved; no new bake',
        collision_repair=dict(physical_props=col['physical_props'],triangles=col['collision_triangles'],
            bridge_props=col['solid_bsp_bridge_props'],world_preserved=True),
        material_repair=dict(recovered_entries=mat['recovered_materials'],triangles=mat['recovered_triangles'],
            textures=mat['unique_new_textures'],deferred=mat['deferred']),
        native_validation='docs/candidates/thunderdome/port-0.2.0/validation.json')
    status['historical_0_1_1_build']=status.pop('build')
    status['historical_0_1_1_collision']=status.pop('collision')
    status['build']=dict(bytes=(package/'mod/maps/mp_thunderdome.bsp').stat().st_size,
        collision_only_lumps_changed=offline['changed_collision_lumps'],native_verified=True)
    status['collision']=dict(active_world_headers=col['world_headers_preserved'],active_prop_headers=col['new_headers'],
        active_prop_triangles=col['collision_triangles'],world_triangles=126819,physical_props=col['physical_props'],
        ownership='docs/candidates/thunderdome/port-0.2.0/collision-repair.json')
    status['streaming_sidecar']['client_load_verified']=True
    write(package/'build-status.json',status)
    docs=ROOT/'docs/candidates/thunderdome/port-0.2.0';docs.mkdir(parents=True,exist_ok=True)
    for name in ('collision-repair.json','material-repair.json','offline-verification.json','bridge-contacts.json'):
        shutil.copy2(OUT/name,docs/name)
    before=json.loads((OUT/'before-probes.json').read_text())['probes'];after=json.loads((OUT/'after-probes.json').read_text())['probes']
    contacts=dict(samples=len(after),before_hits=sum(p['native']['fraction']<1 for p in before),
        after_hits=sum(p['native']['fraction']<1 for p in after),before_near_surface=sum(p['contact'] for p in before),
        after_near_surface=sum(p['contact'] for p in after),before_start_solid=sum(p['native']['startSolid'] for p in before),
        after_start_solid=sum(p['native']['startSolid'] for p in after),
        limitation='A hit can be an overlapping surface. Near-surface threshold is 8 units; neither count is movement certification.')
    # Publish compact diagnostic receipts, never session credentials or full raw logs.
    clean=dict(proof);clean['logs']={k:v for k,v in proof['logs'].items() if k!='path'}
    clean.update(surface_probes=contacts,offline=offline,tests_passed=8,
        unsupported_ctf='Extra CTF trial had no flag entities and stalled with server index 3 error; PS/FFA rerun passed in a fresh process.',
        captures=[dict(name=r['name'],sha256=r['capture']['sha256'],width=r['capture']['width'],height=r['capture']['height']) for r in captures],
        runtime_sha256={p.relative_to(package).as_posix():digest(p) for p in runtime_files(package)})
    write(docs/'validation.json',clean)
    for r in captures:
        shutil.copy2(r['capture']['path'],docs/(r['name']+'.png'))
    result=write_player_zip(package,release);write(OUT/'release.json',result)
    write(docs/'release.json',result)
    print('Finalized tested Thunderdome 0.2.0 player package',flush=True)


def install():
    import datetime
    from package_player_mods import runtime_files
    from map_pack_lifetime import audit
    sys.path.insert(0,str(ROOT/'test-harness'))
    from harness import Controller
    c=Controller()
    if c.session['profile']!='R2Anniversary14':raise ValueError('Unexpected owned test profile')
    c.export_logs();c.request('/stop-game',{});c.request('/shutdown',{})
    state=subprocess.run(['powershell','-NoProfile','-Command',
        "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like 'D:\\Games\\Titanfall2\\*.exe' } | Select-Object -ExpandProperty ProcessId"],capture_output=True,text=True,check=True)
    if state.stdout.strip():raise ValueError('A game-directory process remains active; do not replace the installed mod')
    profile=Path('D:/Games/Titanfall2/R2Northstar').resolve();mods=profile/'mods'
    target=mods/'ArenaThunderdome'
    if target.resolve().parent!=mods.resolve():raise ValueError('Installed mod escaped named profile')
    for p in __import__('package_player_mods').runtime_files(BASE):
        if digest(p)!=digest(target/p.relative_to(BASE)):raise ValueError('Installed baseline has unknown edits')
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=profile/'.thunderdome-repair-backups'/stamp;stage=profile/'.thunderdome-repair-staging'/stamp/'ArenaThunderdome'
    for p in (backup,stage):
        if not p.resolve().is_relative_to(profile):raise ValueError('Staging/backup escaped profile')
        p.mkdir(parents=True,exist_ok=False)
    source=ROOT/'northstar/ArenaThunderdome';expected={}
    for p in [*runtime_files(source),source/'README.md',source/'screenshot.png']:
        rel=p.relative_to(source);dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest);expected[rel.as_posix()]=digest(p)
        assert digest(dest)==expected[rel.as_posix()]
    audit(stage/'paks','mp_thunderdome')
    enabled_path=profile/'enabledmods.json';shutil.copy2(enabled_path,backup/'enabledmods.json')
    enabled=json.loads(enabled_path.read_text());old=enabled.get('ArenaThunderdome',{})
    preference=old.get('0.1.1',True) if isinstance(old,dict) else bool(old)
    enabled['ArenaThunderdome']={**({v:False for v in old} if isinstance(old,dict) else {}),'0.2.0':preference}
    kept=backup/'ArenaThunderdome';os.replace(target,kept)
    try:
        os.replace(stage,target);write(enabled_path,enabled)
    except Exception:
        if target.exists():os.replace(target,backup/'failed-candidate')
        os.replace(kept,target);shutil.copy2(backup/'enabledmods.json',enabled_path);raise
    for rel,sha in expected.items():assert digest(target/rel)==sha
    write(OUT/'installation.json',dict(version='0.2.0',installed=str(target),backup=str(kept),
        enabled=preference,runtime_sha256=expected,rollback='Close game; restore backed-up mod folder and enabledmods.json.'))
    print('Installed Thunderdome 0.2.0; original mod and preferences retained at',backup,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['stage','shared-materials','shared-shaders','probe-plan','before-probes','after-probes','collision','materials','verify','acceptance','finalize','install'])
    a=p.parse_args()
    {'stage':stage,'shared-materials':shared_materials,'shared-shaders':shared_shaders,
     'probe-plan':probe_plan,'before-probes':lambda:native_probes('before'),
     'after-probes':lambda:native_probes('after'),'collision':collision,'materials':materials,'verify':verify,'acceptance':acceptance,'finalize':finalize,'install':install}[a.action]()
