"""Classify source materials whose albedo UVs are projected from world position.

Apex "wld" pixel shaders rebuild the world position (`add r0.xyz, v1.xyz, cb2[0]`)
and derive texture coordinates as (x, -y) . c_uvNRotScale + c_uvNTranslate. The
converted meshes carry raw world coordinates in those UV slots, so textures
repeat every unit and collapse to a flat average colour. This traces the
albedo (t0) sample back to the c_uvN slot that feeds it, from DXBC disassembly.
"""
import json
import re
import sys
from pathlib import Path

from apex_material_constants import ApexMaterials
from inspect_apex_shader import disassemble
from new_arena_ports import CONFIG, folder

# cb0 layout: c_uvN occupies 24 bytes from (N-1)*24: RotScaleX, RotScaleY, Translate.
TRANSLATE = {f'cb0[{(16+24*i)//16}].{"xyzw"[((16+24*i)%16)//4]}': i+1 for i in range(5)}


def albedo_source(ps, texture=0):
    """Return the c_uvN slot and source (world/mesh) feeding a texture's sample (t0 = albedo)."""
    lines = [l.strip() for l in ps.splitlines() if l.strip() and not l.lstrip().startswith('//')]
    for i, line in enumerate(lines):
        m = re.match(r'sample\S*\(texture2d\)\S* r\d+\.\w+, (\w+)\.(\w)\w*, t%d\.' % texture, line)
        if not m:
            continue
        reg, comp = m.group(1), m.group(2)
        if reg.startswith('v'):
            return dict(kind='mesh', slot=None)
        temp = scroll = None
        # 1. The instruction writing reg.<comp>: add/mad with a translate constant.
        for j in range(i-1, -1, -1):
            w = re.match(r'(add|mad) %s\.(\w+), (.*)' % reg, lines[j])
            if not w or comp not in w.group(2):
                continue
            k = w.group(2).index(comp)
            ops = [o.strip() for o in w.group(3).split(',')]
            src = next(o for o in ops if o.startswith('r'))
            name, swz = src.split('.')
            temp = (name, swz[min(k, len(swz)-1)], j)
            scroll = w.group(1) == 'mad' and any('cb2[0].x' in o for o in ops)
            break
        if not temp:
            return dict(kind='unknown', register=reg)
        # 2. The dp2 that produced that temporary component.
        for j in range(temp[2]-1, -1, -1):
            d = re.match(r'dp2 %s\.(\w+), (\w+)\.(\w+), cb0\[(\d+)\]\.(\w)' % temp[0], lines[j])
            if not d or temp[1] not in d.group(1):
                continue
            offset = int(d.group(4))*16+'xyzw'.index(d.group(5))*4
            slot, part = divmod(offset, 24)
            source = d.group(2)
            if source.startswith('v'):
                kind = 'mesh'
            else:
                defined = any(re.match(r'add %s\.xyz, v\d+\.xyzx, cb2\[0\]' % source, l) for l in lines[:j])
                kind = 'world' if defined and d.group(3).startswith('xw') else 'unknown'
            if part != 0:
                kind = 'unknown'
            return dict(kind=kind, slot=slot+1, scroll=scroll)
        return dict(kind='unknown', register=reg)
    return dict(kind='no-albedo')


def classify(ident):
    out = folder(ident)
    src = ApexMaterials(out/'paks'/(CONFIG[ident]['source']+'.rpak'))
    cache = out/'shader-inspection'
    scene = json.loads((out/'scene.json').read_text())
    result = {}
    for name in sorted(scene['materials']):
        if name not in src.materials:
            result[name] = dict(kind='not-in-source-pak', triangles=scene['materials'][name])
            continue
        path = cache/(name+'-ps.txt')
        try:
            if not path.exists():
                disassemble(src, name, cache)
            info = albedo_source(path.read_text(errors='replace'))
        except Exception as error:
            info = dict(kind='error', error=str(error))
        if info.get('slot'):
            values, _ = src.constants(name)
            n = info['slot']
            info.update(rot_x=values[f'c_uv{n}RotScaleX'], rot_y=values[f'c_uv{n}RotScaleY'],
                        translate=values[f'c_uv{n}Translate'])
        info['triangles'] = scene['materials'][name]
        result[name] = info
    (out/'world-uv-materials.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    import collections
    for ident in sys.argv[1:] or ['party-crasher', 'firing-range', 'overflow']:
        r = classify(ident)
        kinds = collections.Counter(v['kind'] for v in r.values())
        tris = collections.Counter()
        for v in r.values():
            tris[v['kind']] += v['triangles']
        print(ident, dict(kinds), dict(tris), flush=True)
