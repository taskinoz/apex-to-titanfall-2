"""Survey Apex two-layer (bm) materials: per-layer UV source and blend input.

For each material with an albedo2 texture, trace which c_uvN slot and source
(mesh UV or world position) feeds albedo, albedo2 and layerBlend, and whether
the blend input is vertex alpha or a z-up (normal) ramp. Titanfall's native bm
shader samples all layers with one UV, so layers must share one UV mapping.
"""
import json
import re
import sys
from pathlib import Path

from apex_material_constants import ApexMaterials
from classify_world_uv import albedo_source
from inspect_apex_shader import disassemble
from new_arena_ports import CONFIG, folder


def texture_slots(ps):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'^// (\w+Texture)\s+texture\s+\S+\s+2d\s+t(\d+)', ps, re.M)}


def survey(ident):
    out = folder(ident); src = ApexMaterials(out/'paks'/(CONFIG[ident]['source']+'.rpak'))
    scene = json.loads((out/'scene.json').read_text())['materials']; cache = out/'shader-inspection'
    result = {}
    for name, count in scene.items():
        d = out/'legion/exported_files/materials'/name
        if not d.is_dir() or not any('albedo2' in p.name for p in d.iterdir()) or name not in src.materials:
            continue
        path = cache/(name+'-ps.txt')
        if not path.exists():
            disassemble(src, name, cache)
        ps = path.read_text(errors='replace'); slots = texture_slots(ps)
        values, _ = src.constants(name)
        row = dict(triangles=count, ramp=values.get('c_layerBlendRamp', [None])[0])
        for tex in ('albedoTexture', 'albedo2Texture', 'layerBlendTexture'):
            if tex not in slots:
                row[tex] = None; continue
            info = albedo_source(ps, slots[tex])
            n = info.get('slot')
            if n:
                info.update(rot_x=values[f'c_uv{n}RotScaleX'], rot_y=values[f'c_uv{n}RotScaleY'], translate=values[f'c_uv{n}Translate'])
            row[tex] = info
        body = ps[ps.find('dcl_temps'):]
        row['zup'] = bool(re.search(r'mad r\d+\.\w, v\d+\.z, r\d+\.\w, -cb0\[21\]\.w', body))
        row['zup_params'] = dict(min=values.get('c_zUpBlendingMinAngleCos'), max=values.get('c_zUpBlendingMaxAngleCos'),
                                 scale=values.get('c_zUpBlendingVertexAlphaAndL0_albedoTint', [None])[0])
        result[name] = row
    (out/'layer-blend-survey.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    for ident in sys.argv[1:]:
        for n, r in sorted(survey(ident).items(), key=lambda kv: -kv[1]['triangles']):
            f = lambda i: None if not i else (i['kind'], i.get('slot'), [round(v, 5) for v in i.get('rot_x', [])])
            print(ident, r['triangles'], n, 'A', f(r['albedoTexture']), 'A2', f(r['albedo2Texture']), 'M', f(r['layerBlendTexture']), 'zup' if r['zup'] else '', r['ramp'])
