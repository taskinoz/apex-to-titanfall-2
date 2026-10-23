"""One resident UI atlas for every map; loading materials stay independent.

Titanfall pools at most 20 "UI image atlas" assets across the whole game
(docs/candidates/ui-atlas-lifetime-2026-10-14.md), so all maps share one atlas:
2560x1440 loading art in a 3-column grid, 1024x1024 minimaps in a row beneath.
"""
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from map_pack_lifetime import ROOT, MAPS
from extract_native_material import NativePak
from build_phase_runner_presentation import guid

sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from PIL import Image
from restore_banner_display_textures import image_dds

WORK = Path('D:/Games/ApexToTitanfallWork/new-arena-ports/shared-map-ui')
SHARED = ROOT/'northstar/ApexMaps.UI'
PACK = 'apex_maps_ui.rpak'
COLUMNS = 3
SIZE = (8192,5376)  # 3 rows of loading art (4320) + one row of minimaps (1024); seven maps
SOURCES = {
    'PhaseRunner': (ROOT/'output/phase-runner/presentation', ROOT/'output/minimaps/phase_runner_minimap'),
    'ArenaComposite': (ROOT/'output/composite/presentation', ROOT/'output/minimaps/drop_off_minimap'),
    'ApexFiringRange': (WORK.parent/'firing-range/presentation', WORK.parent/'firing-range/minimap'),
    'ArenaPartyCrasher': (WORK.parent/'party-crasher/presentation', WORK.parent/'party-crasher/minimap'),
    'ArenaOverflow': (WORK.parent/'overflow/presentation', WORK.parent/'overflow/minimap'),
    'ArenaThermalStation': (WORK.parent/'thermal-station/presentation', WORK.parent/'thermal-station/minimap'),
    'ArenaThunderdome': (WORK.parent/'thunderdome/presentation', WORK.parent/'thunderdome/minimap'),
}


