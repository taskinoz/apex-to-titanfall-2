"""Restore source facade sections and roof equipment without rebuilding the base.

The receipt and immutable snapshot make this a one-shot append. Existing HDR
materials, old lightmap charts, probes, scripts and the shared UI are retained.
"""
import argparse
import collections
import json
import os
import shutil
import struct
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, WORK, folder
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
import recover_composite_details as recovery

OUT = folder('party-crasher')
PROJECT = OUT / 'structure-recovery'
BACKUP = OUT / 'before-0.4.0'
TRIANGLE_ALLOWANCE = 74000
INDEX_FRACTION = .98


def write(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.new')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temp, path)


def category(model):
    name = Path(model).stem.lower()
    # These dense inset/window modules cost 30,904 triangles for 15 props.
    # Boundary coverage and complete roof arrays take precedence this round.
    if name in ('citymodern_wall_128x256_window_dtown_a',
                'citymodern_wall_128x384_window_dtown_a',
                'citymodern_wall_256x384_window_dtown_a',
                'citymodern_wall_384x256_window_dtown_a'):
        return None
    if 'window' in name and 'window_256x128_seta_' not in name:
        return 'facade'
    if name in ('citymodern_wall_32x128_concrete_dtown_c',
                'citymodern_wall_8x128_concrete_corner_b',
                'citymodern_wall_8x64_concrete_corner_b',
                'party_crashers_small_building_ext_04'):
        return 'facade'
    if name == 'vent_roof_03_tallflat':
        return 'roof-vent'
    if name == 'solar_panel_colony_single_02':
        return 'roof-solar'
    if name in ('olympus_rock_mountain_01', 'olympus_rock_mountain_02', 'olympus_rock_mountain_03'):
        return 'edge-rock'
    return None


def plan():
    if (PROJECT / 'result.json').exists():
        raise ValueError('Already applied; use the immutable snapshot to rebuild')
    PROJECT.mkdir(parents=True, exist_ok=True)
    scene = json.loads((OUT / 'scene.json').read_text())
    present = {p['index'] for p in scene['placements']}
    index = asset_index('party-crasher')
    groups = collections.defaultdict(list)
    for p in scene['omitted']:
        kind = category(p['model'])
        if kind:
            groups[kind].append(p)
    selected, skipped, pieces, physics, cache = [], [], [], [], {}
    used = 0
    mapping = json.loads((OUT / 'materials/mapping.json').read_text())['materials']
    recovery.ARMS = set()  # Composite's SMD exceptions do not apply to this map.
    for kind in ('facade', 'roof-vent', 'roof-solar', 'edge-rock'):
        for p in sorted(groups[kind], key=lambda p: p['index']):
            if p['index'] in present:
                raise ValueError('Duplicate source placement')
            try:
                path = index[Path(p['model']).stem.lower()]
                if path not in cache:
                    levels = struct.unpack_from('<18Q', (path / (path.name+'.vg')).read_bytes(), 16)[13]
                    last_detail = 4 if Path(p['model']).stem in ('olympus_rock_mountain_02', 'olympus_rock_mountain_03') else 3
                    lod = min(last_detail, levels-1)
                    raw, slots, skins = load(path, lod, True)
                    cache[path] = [np.asarray(s, 'f4').reshape(-1, 3, 12) for s in raw], slots, skins, lod
                raw, slots, skins, lod = cache[path]
                skin = skins[min(p['skin'], len(skins)-1)]
                matrix = np.asarray(rotation(p['angles']))
                local = []
                for section, slot in zip(raw, slots):
                    name = skin[slot]
                    if not len(section) or any(s in name.lower() for s in
                            ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')):
                        continue
                    if name not in mapping and not (OUT / 'legion/exported_files/materials' / name /
                                                   (name+'_albedoTexture.dds')).is_file():
                        raise ValueError('Source texture unavailable: '+name)
                    t = section.copy()
                    t[:, :, :3] = section[:, :, :3] @ matrix.T * p['scale'] + p['origin']
                    t[:, :, 3:6] = section[:, :, 3:6] @ matrix.T
                    t[:, :, 7] = 1-section[:, :, 7]
                    t[:, :, 11] = 255
                    local.append((name, t))
                count = sum(len(t) for _, t in local)
                if not count or used+count > TRIANGLE_ALLOWANCE:
                    raise ValueError('No supported surface or remaining triangle allowance')
                row = dict(p, folder=str(path), lod=lod, triangles=count, category=kind,
                           recovery='Exact source VG, authored LOD, skin, UV and placement')
                col, method = recovery.collision(row, raw)
                row.update(collision_triangles=len(col), collision_recovery=method)
                selected.append(row)
                pieces.extend(local)
                physics.append(col)
                used += count
            except (KeyError, ValueError, OSError, struct.error) as error:
                skipped.append(dict(index=p['index'], model=p['model'], reason=str(error)))
    if not selected:
        raise ValueError('No source geometry recovered')
    names = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(PROJECT / 'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names.index(n), 'i4') for n, t in pieces]),
             names=names, collision=np.concatenate(physics))
    report = dict(version='0.4.0', added_props=len(selected), added_triangles=used,
                  placements=selected, skipped=skipped,
                  categories=dict(collections.Counter(p['category'] for p in selected)),
                  allowance=TRIANGLE_ALLOWANCE, maximum_world_index_fraction=INDEX_FRACTION,
                  policy='Complete source modules; no guessed planes, placement offsets or entity slots. '
                         'Complete authored roof arrays and boundary mountains; existing scene retained.')
    write(PROJECT / 'plan.json', report)
    print(json.dumps({k:report[k] for k in ('added_props', 'added_triangles', 'categories', 'skipped')}), flush=True)


def snapshot():
    if BACKUP.exists():
        raise ValueError('Snapshot already exists; do not overwrite the rollback')
    BACKUP.mkdir(parents=True)
    for name in ('mp_party_crasher.bsp', 'mp_party_crasher.stbsp', 'scene.npz', 'scene.json',
                 'physics.npz', 'physics.json', 'source-build.json', 'materials/mapping.json',
                 'materials/build.json', 'materials/build/party_crasher_world.rpak'):
        source, target = OUT / name, BACKUP / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    # The live RPak may be hard-linked to a staged/installed package. Detach
    # before RePak opens it, so neither rollback nor accepted mod is mutated.
    live = OUT / 'materials/build/party_crasher_world.rpak'
    temp = live.with_suffix('.detached.rpak')
    shutil.copy2(live, temp)
    os.replace(temp, live)


def materials():
    if not BACKUP.exists():
        snapshot()
    old = json.loads((BACKUP / 'materials/mapping.json').read_text())
    addition = np.load(PROJECT / 'addition.npz')
    names, ids = list(addition['names']), addition['material']
    scene = json.loads((OUT/'scene.json').read_text())
    counts = dict(json.loads((BACKUP/'scene.json').read_text())['materials'])
    for i, name in enumerate(names):
        counts[str(name)] = counts.get(str(name),0)+int((ids==i).sum())
    scene['materials'] = counts
    write(OUT/'scene.json',scene)
    new = {str(n):int((ids == i).sum()) for i, n in enumerate(names) if n not in old['materials']}
    addition.close()
    if not new:
        return
    # Stage only new materials in a separate project, then merge their files.
    # Regenerating the whole world pack would erase accepted HDR adaptations.
    stage_scene = PROJECT / 'new-material-scene.json'
    write(stage_scene, dict(materials=new))
    import prepare_composite_materials as prepare
    prepare.OUT = PROJECT / 'materials'
    prepare.prepare(stage_scene, [OUT / 'legion/exported_files/materials'], 'party_crasher')
    mdir = prepare.OUT
    staged = json.loads((mdir / 'mapping.json').read_text())
    manifest = json.loads((OUT / 'materials/build.json').read_text())
    files = {f['_path']:f for f in manifest['files']}
    extras = json.loads((mdir / 'build.json').read_text())
    # Never overwrite an existing material/texture/shader source.
    for f in extras['files']:
        if f['_path'] in files:
            continue
        path = f['_path']
        extensions = ('json', 'uber') if f['_type']=='matl' else ('dds',) if f['_type']=='txtr' else ('msw',)
        for ext in extensions:
            source = (mdir / 'assets' / path).with_suffix('.'+ext)
            target = (OUT / 'materials/assets' / path).with_suffix('.'+ext)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        files[path] = f
    old['materials'].update({n:staged['materials'][n] for n in new})
    from recover_arena_atmosphere import NativeMaterials, tint
    from apex_material_constants import ApexMaterials
    from PIL import Image
    manifest['files'] = list(files.values())
    builder = NativeMaterials(OUT / 'materials', 'party_crasher', manifest)
    source = ApexMaterials(OUT / 'paks/mp_rr_party_crasher.rpak')
    adapted = []
    for name in new:
        r = old['materials'][name]
        if r['transparent']:
            # Crack decals, fence cutouts and search-light lenses use the tested world-alpha preset.
            if not (name.startswith('decals_cracks_') or 'fence' in name or name.startswith('search_light_glass')):
                raise ValueError('New structural material needs explicit alpha review: '+name)
            # Cracks are source overlays, not holes in the underlying rock.
            # Keep the tested world-alpha preset and its derived opacity map.
            target = (OUT/'materials/assets'/r['textures']['0']).with_suffix('.dds')
            raw = bytearray(target.read_bytes())
            if raw[84:88] == b'DX10':
                fmt = struct.unpack_from('<I', raw, 128)[0]
                if fmt in (71,74,77,98):
                    struct.pack_into('<I',raw,128,fmt+1)
                    target.write_bytes(raw)
            adapted.append(dict(material=name, native_source_channels='Source crack overlay with explicit alpha'))
            continue
        values, _ = source.constants(name)
        colour = tint(values, 'c_zUpBlendingVertexAlphaAndL0_albedoTint')
        textures = dict(r['textures'])
        for slot, semantic, neutral in [('1','normal',(128,128,255,255)),
                                       ('2','gloss',(30,30,30,255)), ('3','spec',(8,8,8,255))]:
            if slot not in textures:
                textures[slot] = builder.texture('neutral_'+semantic, image=Image.new('RGBA',(4,4),neutral))
        path = 'material/'+r['name']+'_wld.rpak'
        cpath = 'material/'+r['name']+'_colpass_wld.rpak'
        for destination in (cpath, path):
            spec = json.loads((OUT/'materials/assets'/destination).with_suffix('.json').read_text())
            uber = (OUT/'materials/assets'/destination).with_suffix('.uber').read_bytes()
            # Source COLOR fields on rock blend layers are weights, not RGB.
            builder.write(destination, r['name']+('_colpass' if destination==cpath else ''),
                          spec, uber, textures, colour, colpass=cpath if destination==path else None)
        r.update(textures=textures, native_source_channels='Source albedo tint/PBR; blend weights excluded from RGB tint')
        adapted.append(dict(material=name, source_albedo_tint=colour))
    builder.finish(manifest)
    write(OUT / 'materials/mapping.json', old)
    write(PROJECT / 'materials.json', dict(new_materials=adapted, baseline_materials_preserved=True))


def append():
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = OUT, PROJECT, OUT/'mp_party_crasher.bsp', BACKUP
    direction = -np.asarray(json.loads((OUT / 'environment.json').read_text())['native_sun_normal'])
    recovery.append(OUT/'signage-recovery', INDEX_FRACTION,
                    str(WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_party_crasher', 'party_crasher_world')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan','materials','append'])
    args = p.parse_args()
    dict(plan=plan, materials=materials, append=append)[args.action]()
