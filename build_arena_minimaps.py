"""Build native Titanfall overview images from locally extracted Apex artwork.

No BSP, visibility, collision, world materials or client scripts are modified.
Original artwork is resized to Titanfall's 1024-pixel radar reference while
retaining the original world coverage. Apex units per pixel cannot be reused.
"""
import json
import shutil
import struct
import subprocess
from pathlib import Path

from build_phase_runner_presentation import guid
from extract_native_material import NativePak
from package_player_mods import runtime_files, digest
from restore_banner_display_textures import image_dds

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/minimaps'
MAPS = {
    'PhaseRunner': dict(map='mp_phase_runner', source='mp_rr_arena_phase_runner',
        pack='phase_runner_minimap', corner=(-8099, 7514), scale=16.015625,
        source_scale=4, source_size=(4100, 4100), size=(1024, 1024),
        source_corner=(17901, 26514), offset=(26000, 19000, 0),
        image='tools/legion/exported_files/atlases/0xcb0551f3b6dbf270/0xdc6144f3.dds'),
    'ArenaComposite': dict(map='mp_arena_composite', source='mp_rr_arena_composite',
        pack='drop_off_minimap', corner=(-7196, 10181), scale=14,
        source_scale=3.5, source_size=(4096, 4096), size=(1024, 1024),
        source_corner=(-7196, 10181), offset=(0, 0, 0),
        image='tools/composite-legion/exported_files/atlases/0xf9872d702e9d0069/0xf5cf453c.dds'),
}


def overview(config):
    return '\n'.join([
        '"'+config['map']+'"', '{', '    "assets"', '    {',
        '        "minimap" "overviews/'+config['map']+'"', '    }',
        '    "pos_x" "'+str(config['corner'][0])+'"',
        '    "pos_y" "'+str(config['corner'][1])+'"',
        '    "scale" "'+str(config['scale'])+'"',
        '    "displayDist" "2048"', '    "threatMaxDist" "2500"',
        '    "threatNearDist" "500"', '    "threatFarDist" "2000"', '}', '',
    ])


def verify_pack(path, config):
    pak = NativePak(path)
    assert sorted(a['type'] for a in pak.assets) == ['txtr', 'uimg']
    uimg = next(a for a in pak.assets if a['type'] == 'uimg')
    assert uimg['version'] == 10
    # Follow stock overview atlas naming; image hash also verified below.
    assert uimg['guid'] == guid('ui_image_atlas/overviews/'+config['map']+'.rpak')
    header = pak.address(uimg['header'])
    assert struct.unpack_from('<4H', pak.data, header+8) == (*config['size'], 1, 0)
    pointer = lambda at: pak.address(struct.unpack_from('<2I', pak.data, header+at))
    assert struct.unpack_from('<8f', pak.data, pointer(16)) == (0, 0, 1, 1, 0, 0, 1, 1)
    assert struct.unpack_from('<2H', pak.data, pointer(24)) == config['size']
    names = pointer(48)
    name = pak.data[names:pak.data.index(0, names)].decode('ascii')
    assert name == 'overviews/'+config['map']
    image_guid = guid(name)
    assert struct.unpack_from('<I', pak.data, pointer(40))[0] == ((image_guid & 0xffffffff) ^ (image_guid >> 32))
    assert struct.unpack_from('<4f', pak.data, pak.address(uimg['cpu'])) == (0, 0, 1, 1)
    texture = next(a for a in pak.assets if a['type'] == 'txtr')
    assert struct.unpack_from('<Q', pak.data, header+56)[0] == texture['guid']
    assert texture['guid'] == guid('texture/overviews/'+config['map']+'.rpak')
    return dict(ui_image=name, size=config['size'], bytes=path.stat().st_size,
                sha256=digest(path), asset_types=['txtr', 'uimg'])


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = OUT/'baseline-runtime.json'
    if not baseline.exists():
        baseline.write_text(json.dumps({name: {p.relative_to(ROOT/'northstar'/name).as_posix(): digest(p)
            for p in runtime_files(ROOT/'northstar'/name)} for name in MAPS}, indent=2))
    reports = {}
    for package, config in MAPS.items():
        work = OUT/config['pack']
        texture = 'texture/overviews/'+config['map']+'.rpak'
        target = (work/'assets'/texture).with_suffix('.dds')
        target.parent.mkdir(parents=True, exist_ok=True)
        image = image_dds(ROOT/config['image'])
        assert image.size == config['source_size']
        assert config['scale']*1024 == config['source_scale']*image.width
        from PIL import Image
        image = image.resize(config['size'], Image.Resampling.LANCZOS)
        png = work/'source.png'
        image.save(png)
        # Preserve original full-map bounds, orientation, alpha and sRGB colour.
        subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-f', 'BC7_UNORM_SRGB',
                        '-m', '1', '-y', '-o', str(target.parent), str(png)], check=True)
        shutil.move(str(target.parent/'source.dds'), target)
        manifest = dict(version=7, name=config['pack'], keepDevOnly=True,
            assetsDir=str(work/'assets'), outputDir=str(work/'build'), compressLevel=0,
            hasDynamicLibrary=False, files=[dict(_type='uimg',
            _path='ui_image_atlas/overviews/'+config['map']+'.rpak', atlas=texture,
            images=[dict(path='overviews/'+config['map'], posX=0, posY=0,
                         width=image.width, height=image.height)])])
        (work/'build.json').write_text(json.dumps(manifest, indent=2))
        process = subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(work/'build.json')],
                                 capture_output=True, text=True)
        (work/'build.log').write_text(process.stdout+process.stderr)
        process.check_returncode()
        built = work/'build'/(config['pack']+'.rpak')
        report = verify_pack(built, config)
        mod = ROOT/'northstar'/package
        shutil.copy2(built, mod/'paks'/built.name)
        dest = mod/'mod/resource/overviews'/(config['map']+'.txt')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(overview(config), encoding='ascii')
        mapping = mod/'paks/rpak.json'
        before = work/'rpak-before.json'
        if not before.exists(): shutil.copy2(mapping, before)
        value = json.loads(mapping.read_text())
        value.setdefault('Postload', {}).pop(built.name, None)
        value[built.name] = '^'+config['map']+'$'
        mapping.write_text(json.dumps(value, indent=2)+'\n')
        report.update(config, image_sha256=digest(ROOT/config['image']),
                      overview_sha256=digest(dest), native_runtime_verified=False)
        reports[package] = report
    (OUT/'build-report.json').write_text(json.dumps(reports, indent=2))
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    build()
