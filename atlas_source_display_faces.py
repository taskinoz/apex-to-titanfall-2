"""Freeze Apex screen artwork on the existing front animation quads.

Repack each console's resident texture atlas: three repeats of its old texture
and one region for the source screen artwork. Re-map its UVs without changing
triangles, sort bindings, lighting, visibility or collision. Auxiliary PBR
maps repeat losslessly at their original top mip.
"""
import argparse,json,os,shutil,struct,subprocess
from restore_banner_display_textures import ROOT,CONFIG,DT,np,read_lumps,material_name,image_dds,compact,Image
from scipy.spatial import cKDTree
from optimize_preview_textures import dds,FORMATS

def rows(l):
    v=np.frombuffer(l[73],DT);p=np.frombuffer(l[3],'<f4').reshape(-1,3);ix=np.frombuffer(l[79],'<u2')
    for mi,r in enumerate(struct.iter_unpack('<I3H6b2h2BHI',l[80])):
        ti,page,_,_,base=struct.unpack_from('<3hHI',l[82],r[-2]*12);ids=(base+ix[r[0]:r[0]+r[1]*3].astype('u4')).reshape(-1,3)
        yield mi,r,material_name(l,ti),page,ids,v[ids],p[v['pi'][ids]]

def repeated_dds(source,dest):
    raw=source.read_bytes();info=dds(raw);w,h=info['width'],info['height'];block=FORMATS[info['format']][1]
    assert w%4==0 and h%4==0
    top=np.frombuffer(raw[info['offset']:info['offset']+info['top_bytes']],'u1').reshape(h//4,w//4,block)
    expanded=np.tile(top,(1,4,1)).tobytes();header=bytearray(raw[:info['offset']]);struct.pack_into('<I',header,16,w*4);struct.pack_into('<I',header,20,len(expanded));struct.pack_into('<I',header,28,1)
    dest.parent.mkdir(parents=True,exist_ok=True);staging=dest.parent/'conversion';staging.mkdir(exist_ok=True);inp=staging/dest.name;inp.write_bytes(header+expanded)
    run=subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-y','-m','0','--ignore-mips','-f',FORMATS[info['format']][0],'-dx10','-o',str(dest.parent),str(inp)],capture_output=True,text=True);run.check_returncode()
    new=bytearray(dest.read_bytes());layout=dds(new);assert (layout['width'],layout['height'],layout['format'])==(w*4,h,info['format']);assert layout['top_bytes']==len(expanded)
    new[layout['offset']:layout['offset']+len(expanded)]=expanded;dest.write_bytes(new)

def apply(ident):
    mod=ROOT/'northstar'/CONFIG[ident][0];path=mod/'mod/maps'/(CONFIG[ident][1]+'.bsp');work=ROOT/'output/banner-display-repair'/ident;receipt=work/'display-atlas.json'
    if receipt.exists() or (work/'before-display-atlas.bsp').exists():raise ValueError('Display atlas already applied or interrupted; restore the staging backup before reapplying')
    l=read_lumps(path,range(128));data=list(rows(l));screen=[x for x in data if 'caustic_big_screen_01_blue' in x[2]];donorp=np.concatenate([x[6].reshape(-1,3) for x in screen]);donoruv=np.concatenate([x[5]['uv'].reshape(-1,2) for x in screen]);tree=cKDTree(donorp)
    echoes=[x for x in data if 'echo_big_screen_animation_01' in x[2]];ids=np.unique(np.concatenate([x[4].ravel() for x in echoes]));allother=np.unique(np.concatenate([x[4].ravel() for x in data if 'echo_big_screen_animation_01' not in x[2]]));assert not np.intersect1d(ids,allother).size
    vertices=np.frombuffer(l[73],DT).copy();uv=vertices['uv'][ids].copy();assert uv[:,0].min()>-.9 and uv[:,0].max()<1.9
    vertices['uv'][ids,0]=(uv[:,0]+1)/4;front={};faces=[]
    for mi,r,name,page,vi,v,pts in echoes:
        distance,nearest=tree.query(pts.reshape(-1,3));distance=distance.reshape(-1,3);nearest=nearest.reshape(-1,3)
        sel=(np.ptp(v['uv'][:,:,0],axis=1)<.01)&(np.ptp(v['uv'][:,:,1],axis=1)>.1)&(np.linalg.norm(np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0]),axis=1)>2000)&(distance<3.1).all(1)
        for t in np.flatnonzero(sel):
            target=donoruv[nearest[t]].copy();target[:,0]=(target[:,0]+3)/4
            for i,value in zip(vi[t],target):
                if int(i) in front:assert np.allclose(front[int(i)],value,atol=1e-5)
                front[int(i)]=value
            faces.append(dict(mesh=mi,triangle=int(t),position=pts[t].mean(0).tolist()))
    assert len(faces)==24
    for i,value in front.items():vertices['uv'][i]=value
    assets=work/'assets';manifest=json.loads((work/'build.json').read_text());base='echo_big_screen_animation_01_northstar_colour'
    prefix='world/composite/' if ident=='drop-off' else 'world/phase_runner_preview/'
    primary=assets/('material/'+prefix+base+'_wld.json');colpass=assets/('material/'+prefix+base+'_colpass_wld.json');spec=json.loads(primary.read_text());a=(assets/spec['$textures']['0']).with_suffix('.dds');green=next(assets.rglob('caustic_big_screen_01_blue_albedo.dds'))
    echo=image_dds(a);w,h=echo.size;other=image_dds(green).resize((w,h),Image.Resampling.LANCZOS);atlas=Image.new('RGBA',(w*4,h))
    for tile in range(3):atlas.paste(echo,(tile*w,0))
    atlas.paste(other,(w*3,0));png=work/'echo-display-atlas.png';atlas.save(png)
    run=subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-y','-f','BC7_UNORM_SRGB','-m','0','-dx10','-o',str(a.parent),str(png)],capture_output=True,text=True);run.check_returncode();os.replace(a.parent/(png.stem+'.dds'),a)
    new_channels={};auxiliary={};slug=ident.replace('-','_')+'_banner_displays'
    for slot,role in [('1','normal'),('2','gloss'),('3','spec')]:
        value=spec['$textures'][slot];assert not value.startswith('0x');src=(assets/value).with_suffix('.dds');target='texture/'+slug+'/echo_display_atlas_'+role+'.rpak';repeated_dds(src,(assets/target).with_suffix('.dds'));new_channels[slot]=target;auxiliary[slot]=dict(original=src.relative_to(assets).as_posix(),expanded=(assets/target).with_suffix('.dds').relative_to(assets).as_posix());manifest['files'].append({'_type':'txtr','_path':target,'$disableStreaming':True})
    for p in (primary,colpass):
        s=json.loads(p.read_text());s['width']=w*4;s['height']=h;s['$textures'].update(new_channels);p.write_text(json.dumps(s,indent=2))
    # Material processing can auto-load referenced textures. Explicit resident
    # textures must precede materials to avoid adding the same GUID twice.
    manifest['files'].sort(key=lambda f:f['_type']!='txtr')
    (work/'build.json').write_text(json.dumps(manifest,indent=2));run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(work/'build.json')],capture_output=True,text=True);(work/'build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    backup=work/'before-display-atlas.bsp';shutil.copy2(path,backup);temp=path.with_suffix('.display-atlas.bsp');compact(path,temp,{73:vertices.tobytes()});new=read_lumps(temp,range(128));assert [i for i in range(128) if new[i]!=l[i]]==[73]
    dest=mod/'paks'/(slug+'.rpak');stage=dest.with_suffix('.new.rpak');shutil.copy2(work/'build'/(slug+'.rpak'),stage);os.replace(stage,dest);os.replace(temp,path)
    proof=dict(front_faces=faces,front_vertices={str(k):v.tolist() for k,v in front.items()},all_console_vertices=ids.tolist(),atlas_dimensions=[w*4,h],body_uv_transform='u=(u+1)/4; v unchanged',auxiliary=auxiliary,auxiliary_top_mips_losslessly_repeated=True,collision_geometry_visibility_lighting_preserved=True,resident_bytes=dest.stat().st_size)
    receipt.write_text(json.dumps(proof,indent=2));print(ident,len(faces),'front faces;',len(ids),'console UV vertices;',dest.stat().st_size,'resident bytes')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('map',choices=CONFIG);apply(p.parse_args().map)
