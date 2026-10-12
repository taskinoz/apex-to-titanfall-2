"""Audit recoverable source placements against current native rendering budgets."""
import collections
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
import numpy as np
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY
from repair_preview_index_padding import read_lumps
from optimize_portalfree_render import material_name
from read_vg_static import load

OUT = ROOT/'output/arena-fill'
CONFIG = {
    'phase-runner': dict(package='PhaseRunner', map='mp_phase_runner', version='1.5.0'),
    'drop-off': dict(package='ArenaComposite', map='mp_arena_composite', version='0.9.0'),
}


def source_inventory(ident):
    if ident == 'phase-runner':
        rows = json.loads((ROOT/'docs/conversion/static-placement-inventory.json').read_text())
        present = {p['source_index'] for p in rows['placements'] if p['status']=='rendered'}
        props = json.loads((ROOT/'output/phase-runner/static-props.json').read_text())
        candidates = [p for p in props if p['index'] not in present and p['in_arena']]
    else:
        scene = json.loads((ROOT/'output/composite/scene.json').read_text())
        present = {p['index'] for p in scene['placements']}
        props = json.loads((ROOT/'output/composite/source-inventory.json').read_text())['props']
        omitted = {p['index'] for p in scene['omitted'] if p.get('reason')=='Budget'}
        # The source omission list is also the explicit local-arena filter.
        local = {p['index'] for p in scene['omitted']}
        candidates = [p for p in props if p['index'] not in present and p['index'] in local]
    return candidates, present


def model_index():
    folders = [ROOT/'tools/composite-legion/exported_files/models',
               ROOT/'tools/legion/exported_files/models',
               ROOT/'output/phase-runner/shared-assets/models',
               ROOT/'output/phase-runner/common-assets/exported_files/models',
               ROOT/'output/phase-runner/legion-assets/exported_files/models']
    index = {}
    for folder in folders:
        if folder.exists():
            for p in folder.rglob('*.rmdl'):
                if p.with_suffix('.vg').exists(): index.setdefault(p.stem.lower(), p.parent)
    return index


def native_materials(ident):
    config = CONFIG[ident]
    bsp = ROOT/'northstar'/config['package']/'mod/maps'/(config['map']+'.bsp')
    lumps = read_lumps(bsp, (2, 0x2b, 0x2c))
    result = {}
    for ti in range(len(lumps[2])//36):
        name = material_name(lumps, ti)
        result.setdefault(name.rsplit('/', 1)[-1].lower(), dict(index=ti, name=name,
            flags=struct.unpack_from('<I', lumps[2], ti*36+32)[0]))
    return result


def audit_sources():
    OUT.mkdir(parents=True, exist_ok=True)
    index = model_index()
    cache = {}
    reports = {}
    for ident, config in CONFIG.items():
        candidates, present = source_inventory(ident)
        native = native_materials(ident)
        counts = collections.Counter(p['model'] for p in candidates)
        rows = []
        for model, count in counts.items():
            stem = Path(model).stem.lower()
            folder = index.get(stem)
            try:
                if folder is None: raise ValueError('Compiled model unavailable')
                if stem not in cache:
                    levels = struct.unpack_from('<18Q', (folder/(folder.name+'.vg')).read_bytes(), 16)[13]
                    lod = min(levels-1, 3)
                    sections, slots, skins = load(folder, lod, with_colors=True)
                    cache[stem] = sections, slots, skins, lod
                sections, slots, skins, lod = cache[stem]
                materials = sorted({name for skin in skins for name in skin})
                rows.append(dict(model=model, count=count, folder=str(folder.relative_to(ROOT)), lod=lod,
                    triangles_each=sum(len(s) for s in sections), materials=materials,
                    existing_materials=[n for n in materials if n.lower() in native],
                    new_materials=[n for n in materials if n.lower() not in native]))
            except (ValueError, OSError, struct.error) as error:
                rows.append(dict(model=model, count=count, unavailable=str(error)))
        budget = audit(ROOT/'northstar'/config['package']/'mod/maps'/(config['map']+'.bsp'))
        report = dict(baseline_version=config['version'], known_rendered_source_placements=len(present),
            local_omitted_source_placements=len(candidates), budget=budget,
            proposed_world_fraction=.97, reserved_native_indices=WORLD_INDEX_CAPACITY-int(WORLD_INDEX_CAPACITY*.97),
            available_indices=int(WORLD_INDEX_CAPACITY*.97)-budget['native_padded_indices'], models=rows)
        (OUT/(ident+'-audit.json')).write_text(json.dumps(report, indent=2))
        reports[ident] = report
        print(ident, 'remaining', len(candidates), 'available triangles approximately',report['available_indices']//3)
        for row in sorted(rows, key=lambda r:(len(r.get('new_materials', [])), -r['count']))[:25]:
            print(' ', Path(row['model']).stem, row['count'], row.get('triangles_each'),
                  'new', row.get('new_materials', []), row.get('unavailable', ''))
    return reports


if __name__ == '__main__':
    audit_sources()
