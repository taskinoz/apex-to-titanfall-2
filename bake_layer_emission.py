"""Bake a two-layer emissive blend material (lava under crust) into the native single-layer textures.

Thermal Station's `volcanic_ground_03_wld_lava_scroll_bm` is crust (albedo2) over scrolling lava (albedo, black,
with a grey flow emissive), mixed by layerBlend (white crust, black cracks); Apex tints the lava in its stripped
shader. The native material draws layer 0 only, so the whole surface glowed untinted grey-white. This writes
albedo = crust where the mask is crust, and emissive = flow x crack mask x CONFIG[ident]['layer_emission'][name]
(the lava RGB), over the textures recover_arena_atmosphere.py built, then rebuilds the world RPak. Run after
recover_arena_atmosphere.py and before add_ring_wall.py:

  python bake_layer_emission.py thermal-station
"""
import json
import subprocess
import sys

import numpy as np
from PIL import Image
from new_arena_ports import CONFIG, ROOT, folder
from restore_banner_display_textures import image_dds

SIZE = 1024


def load(path, mode):
    return np.asarray(image_dds(path).convert(mode).resize((SIZE, SIZE), Image.Resampling.LANCZOS)).astype('f4')/255


def save(rgb, path):
    png = path.with_suffix('.png'); Image.fromarray(np.clip(rgb*255+.5, 0, 255).astype('u1')).save(png)
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-srgb', '-f', 'BC3_UNORM_SRGB', '-o', str(path.parent), str(png)],
                   check=True, capture_output=True)
    png.unlink()  # texconv wrote <stem>.dds over path


def bake(ident):
    out = folder(ident); slug = ident.replace('-', '_'); report = {}
    for name, colour in CONFIG[ident].get('layer_emission', {}).items():
        src = out/'legion/exported_files/materials'/name; t = lambda s: src/f'{name}_{s}Texture.dds'
        crust = load(t('layerBlend'), 'L')[..., None]
        albedo = load(t('albedo2'), 'RGB')*crust + load(t('albedo'), 'RGB')*(1-crust)
        emissive = load(t('emissive'), 'L')[..., None]*(1-crust)*np.asarray(colour, 'f4')/255
        built = out/'materials/assets/texture'/slug
        save(albedo, built/f'{name}_albedo.dds'); save(emissive, built/f'{name}_emissive.dds')
        report[name] = dict(crack_fraction=round(float((crust < .5).mean()), 3), lava=colour)
    if report:
        subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(out/'materials/build.json')], check=True, capture_output=True)
    (out/'layer-emission.json').write_text(json.dumps(report, indent=2))
    print(ident, 'baked layer emission', report, flush=True)


if __name__ == '__main__':
    bake(sys.argv[1])
