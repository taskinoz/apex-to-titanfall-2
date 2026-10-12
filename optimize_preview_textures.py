"""Deduplicate identical channels and add native mip chains in a separate RPak project."""
import json,struct,hashlib,shutil,subprocess,math,concurrent.futures,collections,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'output/phase-runner/dev-materials'
TARGET=ROOT/'output/phase-runner/balanced-materials'
FORMATS={72:('BC1_UNORM_SRGB',8),99:('BC7_UNORM_SRGB',16),71:('BC1_UNORM',8),77:('BC3_UNORM',16),80:('BC4_UNORM',8),83:('BC5_UNORM',16)}
LEGACY={b'DXT1':71,b'DXT5':77,b'BC4U':80,b'BC5U':83}

def dds(data):
    if data[:4]!=b'DDS ':raise ValueError('Not DDS')
    h,w=struct.unpack_from('<2I',data,12);m=max(1,struct.unpack_from('<I',data,28)[0]);fourcc=data[84:88]
    fmt=struct.unpack_from('<I',data,128)[0] if fourcc==b'DX10' else LEGACY[fourcc]
    offset=148 if fourcc==b'DX10' else 128
    if fourcc==b'DX10' and struct.unpack_from('<I',data,140)[0]!=1:raise ValueError('Array textures need a separate path')
    size=max(1,(w+3)//4)*max(1,(h+3)//4)*FORMATS[fmt][1]
    return dict(width=w,height=h,mips=m,format=fmt,offset=offset,top_bytes=size)

def prepare():
    begin=time.monotonic();TARGET.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((SOURCE/'build.json').read_text());groups=collections.defaultdict(list);rows=[]
    for f in manifest['files']:
        if f['_type']!='txtr':continue
        path=(Path(manifest['assetsDir'])/f['_path']).with_suffix('.dds');raw=path.read_bytes()
        groups[hashlib.sha256(raw).hexdigest()].append((f,path,dds(raw)))
    aliases={};tasks=[]
    for group in groups.values():
        canonical,source,info=group[0]
        for old,_,_ in group:aliases[old['_path']]=canonical['_path']
        names=' '.join(f['_path'] for f,_,_ in group)
        semantic=source.stem.rsplit('_',1)[-1]
        keep_normal=semantic=='normal' and any(s in names for s in ('rock_','snow_','dirt_','moss_','terrain_','sand_'))
        cap=None if semantic=='albedo' or keep_normal else 1024
        scale=min(1,cap/max(info['width'],info['height'])) if cap else 1
        size=(max(1,int(info['width']*scale)),max(1,int(info['height']*scale)))
        tasks.append((canonical,source,info,size))
    def convert(task):
        f,source,info,size=task;target=(TARGET/'assets'/f['_path']).with_suffix('.dds');target.parent.mkdir(parents=True,exist_ok=True)
        full=int(math.log2(max(size)))+1;resize=size!=(info['width'],info['height'])
        if target.is_file() and dds(target.read_bytes())['mips']==full:
            raw=target.read_bytes()
        elif info['mips']==full and not resize:
            shutil.copy2(source,target);raw=target.read_bytes()
        else:
            temp=TARGET/'conversion'/source.stem;temp.mkdir(parents=True,exist_ok=True)
            cmd=[str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-y','-m','0','--ignore-mips','-f',FORMATS[info['format']][0],'-dx10','-gpu','0','-bc','q','-if','BOX','-wrap','-o',str(temp)]
            if resize:cmd+=['-w',str(size[0]),'-h',str(size[1])]
            run=subprocess.run(cmd+[str(source)],capture_output=True,text=True)
            if run.returncode:raise ValueError(source.stem+' '+run.stdout+run.stderr)
            generated=next(temp.glob('*.dds'));raw=bytearray(generated.read_bytes());new=dds(raw)
            if new['format']!=info['format'] or (new['width'],new['height'])!=size:raise ValueError('DDS layout changed unexpectedly')
            if not resize:
                original=source.read_bytes();raw[new['offset']:new['offset']+new['top_bytes']]=original[info['offset']:info['offset']+info['top_bytes']]
            target.write_bytes(raw)
        new=dds(raw)
        return dict(path=f['_path'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source=info,result=new,resized=resize,top_blocks_preserved=not resize,bytes_before=source.stat().st_size,bytes_after=len(raw))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for i,row in enumerate(pool.map(convert,tasks)):
            rows.append(row)
            if (i+1)%50==0:print(f'Mip-ready textures: {i+1}/{len(tasks)}',flush=True)
    files=[t[0] for t in tasks]
    for f in manifest['files']:
        if f['_type']!='matl':continue
        source=Path(manifest['assetsDir'])/f['_path'];target=TARGET/'assets'/f['_path'];target.parent.mkdir(parents=True,exist_ok=True)
        spec=json.loads(source.with_suffix('.json').read_text())
        spec['$textures']={k:aliases.get(v,v) for k,v in spec['$textures'].items()}
        target.with_suffix('.json').write_text(json.dumps(spec,indent=2));shutil.copy2(source.with_suffix('.uber'),target.with_suffix('.uber'));files.append(f)
    manifest['files']=files;manifest['assetsDir']=str(TARGET/'assets');manifest['outputDir']=str(TARGET/'build')
    (TARGET/'build.json').write_text(json.dumps(manifest,indent=2))
    before=sum(path.stat().st_size for group in groups.values() for _,path,_ in group)
    report=dict(original_textures=len(aliases),unique_textures=len(tasks),exact_duplicate_textures_removed=len(aliases)-len(tasks),
        original_dds_bytes=before,optimized_dds_bytes=sum(r['bytes_after'] for r in rows),
        albedo_top_blocks_preserved=True,rock_terrain_normal_top_blocks_preserved=True,
        auxiliary_resolution_cap=1024,full_resident_mip_chains=True,star_pak_streaming_enabled=False,
        material_names_uber_and_external_dependencies_preserved=True,aliases=aliases,textures=rows,seconds=time.monotonic()-begin,
        tool='Microsoft DirectXTex 2026.5.8.1',tool_source='https://github.com/microsoft/DirectXTex/releases/tag/may2026')
    (TARGET/'optimization.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('aliases','textures')},indent=2),flush=True)
if __name__=='__main__':prepare()
