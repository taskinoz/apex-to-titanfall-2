"""Build independent native loading/lobby artwork from the source loadscreen."""
import json,sys,subprocess,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from PIL import Image
from extract_native_material import NativePak
from build_phase_runner_presentation import guid
OUT=ROOT/'output/composite/presentation';ART=ROOT/'tools/composite-legion/exported_files/images/0xd82e480a0890d645.png'
def build():
    assets=OUT/'assets';tex='texture/loadscreens/mp_arena_composite.rpak';dest=(assets/tex).with_suffix('.dds');dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-f','BC7_UNORM_SRGB','-m','1','-y','-o',str(dest.parent),str(ART)],capture_output=True,check=True)
    shutil.copy2(dest.parent/(ART.stem+'.dds'),dest);w,h=Image.open(ART).size
    template=ROOT/'output/phase-runner/loading-native-template';spec=json.loads((template/'loadscreen.json').read_text());files=[]
    names=['mp_arena_composite','mp_arena_composite_widescreen','mp_arena_composite_lobby']
    files.append(dict(_type='uimg',_path='ui_image_atlas/composite.rpak',atlas=tex,images=[dict(path='loadscreens/'+name,posX=0,posY=0,width=w,height=h) for name in names]))
    for name in names:
        p='material/loadscreens/'+name+'_gen.rpak';s=dict(spec,name='loadscreens/'+name,width=w,height=h,shaderType='gen');s['$textures']={'0':tex};s['blendStates']=spec['blendStates']+['0x0']*4
        target=assets/p;target.parent.mkdir(parents=True,exist_ok=True);target.with_suffix('.json').write_text(json.dumps(s,indent=2));shutil.copy2(template/'loadscreen.uber',target.with_suffix('.uber'));files.append(dict(_type='matl',_path=p))
    manifest=dict(version=7,name='composite_presentation',keepDevOnly=True,assetsDir=str(assets),outputDir=str(OUT/'build'),compressLevel=0,hasDynamicLibrary=False,files=files)
    (OUT/'build.json').write_text(json.dumps(manifest,indent=2));result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(OUT/'build.json')],capture_output=True,text=True);(OUT/'build.log').write_text(result.stdout+result.stderr);result.check_returncode()
    pak=NativePak(OUT/'build/composite_presentation.rpak');assets={a['guid']:a for a in pak.assets}
    for name in names:
        a=assets[guid('material/loadscreens/'+name+'_gen.rpak')];actual,uber=pak.material(a)
        if uber!=(template/'loadscreen.uber').read_bytes() or int(actual['$textures']['0'],16)!=guid(tex):raise ValueError('Native loading material binding differs')
    (OUT/'presentation.json').write_text(json.dumps(dict(source='mp_rr_arena_composite_loadscreen.rpak',display_name='Composite',art_sha256=hashlib.sha256(ART.read_bytes()).hexdigest(),dimensions=[w,h],materials=names,native_loading_material_verified=True,client_verified=False),indent=2))
    print('Built Composite native loading screen and lobby artwork')
if __name__=='__main__':build()
