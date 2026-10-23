"""Name Legion's GUID-only texture exports by their material slot (R5R source packs).

Legion writes a texture as `0x<guid>.dds` when it has no name, so the material
step finds no `<name>_albedoTexture.dds` and draws the grey fallback (Thermal
Station's `building_walls_metal_03` looked flat and glared white). Apex v15
material headers point at their texture handles at offset 96 (end pointer at
104); slots 0-3 are albedo, normal, gloss and spec, as prepare_composite_materials
expects. Each matching GUID file is hard-linked under its semantic name.

  python recover_guid_textures.py thermal-station
"""
import json
import os
import shutil
import struct
import sys

from new_arena_ports import CONFIG, folder
from apex_material_constants import ApexMaterials

SLOTS = ('albedo', 'normal', 'gloss', 'spec')
TEXTURE_PTR = 96


def recover(ident):
    out = folder(ident); root = out/'legion/exported_files/materials'
    src = ApexMaterials(out/'paks'/(CONFIG[ident]['source']+'.rpak'))
    lower = {k.lower(): k for k in src.materials}; report = {}
    for d in sorted(root.iterdir()):
        if not d.is_dir() or (d/(d.name+'_albedoTexture.dds')).exists():
            continue
        guids = {int(f.stem[2:], 16): f for f in d.glob('0x*.dds')}
        key = lower.get(d.name.lower())
        if not guids or key is None:
            continue
        a = src.materials[key]; h = src.address(a['header'])
        start = src.address(struct.unpack_from('<2I', src.data, h+TEXTURE_PTR))
        end = src.address(struct.unpack_from('<2I', src.data, h+TEXTURE_PTR+8))
        if start is None or end is None or not 0 < end-start <= 512:
            continue
        handles = struct.unpack_from('<'+'Q'*((end-start)//8), src.data, start); named = {}
        for slot, semantic in enumerate(SLOTS):
            if slot < len(handles) and handles[slot] in guids:
                target = d/f'{d.name}_{semantic}Texture.dds'
                try:
                    os.link(guids[handles[slot]], target)
                except OSError:
                    shutil.copy2(guids[handles[slot]], target)
                named[semantic] = guids[handles[slot]].name
        if named:
            report[d.name] = named
    (out/'guid-textures.json').write_text(json.dumps(report, indent=2))
    print(ident, 'materials recovered from GUID textures:', len(report), flush=True)


if __name__ == '__main__':
    recover(sys.argv[1])
