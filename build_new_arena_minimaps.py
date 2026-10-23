"""Port original overview artwork, or draw an explicitly approximate range plan."""
import json
import re
import shutil
import subprocess
import sys
from new_arena_ports import CONFIG, ROOT, WORK, folder

sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from PIL import Image, ImageDraw
from restore_banner_display_textures import image_dds
from build_arena_minimaps import overview, verify_pack


def build(ident):
    c=CONFIG[ident];out=folder(ident)/'minimap';out.mkdir(parents=True,exist_ok=True)
    if ident not in ('firing-range','thermal-station','thunderdome'):  # cut-outs and retail maps render their own overview
        files=list((folder(ident)/'legion/exported_files/atlases').rglob('*.dds'))
        if len(files)!=1:raise ValueError('Minimap source atlas must be identified unambiguously')
        image=image_dds(files[0]);original_size=image.size
        text=(ROOT/'inputs/candidates'/ident/'resource/overviews'/(c['source']+'.txt')).read_text()
        fields={k:float(re.search(r'\b'+k+r'\s+([-\d.]+)',text)[1]) for k in ('pos_x','pos_y','scale')}
        corner=[fields['pos_x']+c['offset'][0],fields['pos_y']+c['offset'][1]]
        scale=fields['scale']*image.width/1024
        image=image.resize((1024,1024),Image.Resampling.LANCZOS)
        provenance=dict(kind='original Apex overview atlas',source=str(files[0]),source_size=original_size,source_scale=fields['scale'])
    else:
        scene=np.load(folder(ident)/'scene.npz');t=scene['triangles'];mi=scene['material'];names=scene['names']
        mask=(names[mi]!='sky') & (t[:,:,:3].mean(1)[:,2]<4000)
        t=t[mask];mi=mi[mask];lo=t[:,:,:2].min((0,1));hi=t[:,:,:2].max((0,1))
        span=float(np.max(hi-lo)+512);center=(lo+hi)/2;corner=[float(center[0]-span/2),float(center[1]+span/2)];scale=span/1024
        image=Image.new('RGBA',(1024,1024),(0,0,0,0));draw=ImageDraw.Draw(image)
        for i in np.argsort(t[:,:,:3].mean(1)[:,2],kind='stable'):
            name=str(names[mi[i]]).lower()
            if any(w in name for w in ('decal','grass','foliage','leaf','plant','sky')):continue
            points=[((float(p[0])-corner[0])/scale,(corner[1]-float(p[1]))/scale) for p in t[i,:,:3]]
            colour=(112,99,82,255) if any(w in name for w in ('rock','terrain','ground','sand')) else (172,178,176,255)
            draw.polygon(points,fill=colour)
        provenance=dict(kind='generated approximate top-down geometry plan',source_overview_available=False,
                        limitation='Height-sorted surfaces; no original Apex overview exists in this source archive')
        scene.close()
    png=out/'source.png';image.save(png);slug=ident.replace('-','_');pack=slug+'_minimap'
    config=dict(map=c['target'],corner=corner,scale=scale,size=(1024,1024),pack=pack)
    texture='texture/overviews/'+c['target']+'.rpak';dest=(out/'assets'/texture).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-f','BC7_UNORM_SRGB','-m','1','-y','-o',str(dest.parent),str(png)],capture_output=True,check=True)
    shutil.copy2(dest.parent/'source.dds',dest)
    manifest=dict(version=7,name=pack,keepDevOnly=True,assetsDir=str(out/'assets'),outputDir=str(out/'build'),compressLevel=0,
        hasDynamicLibrary=False,files=[dict(_type='uimg',_path='ui_image_atlas/overviews/'+c['target']+'.rpak',atlas=texture,
        images=[dict(path='overviews/'+c['target'],posX=0,posY=0,width=1024,height=1024)])])
    (out/'build.json').write_text(json.dumps(manifest,indent=2))
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(out/'build.json')],capture_output=True,text=True)
    (out/'build.log').write_text(run.stdout+run.stderr);run.check_returncode();verify_pack(out/'build'/(pack+'.rpak'),config)
    mod=WORK/'candidates'/c['package'];shutil.copy2(out/'build'/(pack+'.rpak'),mod/'paks'/(pack+'.rpak'))
    target=mod/'mod/resource/overviews'/(c['target']+'.txt');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(overview(config))
    path=mod/'paks/rpak.json';mapping=json.loads(path.read_text());mapping.setdefault('Postload',{}).pop(pack+'.rpak',None);mapping[pack+'.rpak']='^'+c['target']+'$';path.write_text(json.dumps(mapping,indent=2))
    (out/'minimap.json').write_text(json.dumps(dict(config=config,provenance=provenance,native_runtime_verified=False),indent=2))
    print(ident,'minimap',corner,scale,provenance['kind'],flush=True)


if __name__=='__main__':
    for ident in CONFIG if sys.argv[1]=='all' else [sys.argv[1]]:build(ident)