def repak(manifest, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2))
    run = subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(target)], capture_output=True, text=True)
    target.with_suffix('.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    return Path(manifest['outputDir'])/(manifest['name']+'.rpak')


def build():
    WORK.mkdir(parents=True, exist_ok=True)
    canvas = Image.new('RGBA', SIZE, (0,0,0,0))
    images, provenance, loading = [], {}, {}
    for i, (package, (presentation, minimap)) in enumerate(SOURCES.items()):
        entries = []
        for source, position in ((presentation, ((i%COLUMNS)*2560,(i//COLUMNS)*1440)),
                                 (minimap, (i*1024, 3*1440))):
            manifest = json.loads((source/'build.json').read_text())
            ui = next(f for f in manifest['files'] if f['_type']=='uimg')
            path = (Path(manifest['assetsDir'])/ui['atlas']).with_suffix('.dds')
            image = image_dds(path).convert('RGBA')
            x,y = position
            if image.width > (2560 if source==presentation else 1024) or image.height > (1440 if source==presentation else 1024):
                raise ValueError('Source art does not fit reserved rectangle: '+str(path))
            canvas.paste(image, position)
            for original in ui['images']:
                item = dict(original)
                item['posX'] += x
                item['posY'] += y
                images.append(item)
            entries.append(dict(source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                original_size=list(image.size),position=list(position),resized=False))
            if source == presentation:
                standalone = dict(manifest)
                standalone['files'] = [dict(_type='txtr',_path=ui['atlas'],**{'$disableStreaming':True})]
                standalone['files'] += [f for f in manifest['files'] if f['_type']!='uimg']
                standalone['outputDir'] = str(WORK/'loading'/package)
                built = repak(standalone, WORK/'loading'/package/'build.json')
                pak = NativePak(built)
                if any(a['type']=='uimg' for a in pak.assets):
                    raise ValueError('Standalone loading pack still owns a UI atlas')
                original_pak = ROOT/'northstar'/package/'paks'/built.name
                backup = WORK/'before'/package/original_pak.name
                backup.parent.mkdir(parents=True, exist_ok=True)
                if not backup.exists():
                    shutil.copy2(original_pak,backup)
                before = NativePak(backup)
                old = {a['guid']:a for a in before.assets if a['type']=='matl'}
                new = {a['guid']:a for a in pak.assets if a['type']=='matl'}
                if old.keys()!=new.keys() or any(before.material(old[g])!=pak.material(new[g]) for g in old):
                    raise ValueError('Native loading material state/buffer changed')
                loading[package] = dict(built=str(built),sha256=hashlib.sha256(built.read_bytes()).hexdigest(),
                                        native_materials_unchanged=True,ui_atlases=0)
        provenance[package] = entries
    expected = 4*len(SOURCES)
    if len(images)!=expected or len({item['path'] for item in images})!=expected:
        raise ValueError('Shared atlas must include three loading names and one overview per map')
    tex = 'texture/apex_maps/ui_shared.rpak'
    dest = (WORK/'assets'/tex).with_suffix('.dds')
    dest.parent.mkdir(parents=True,exist_ok=True)
    png = WORK/'ui-shared.png'
    canvas.save(png)
    # -srgb: the PNG already holds sRGB values; without it texconv treats it as linear and
    # brightens every overview and loading name (dark Apex minimaps looked washed out).
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'),'-nologo','-srgb','-f','BC7_UNORM_SRGB','-m','1',
                    '-y','-o',str(dest.parent),str(png)],capture_output=True,check=True)
    shutil.copy2(dest.parent/'ui-shared.dds',dest)
    manifest = dict(version=7,name='apex_maps_ui',keepDevOnly=True,assetsDir=str(WORK/'assets'),
                    outputDir=str(WORK/'build'),compressLevel=0,hasDynamicLibrary=False,
                    files=[dict(_type='uimg',_path='ui_image_atlas/apex_maps_shared.rpak',atlas=tex,images=images)])
    built = repak(manifest,WORK/'build.json')
    pak = NativePak(built)
    if sorted(a['type'] for a in pak.assets)!=['txtr','uimg']:
        raise ValueError('Shared pack contains unexpected assets')
    ui = next(a for a in pak.assets if a['type']=='uimg')
    address = pak.address(ui['header'])
    if struct.unpack_from('<4H',pak.data,address+8)!=(*SIZE,expected,0):
        raise ValueError('Shared atlas dimensions/count differ')
    (SHARED/'paks').mkdir(parents=True,exist_ok=True)
    shutil.copy2(built,SHARED/'paks'/PACK)
    (SHARED/'mod.json').write_text(json.dumps(dict(Name='ApexMaps.UI',Version='0.2.1',LoadPriority=9,
        Description='Shared original loading artwork and minimaps for the Apex map conversions.'),indent=2)+'\n')
    (SHARED/'paks/rpak.json').write_text(json.dumps(dict(Postload={PACK:'common.rpak'}),indent=2)+'\n')
    for package, result in loading.items():
        paks = ROOT/'northstar'/package/'paks'
        shutil.copy2(result['built'], paks/Path(result['built']).name)
        for old in paks.glob('*_minimap.rpak'):
            backup = WORK/'before'/package/old.name
            if not backup.exists():
                shutil.copy2(old,backup)
            old.unlink()
        config = json.loads((paks/'rpak.json').read_text())
        config = {'Aliases':config['Aliases'],'Postload':{p.name:'mp_coliseum.rpak' for p in paks.glob('*.rpak')
                                                           if not p.name.endswith('_presentation.rpak')}}
        config['Postload'][Path(result['built']).name] = 'common.rpak'
        (paks/'rpak.json').write_text(json.dumps(config,indent=2)+'\n')
    receipt = dict(images=images,provenance=provenance,loading=loading,shared_ui_atlases=1,
                   resident_dimensions=list(SIZE),shared_pack_sha256=hashlib.sha256(built.read_bytes()).hexdigest(),
                   native_runtime_verified=False)
    (WORK/'build-proof.json').write_text(json.dumps(receipt,indent=2))
    (ROOT/'docs/conversion/shared-map-ui.json').write_text(json.dumps(receipt,indent=2))
    print('Built one shared UI atlas and',len(loading),'atlas-free native loading packs',flush=True)


if __name__=='__main__':
    build()
