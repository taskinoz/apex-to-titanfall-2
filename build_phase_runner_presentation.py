"""Native loading material, lobby atlas and localized Phase Runner map tokens."""
import json,shutil,struct,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
from PIL import Image
from extract_native_material import NativePak
OUT=ROOT/'output/phase-runner/presentation'
ART=ROOT/'output/phase-runner/loadscreen-source/texture/0x73107148EEA2DDC3.png'
LANGUAGES=('english','french','german','italian','japanese','mspanish','polish','portuguese','russian','spanish','tchinese','schinese','korean')

def guid(path):
    result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),'-pakguid',path],capture_output=True,text=True,check=True)
    return int(result.stdout.strip(),16)

def build():
    assets=OUT/'assets';texture='texture/loadscreens/mp_phase_runner.rpak';target=(assets/texture).with_suffix('.dds');target.parent.mkdir(parents=True,exist_ok=True)
    # Format conversion only: preserve original full-resolution artwork.
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-f','BC7_UNORM_SRGB','-m','1','-y','-o',str(target.parent),str(ART)],check=True)
    if target.exists():target.unlink()
    shutil.move(str(target.parent/ART.with_suffix('.dds').name),target)
    width,height=Image.open(ART).size
    template=ROOT/'output/phase-runner/loading-native-template';spec=json.loads((template/'loadscreen.json').read_text())
    native=NativePak(ROOT/'inputs/tf2-rpak-work/coliseum-loadscreen.raw.rpak')
    asset=next(a for a in native.assets if a['type']=='matl')
    if guid('material/loadscreens/mp_coliseum_widescreen_gen.rpak')!=asset['guid']:raise ValueError('Native loadscreen lookup suffix differs')
    files=[]
    paths=[]
    for name in ('mp_phase_runner_widescreen','mp_phase_runner','mp_phase_runner_lobby'):
        path='material/loadscreens/'+name+'_gen.rpak';new=dict(spec);new['name']='loadscreens/'+name;new['width']=width;new['height']=height;new['shaderType']='gen'
        new['$textures']={'0':texture};new['blendStates']=spec['blendStates']+['0x0']*4
        dest=assets/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.with_suffix('.json').write_text(json.dumps(new,indent=2));shutil.copy2(template/'loadscreen.uber',dest.with_suffix('.uber'))
        files.append(dict(_type='matl',_path=path));paths.append(path)
    files.insert(0,dict(_type='uimg',_path='ui_image_atlas/phase_runner.rpak',atlas=texture,images=[dict(path='loadscreens/'+name,posX=0,posY=0,width=width,height=height)
        for name in ('mp_phase_runner_lobby','mp_phase_runner','mp_phase_runner_widescreen')]))
    manifest=dict(version=7,name='phase_runner_presentation',keepDevOnly=True,assetsDir=str(assets),outputDir=str(OUT/'build'),compressLevel=0,hasDynamicLibrary=False,files=files)
    (OUT/'build.json').write_text(json.dumps(manifest,indent=2))
    result=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(OUT/'build.json')],capture_output=True,text=True)
    (OUT/'build.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    pak=NativePak(OUT/'build/phase_runner_presentation.rpak');byguid={a['guid']:a for a in pak.assets};common=NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak')
    shader=int(spec['shaderSet'],16)
    if shader not in {a['guid'] for a in common.assets}:raise ValueError('Loading shader missing from common.rpak')
    for path in paths:
        a=byguid[guid(path)];actual,uber=pak.material(a)
        if uber!=(template/'loadscreen.uber').read_bytes():raise ValueError('Loading shader buffer changed')
        for key in ('features','samplers','shaderSet','glueFlags','glueFlags2','depthStencilFlags','rasterizerFlags','blendStateMask'):
            if actual[key]!=spec[key]:raise ValueError('Loading material state differs '+key)
        if actual['$textures']!={'0':hex(guid(texture)).upper().replace('0X','0x')}: 
            if int(actual['$textures']['0'],16)!=guid(texture):raise ValueError('Loading texture binding differs')
    uimg=next(a for a in pak.assets if a['type']=='uimg');addr=pak.address(uimg['header']);hw,hh,count,unknown=struct.unpack_from('<4H',pak.data,addr+8)
    if (hw,hh,count,unknown)!=(width,height,3,0):raise ValueError('Lobby atlas layout differs')
    resource=OUT/'resource';resource.mkdir(exist_ok=True)
    descriptions={'english':'An industrial arena between snowy peaks. Fight through the Phase Runner tunnels.',
      'french':'Une arène industrielle entre des sommets enneigés. Combattez dans les tunnels du Phase Runner.',
      'german':'Eine Industriearena zwischen verschneiten Gipfeln. Kämpfe in den Tunneln des Phase Runners.',
      'italian':'Un’arena industriale tra cime innevate. Combatti nei tunnel del Phase Runner.',
      'japanese':'雪山に囲まれた工業地帯。Phase Runnerのトンネルで戦おう。',
      'mspanish':'Una arena industrial entre cumbres nevadas. Combate en los túneles del Phase Runner.',
      'polish':'Przemysłowa arena wśród ośnieżonych szczytów. Walcz w tunelach Phase Runnera.',
      'portuguese':'Uma arena industrial entre picos nevados. Lute nos túneis do Phase Runner.',
      'russian':'Промышленная арена среди заснеженных вершин. Сражайтесь в туннелях Phase Runner.',
      'spanish':'Una arena industrial entre cumbres nevadas. Combate en los túneles del Phase Runner.',
      'tchinese':'雪峰間的工業競技場。在 Phase Runner 隧道中戰鬥。',
      'schinese':'雪峰间的工业竞技场。在 Phase Runner 隧道中战斗。',
      'korean':'눈 덮인 봉우리 사이의 산업 지대. Phase Runner 터널에서 전투를 벌이세요.'}
    for language in LANGUAGES:
        text='"lang"\n{\n\t"Language" "'+language+'"\n\t"Tokens"\n\t{\n'
        for token,value in {'mp_phase_runner':'Phase Runner','mp_phase_runner_ALLCAPS':'PHASE RUNNER','mp_phase_runner_CLASSIC_DESC':descriptions[language],
            'mp_phase_runner_preview':'Phase Runner (0.1.36 backup)','mp_phase_runner_preview_ALLCAPS':'PHASE RUNNER (BACKUP)'}.items():text+='\t\t"'+token+'" "'+value+'"\n'
        (resource/f'phase_runner_{language}.txt').write_text(text+'\t}\n}\n',encoding='utf-16')
    report=dict(map_name='mp_phase_runner',display_name='Phase Runner',art_source='Locally installed Apex mp_rr_arena_phase_runner_loadscreen.rpak',
        art_png_sha256=hashlib.sha256(ART.read_bytes()).hexdigest(),width=width,height=height,texture_format='BC7_UNORM_SRGB, resident',
        native_loading_shader_guid=hex(shader),native_shader_suffix='gen',native_loading_material_states_and_buffer_verified=True,
        common_shader_dependency_verified=True,loading_materials=paths,lobby_atlas_images=3,localization_languages=list(LANGUAGES),
        rpak_sha256=hashlib.sha256((OUT/'build/phase_runner_presentation.rpak').read_bytes()).hexdigest(),client_presentation_verified=False)
    (OUT/'presentation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':build()
