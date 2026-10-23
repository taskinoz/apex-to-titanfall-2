"""Lay out an RSX export of a current Apex map the way the port pipeline expects Legion's.

RSX (extract_apex_current.py, plus a material export run from the map folder)
writes `exported_files/material/<name>_<shader>/<name>_<sem>.dds` with a
`<name>_<shader>.json` whose `$textureTypes` gives each slot's semantic
(`_col`, `_nml`, ...). Two-layer materials list each semantic twice: first
and second layer. Legion's layout, read by prepare_composite_materials.py and
the blend/emission steps, is `materials/<base>/<base>_<semantic>Texture.dds`
with `albedo2Texture` etc. for the second layer.

World materials come from `<base>_wldc`; model materials are per-model copies
`<model>_<base>_rgdp` (or `_rgdc`), and the first copy found provides `<base>`.
Model Cast folders are linked under legion/exported_files/models.

  python adapt_rsx_exports.py mp_rr_thunderdome thermal-or-port-ident
"""
import collections
import json
import os
import shutil
import sys
from pathlib import Path

SEMANTIC = {'_col': 'albedo', '_nml': 'normal', '_gls': 'gloss', '_spc': 'spec', '_ao': 'ao', '_det': 'detail',
            '_bm': 'layerBlend', '_opa': 'opacityMultiply', '_ilm': 'emissive', '_emi': 'emissive', '_cav': 'cavity',
            '_msk': 'mask', '_dis': 'uvDistortion'}
SHADERS = ('_wldc', '_wld', '_rgdp', '_rgdc', '_sknp', '_skn')


# Retail emission tints are not reflected yet (atmosphere uses unit tints), so an `_ilm` map is
# treated as emission only when it is a sparse light mask; mostly-bright ones (water wetness /
# reflection masks, mean 187 on td2_wetlands_water_screen_01_bm) would glow white.
EMISSIVE_MAX_MEAN = 100


def mean_luminance(dds):
    import subprocess, tempfile
    import numpy as np
    from PIL import Image
    tool = Path(__file__).resolve().parent/'tools/directxtex/texconv.exe'
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([str(tool), '-nologo', '-y', '-ft', 'png', '-f', 'R8G8B8A8_UNORM', '-w', '64', '-h', '64', '-o', tmp, str(dds)],
                       capture_output=True, check=True)
        return float(np.asarray(Image.open(Path(tmp)/(dds.stem+'.png')).convert('L')).mean())


def adapt(source_map, dest):
    src = Path('D:/Games/ApexToTitanfallWork/apex-current')/source_map
    mats = src/'rsx-export/exported_files/material'
    out = Path(dest)/'legion/exported_files'; (out/'materials').mkdir(parents=True, exist_ok=True)
    done, report = set(), collections.Counter()
    # Prefer world (_wldc) copies, then model copies, so a base name maps to its world look when both exist.
    folders = sorted(mats.iterdir(), key=lambda f: (not f.name.endswith('_wldc'), f.name))
    for folder in folders:
        stem = folder.name; shader = next((s for s in SHADERS if stem.endswith(s)), None)
        if shader is None:
            report['unknown shader'] += 1; continue
        spec_path = folder/(stem+'.json')
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text())
        name = spec['name'].replace('\\', '/').rsplit('/', 1)[-1].lower()
        bases = [name]
        if shader != '_wldc':
            # Model materials: <model>_<base>; Cast meshes name the <base> part.
            bases = [name.split('_', i)[-1] for i in range(1, name.count('_')+1)] + [name]
        textures = spec.get('$textures', {}); types = spec.get('$textureTypes', {}); seen = collections.Counter(); files = {}
        for slot in sorted(textures, key=int):
            kind = types.get(slot); path = textures[slot]
            if not kind or not path.endswith('.rpak') or kind not in SEMANTIC:
                continue
            seen[kind] += 1
            if seen[kind] > 2:
                continue
            dds = folder/(Path(path).stem+'.dds')
            if dds.exists():
                if kind == '_ilm' and mean_luminance(dds) >= EMISSIVE_MAX_MEAN:
                    report['bright _ilm treated as mask'] += 1; continue
                files[SEMANTIC[kind]+('2' if seen[kind] == 2 else '')] = dds
        if 'albedo' not in files:
            report['no albedo'] += 1; continue
        for base in bases:
            if base in done:
                continue
            target = out/'materials'/base; target.mkdir(exist_ok=True)
            for semantic, dds in files.items():
                link = target/(f'{base}_{semantic}Texture.dds')
                if not link.exists():
                    try:
                        os.link(dds, link)
                    except OSError:
                        shutil.copy2(dds, link)
            (target/(base+'.rsx.json')).write_text(json.dumps(dict(source=stem, shader=shader[1:], spec=spec), indent=1))
            done.add(base); report[shader] += 1
    # Models: link Cast folders where asset_index() looks.
    models = out/'models'; models.mkdir(exist_ok=True); linked = 0
    for folder in (src/'models').iterdir():
        target = models/folder.name
        if not target.exists():
            os.symlink(folder, target, target_is_directory=True) if os.name != 'nt' else \
                __import__('subprocess').run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(target), str(folder)], check=True, capture_output=True)
            linked += 1
    print(json.dumps(dict(materials=len(done), by_shader=dict(report), models_linked=linked)), flush=True)


if __name__ == '__main__':
    adapt(sys.argv[1], sys.argv[2])
