"""Stage native materials, retaining source channels and resident mip chains."""
import concurrent.futures,json,shutil,struct,subprocess,sys,math,hashlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from PIL import Image
from extract_native_material import NativePak
from stage_prop_geometry import material_basename
from optimize_preview_textures import dds,FORMATS
OUT=ROOT/'output/composite/materials'
def prepare(scene_path=None,material_roots=(),namespace='composite',sky_material=None):
    report=json.loads(Path(scene_path or ROOT/'output/composite/scene.json').read_text());assets=OUT/'assets';OUT.mkdir(parents=True,exist_ok=True)
    roots=[*map(Path,material_roots),ROOT/'tools/composite-legion/exported_files/materials',ROOT/'tools/legion/exported_files/materials',ROOT/'output/phase-runner/shared-assets/materials',ROOT/'output/phase-runner/common-assets/exported_files/materials']
    index={}
    for root in roots:
        if root.is_dir():
            for p in root.rglob('*_albedoTexture.dds'):index.setdefault(p.stem.removesuffix('_albedoTexture').lower(),p.parent)
    native=NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak');primary,uber=native.material(next(a for a in native.assets if a['guid']==0x92424EA716974A64));colour,cuber=native.material(next(a for a in native.assets if a['guid']==0x1F8E00B988C71BBB))
    files=[];mapping={};missing={};tasks=[]
    # A named plain fallback records missing channels without borrowing a wrong atlas.
    fallback=OUT/'fallback';fallback.mkdir(exist_ok=True);Image.new('RGBA',(16,16),(115,128,136,255)).save(fallback/'composite_fallback.png')
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0','-f','BC1_UNORM_SRGB','-o',str(fallback),str(fallback/'composite_fallback.png')],capture_output=True,check=True)
    Image.new('RGBA',(16,16),(255,255,255,255)).save(fallback/'screen_opacity.png')
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0','-f','BC4_UNORM','-o',str(fallback),str(fallback/'screen_opacity.png')],capture_output=True,check=True)
    allnames=dict(report['materials']);allnames[namespace+'_sky']=0
    for original,count in allnames.items():
        base=material_basename(original);folder=index.get(sky_material if original=='sky' and sky_material else base) or index.get(base+'_wldc');channels={}
        exported=folder.name.lower() if folder else base
        if folder:
            for slot,semantic in ((0,'albedo'),(1,'normal'),(2,'gloss'),(3,'spec'),(13,'opacityMultiply')):
                source=next((p for p in folder.iterdir() if p.name.lower()==(exported+'_'+semantic+'Texture.dds').lower()),None)
                if source:
                    path=f'texture/{namespace}/{base}_{semantic}.rpak';tasks.append((source,path));channels[str(slot)]=path
        if not channels:
            missing[original]=count;channels={'0':f'texture/{namespace}/composite_fallback_albedo.rpak'}
        # Slot thirteen also appears on solid painted cargo: it is not proof
        # that a surface is glass. Preserve the channel but select an opaque
        # shader for these containers, whose source material is solid metal.
        if base=='composite_big_screen_animation_01':
            # Source uber constants specify a translucent closure screen.
            # Its exported albedo is opaque, so it needs explicit coverage.
            channels['13']=f'texture/{namespace}/screen_opacity.rpak'
            tasks.append((fallback/'screen_opacity.dds',channels['13']))
        transparent='13' in channels and base!='underbelly_cargo_containers_hammond'
        name=f'world/{namespace}/{base}';mapping[original]=dict(name=name,source=original,recovered=bool(folder),textures=channels,transparent=transparent)
    tasks.append((fallback/'composite_fallback.dds',f'texture/{namespace}/composite_fallback_albedo.rpak'))
    # A modest resident texture ceiling avoids unpredictable source starpak streaming.
    def convert(task):
        source,path=task;dest=(assets/path).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():return dict(_type='txtr',_path=path,**{'$disableStreaming':True})
        raw=source.read_bytes()
        try:info=dds(raw);format_name=FORMATS[info['format']][0]
        except KeyError:
            # Legacy uncompressed opacity DDS has RGB masks instead of FourCC.
            height,width=struct.unpack_from('<2I',raw,12);info=dict(width=width,height=height,mips=struct.unpack_from('<I',raw,28)[0],format=None);format_name='BC4_UNORM'
        scale=min(1,1024/max(info['width'],info['height']));w=max(4,round(info['width']*scale));h=max(4,round(info['height']*scale));mips=int(math.log2(max(w,h)))+1
        if info['format'] is not None and (w,h)==(info['width'],info['height']) and info['mips']==mips:shutil.copy2(source,dest)
        else:
            temp=OUT/'conversion'/dest.stem;temp.mkdir(parents=True,exist_ok=True)
            cmd=[str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0','--ignore-mips','-f',format_name,'-dx10','-gpu','0','-bc','q','-if','BOX','-wrap','-w',str(w),'-h',str(h),'-o',str(temp),str(source)]
            run=subprocess.run(cmd,capture_output=True,text=True)
            if run.returncode:
                # Some exported non-power-of-two BC textures cannot be resized
                # directly by DirectXTex. Decode first, then resize/recompress.
                decoded=temp/'decoded';decoded.mkdir(exist_ok=True)
                subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-ft','png','-o',str(decoded),str(source)],capture_output=True,check=True)
                png=next(decoded.glob('*.png'))
                with Image.open(png) as image:
                    image.resize((w,h),Image.Resampling.LANCZOS).save(decoded/'resized.png')
                cmd[-1]=str(decoded/'resized.png')
                run=subprocess.run(cmd,capture_output=True,text=True)
            if run.returncode:raise ValueError(str(source)+' '+run.stdout+run.stderr)
            shutil.copy2(next(temp.glob('*.dds')),dest)
        return dict(_type='txtr',_path=path,**{'$disableStreaming':True})
    unique=dict((p,(s,p)) for s,p in tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,item in enumerate(pool.map(convert,unique.values())):
            files.append(item)
            if i%50==0:print('Textures',i+1,'/',len(unique),flush=True)
    # Native world alpha materials require a separate opacity texture in slot
    # thirteen; the opaque shader does not interpret albedo alpha as coverage.
    from bake_terrain_transitions import save_mips
    from extract_world_glass_shader import extract
    from build_phase_runner_presentation import guid
    shaderpath=f'shaderset/{namespace}_world_alpha.rpak';shaderfile=(assets/shaderpath).with_suffix('.msw');extract(shaderfile)
    shader=bytearray(shaderfile.read_bytes());struct.pack_into('<2Q',shader,5,guid(f'shader/{namespace}_alpha_pixel.rpak'),guid(f'shader/{namespace}_alpha_vertex.rpak'));shaderfile.write_bytes(shader)
    files.insert(0,dict(_type='shds',_path=shaderpath))
    alpha_pak=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak');alpha_spec,alpha_uber=alpha_pak.material(next(a for a in alpha_pak.assets if a['guid']==0x92b5ba61a3bf2e7a))
    for original,record in mapping.items():
        base=record['name'];width,height=1024,1024
        path=f'material/{base}_wld.rpak';cpath=f'material/{base}_colpass_wld.rpak'
        if any(w in original.lower() for w in ('decal','btt_wld')) and not record['transparent']:
            raw=bytearray((assets/record['textures']['0']).with_suffix('.dds').read_bytes())
            if raw[84:88]==b'DX10':
                fmt=struct.unpack_from('<I',raw,128)[0]
                if fmt in (72,75,78,99):struct.pack_into('<I',raw,128,fmt-1)
            alpha=Image.open(io.BytesIO(raw)).convert('RGBA').getchannel('A')
            if alpha.getextrema()[0]<250:
                opacity=f'texture/{namespace}/'+base.rsplit('/',1)[-1]+'_derived_opacity.rpak';dst=(assets/opacity).with_suffix('.dds');dst.parent.mkdir(parents=True,exist_ok=True)
                save_mips(Image.merge('RGBA',(alpha,alpha,alpha,Image.new('L',alpha.size,255))),dst)
                record['textures']['13']=opacity;record['transparent']=True;files.append(dict(_type='txtr',_path=opacity,**{'$disableStreaming':True}))
        if record['transparent']:
            new=dict(alpha_spec,name=base,width=width,height=height,shaderSet=shaderpath,rasterizerFlags='0x16',surfaceProp='default')
            # Keep only this source material's channels. Inherited glass bindings
            # can resolve GUIDs yet stall native startup; presence alone is not
            # a valid compatibility check for the shader's texture table.
            new['blendStates']=alpha_spec['blendStates']+['0x0']*4;new['$textures']=dict(record['textures'])
            buffer=bytearray(alpha_uber);struct.pack_into('<6f',buffer,0,1,0,0,1,0,0);struct.pack_into('<f',buffer,108,.2 if original=='composite_big_screen_animation_01' else 1)
            if original=='composite_big_screen_animation_01':record['opacity']=.2
            target=assets/path;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(new,indent=2));target.with_suffix('.uber').write_bytes(buffer);files.append(dict(_type='matl',_path=path));continue
        for destination,spec,buffer in ((cpath,colour,cuber),(path,primary,uber)):
            new=dict(spec);new['blendStates']=spec['blendStates']+['0x0']*4;new['name']=base+('_colpass' if destination==cpath else '')
            new['width']=width;new['height']=height;new['$textures']=dict(spec['$textures'])|record['textures']
            if destination==path:new['$colpassMaterial']=cpath
            target=assets/destination;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(new,indent=2));target.with_suffix('.uber').write_bytes(buffer);files.append(dict(_type='matl',_path=destination))
    manifest=dict(version=7,name=namespace+'_world',keepDevOnly=True,assetsDir=str(assets),outputDir=str(OUT/'build'),compressLevel=0,hasDynamicLibrary=False,files=list({r['_path']:r for r in files}.values()))
    (OUT/'build.json').write_text(json.dumps(manifest,indent=2));(OUT/'mapping.json').write_text(json.dumps(dict(materials=mapping,missing=missing,texture_resolution_cap=1024),indent=2))
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(OUT/'build.json')],capture_output=True,text=True);(OUT/'build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    print('Materials',len(mapping),'missing',len(missing),'RPak bytes',(OUT/'build'/(namespace+'_world.rpak')).stat().st_size,flush=True)
if __name__=='__main__':prepare()
