"""Replace only Party Crasher's placeholder atlas panel with Northstar artwork.

The current world material pack is rebuilt without changing its material
definitions or shaders. DDS blocks outside the panel remain byte identical.
No BSP/STBSP, geometry, collision, lighting, scripts or UI atlases change.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess

from new_arena_ports import ROOT,folder
from package_player_mods import digest
from restore_banner_display_textures import image_dds
from recover_party_report4 import replace_bc3

OUT=folder('party-crasher')
PROJECT=OUT/'northstar-screen-v1'
MOD=ROOT/'northstar/ArenaPartyCrasher'
ART=ROOT/'art/northstar/party-crasher-northstar-screen-v1.png'
TEXTURE=Path('texture/party_crasher/oasis_signs_ad_atlas_01_albedo.dds')
VERSION='0.6.4'
NOTE='Adds a new Northstar billboard image to the curved Oasis screen, matching the Drop-Off banner artwork. Geometry, collision, lighting and gameplay are unchanged from 0.6.3.'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def replace_panel(original,destination,art):
    from PIL import Image
    raw=original.read_bytes()
    h,w=struct.unpack_from('<2I',raw,12);mips=struct.unpack_from('<I',raw,28)[0]
    if raw[84:88]!=b'DX10' or struct.unpack_from('<I',raw,128)[0]!=78:
        raise ValueError('Expected the existing BC3 sRGB atlas')
    source_box=json.loads((OUT/'report4-recovery/textures.json').read_text())['atlas_panel_source_pixels']
    x0,y0,x1,y1=source_box
    source=image_dds(OUT/'legion/exported_files/materials/oasis_signs_ad_atlas_01/oasis_signs_ad_atlas_01_albedoTexture.dds')
    box=(math.floor(x0*w/source.width),math.floor(y0*h/source.height),
         math.ceil((x1+1)*w/source.width),math.ceil((y1+1)*h/source.height))
    atlas=image_dds(original)
    image=Image.open(art).convert('RGBA').resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS)
    atlas.paste(image,box[:2]);atlas.save(PROJECT/'atlas-preview.png')
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,destination)
    replace_bc3(destination,atlas)
    encoded=destination.read_bytes();result=bytearray(raw);at=148;changed=0;retained=0
    for mip in range(max(1,mips)):
        mw,mh=max(1,w>>mip),max(1,h>>mip);bw,bh=max(1,(mw+3)//4),max(1,(mh+3)//4)
        left,top=box[0]//(4*2**mip),box[1]//(4*2**mip)
        right,bottom=math.ceil(box[2]/(4*2**mip)),math.ceil(box[3]/(4*2**mip))
        for y in range(bh):
            for x in range(bw):
                o=at+(y*bw+x)*16
                if left<=x<right and top<=y<bottom:
                    result[o:o+16]=encoded[o:o+16];changed+=raw[o:o+16]!=encoded[o:o+16]
                else:
                    if result[o:o+16]!=raw[o:o+16]:raise ValueError('Unrelated atlas block changed')
                    retained+=1
        at+=bw*bh*16
    if at!=len(raw) or raw[:148]!=result[:148]:raise ValueError('DDS layout changed')
    destination.write_bytes(result)
    return dict(source_panel_pixels=source_box,native_panel_pixels=box,dds_size=[w,h],mips=mips,
                changed_blocks=changed,unchanged_outside_blocks=retained,
                srgb_encoding='Existing DXGI 78 retained; sRGB bytes preserved without gamma re-encoding',
                original_sha256=digest(original),modified_sha256=digest(destination))


def build():
    if (PROJECT/'receipt.json').exists():raise ValueError('Already built; do not overwrite the baseline')
    if json.loads((MOD/'mod.json').read_text())['Version']!='0.6.3':raise ValueError('Unexpected map version')
    oldpak=OUT/'materials/build/party_crasher_world.rpak'
    if digest(oldpak)!=digest(MOD/'paks/party_crasher_world.rpak'):raise ValueError('Build assets do not match accepted mod')
    PROJECT.mkdir(parents=True,exist_ok=True)
    baseline={p.relative_to(MOD).as_posix():digest(p) for p in MOD.rglob('*') if p.is_file()}
    shutil.copy2(oldpak,PROJECT/'party_crasher_world-0.6.3.rpak')
    shutil.copytree(OUT/'materials/assets',PROJECT/'assets',dirs_exist_ok=True)
    texture=replace_panel(OUT/'materials/assets'/TEXTURE,PROJECT/'assets'/TEXTURE,ART)
    manifest=json.loads((OUT/'materials/build.json').read_text());manifest['assetsDir']=str(PROJECT/'assets');manifest['outputDir']=str(PROJECT/'build')
    write(PROJECT/'build.json',manifest)
    run=subprocess.run([str(ROOT/'tools/repak/RePak.exe'),str(PROJECT/'build.json')],capture_output=True,text=True)
    (PROJECT/'build.log').write_text(run.stdout+run.stderr);run.check_returncode()
    from extract_native_material import NativePak
    old,new=NativePak(oldpak),NativePak(PROJECT/'build/party_crasher_world.rpak')
    if [(a['guid'],a['type'],a['version']) for a in old.assets]!=[(a['guid'],a['type'],a['version']) for a in new.assets]:
        raise ValueError('World asset inventory changed')
    count=0
    for a,b in zip(old.assets,new.assets):
        if a['type']=='matl':
            if old.material(a)!=new.material(b):raise ValueError('Material/shader binding changed')
            count+=1
    candidate=PROJECT/'ArenaPartyCrasher';shutil.copytree(MOD,candidate,dirs_exist_ok=True)
    shutil.copy2(PROJECT/'build/party_crasher_world.rpak',candidate/'paks/party_crasher_world.rpak')
    meta=json.loads((candidate/'mod.json').read_text());meta['Version']=VERSION;write(candidate/'mod.json',meta)
    for rel,sha in baseline.items():
        if rel not in ['mod.json','paks/party_crasher_world.rpak'] and digest(candidate/rel)!=sha:raise ValueError('Unrelated payload changed: '+rel)
    from map_pack_lifetime import audit
    audit(candidate/'paks','mp_party_crasher')
    write(PROJECT/'receipt.json',dict(version=VERSION,artwork_sha256=digest(ART),baseline=baseline,
          texture=texture,identical_material_definitions=count,asset_count=len(new.assets),
          candidate_world_sha256=digest(candidate/'paks/party_crasher_world.rpak'),
          geometry_collision_lighting_scripts_and_ui_unchanged=True,ui_atlases_added=0))
    print('Built Northstar screen candidate; identical material definitions:',count,flush=True)


def publish():
    proof=json.loads((PROJECT/'receipt.json').read_text())
    runtime=json.loads((PROJECT/'runtime-captures.json').read_text())
    candidate=PROJECT/'ArenaPartyCrasher'
    if not runtime['mounted_payload_verified'] or not runtime['stock_and_party_reload']:
        raise ValueError('Native rendering/reload proof is required')
    if runtime['logs']['script_errors'] or runtime['logs']['native_crashes']:
        raise ValueError('Native validation recorded errors')
    for rel,sha in proof['baseline'].items():
        if digest(MOD/rel)!=sha:raise ValueError('Accepted baseline changed: '+rel)
    if digest(candidate/'paks/party_crasher_world.rpak')!=proof['candidate_world_sha256']:
        raise ValueError('Tested candidate changed')
    for name in ['mod.json','README.md','build-status.json']:
        shutil.copy2(MOD/name,PROJECT/('baseline-'+name))
    original=OUT/'materials/assets'/TEXTURE
    shutil.copy2(original,PROJECT/'original-atlas.dds')
    def replace(source,destination):
        temp=destination.with_name(destination.name+'.northstar-new')
        shutil.copy2(source,temp);os.replace(temp,destination)
    replace(PROJECT/'assets'/TEXTURE,original)
    replace(PROJECT/'build/party_crasher_world.rpak',OUT/'materials/build/party_crasher_world.rpak')
    replace(candidate/'paks/party_crasher_world.rpak',MOD/'paks/party_crasher_world.rpak')
    replace(candidate/'mod.json',MOD/'mod.json')
    old=(MOD/'README.md').read_text(encoding='utf-8')
    (MOD/'README.md').write_text('# Party Crasher '+VERSION+'\n\n'+NOTE+'\n\n## Previous release notes\n\n'+old,encoding='utf-8')
    status=json.loads((MOD/'build-status.json').read_text());status.update(version=VERSION,
        artwork='art/northstar/party-crasher-northstar-screen-v1.png',
        world_pack_sha256=proof['candidate_world_sha256'])
    write(MOD/'build-status.json',status)
    license_path=MOD/'mod/resource/northstar-banner-license.txt'
    shutil.copy2(ROOT/'art/northstar/NORTHSTAR-LICENSE.txt',license_path)
    docs=ROOT/'docs/candidates/party-crasher/port-0.6.4';docs.mkdir(parents=True,exist_ok=True)
    framed=next(s for s in runtime['captures'] if Path(s['path']).name.startswith('northstar-screen-framed-'))
    if digest(framed['path'])!=framed['sha256']:raise ValueError('Native screenshot changed')
    shutil.copy2(framed['path'],docs/'screen-in-game.png')
    public=dict(version=VERSION,artwork_sha256=proof['artwork_sha256'],texture=proof['texture'],
        identical_material_definitions=proof['identical_material_definitions'],asset_count=proof['asset_count'],
        world_pack_sha256=proof['candidate_world_sha256'],bsp_sha256=proof['baseline']['mod/maps/mp_party_crasher.bsp'],
        geometry_collision_lighting_scripts_and_ui_unchanged=True,ui_atlases_added=0,
        native_screenshot_sha256=framed['sha256'],mounted_payload_verified=True,stock_and_party_reload=True,
        script_errors=0,native_crashes=0,single_client_only=True)
    write(docs/'validation.json',public)
    (docs/'README.md').write_text('# Party Crasher '+VERSION+'\n\n'+NOTE+
        '\n\nThe new artwork replaces the existing star placeholder inside the Oasis advertisement atlas. '
        'The original PNG and generation prompt are retained under `art/northstar/`. '
        'The atlas keeps its existing dimensions, mip chain and sRGB encoding. All '+
        str(proof['texture']['unchanged_outside_blocks'])+' compressed blocks outside the affected panel are byte identical. '
        'All '+str(proof['identical_material_definitions'])+' material definitions and their shader bindings are unchanged. '
        'The exact mounted payload was checked in game, then stock Coliseum and Party Crasher reloaded without logged errors. '
        'This is a single-client visual/reload check, not a new multiplayer or performance certification. '
        'Rollback assets are retained in `party-crasher/northstar-screen-v1/` on the build drive.\n',encoding='utf-8')
    from package_player_mods import RELEASES,write_player_zip
    RELEASES['ArenaPartyCrasher']['version']=VERSION;RELEASES['ArenaPartyCrasher']['notes']=NOTE
    result=write_player_zip(MOD,ROOT/'output'/('ArenaPartyCrasher-'+VERSION+'-Northstar.zip'))
    write(PROJECT/'release.json',result)
    ledger=ROOT/'output/player-distributions.json';entries=json.loads(ledger.read_text())
    entries['ArenaPartyCrasher']=result;write(ledger,entries)
    print('Packaged Party Crasher '+VERSION,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','publish'])
    a=p.parse_args();dict(build=build,publish=publish)[a.action]()
