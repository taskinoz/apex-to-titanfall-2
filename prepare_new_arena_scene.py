"""Recover exact source triangles and authored model LODs for approved ports."""
import collections
import json
import struct
import sys
from pathlib import Path
from new_arena_ports import CONFIG, ROOT, folder, source_bsp

sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
import numpy as np
import bsp_tool
from bsp_tool.branches.respawn.apex_legends import GameLump_SPRP
from read_vg_static import load
from stage_prop_geometry import rotation, material_basename
from plan_arena_fill import model_index
from prepare_composite_scene import sky_dome
from repair_environment_lighting import entities


def asset_index(ident):
    index = model_index()
    for root in (folder(ident) / 'legion/exported_files/models',):
        for p in root.rglob('*.rmdl'):
            if p.with_suffix('.vg').exists():
                index[p.stem.lower()] = p.parent
        for p in root.glob('*/*_LOD0.cast'):  # current Apex models exported by RSX as Cast
            index.setdefault(p.parent.name.lower(), p.parent)
    return index


def foliage(model):
    return any(w in model.lower() for w in ('foliage/', 'grass', 'flower', 'bush', 'plant', 'tree'))


def essential(model):
    return any(w in model.lower() for w in ('stairs', 'stair', 'railing', 'ramp', 'floor',
        'bridge', 'catwalk', 'wall', 'ceiling', 'levels_terrain', 'rock', 'door', 'crane', 'pipe', 'building'))


def priority(model):
    n=model.lower()
    if any(w in n for w in ('vent', 'drain', 'signage_plates', 'conduit_bracket')):return 5
    if any(w in n for w in ('stairs','stair','floor','walkway','bridge','ramp','roof','hull','ship','voyage','catwalk')):return 0
    if any(w in n for w in ('wall','railing','rail_','fence','crate','container','cover','barrier','beam','column','support','frame','tower_arm','pipe','tank','smelting','door','crane',
                            'cage','framework','ceiling','scaffold','girder')):return 1
    if any(w in n for w in ('rock','levels_terrain')):return 2
    if foliage(model):return 4
    return 3


def prepare(ident):
    c = CONFIG[ident]
    out = folder(ident)
    out.mkdir(parents=True, exist_ok=True)
    bsp = bsp_tool.load_bsp(str(source_bsp(ident)))
    geo = bsp.external
    # v52 light probe records differ in size; the port rebuilds its own probes.
    errors = {k: v for k, v in geo.loading_errors.items() if k != 'LIGHTPROBES'}
    if errors:
        raise ValueError(str(errors))
    sprp = geo.GAME_LUMP.sprp
    if not hasattr(sprp, 'props'):
        sprp = GameLump_SPRP.from_bytes(bytes(sprp))
    source_entities = entities(source_bsp(ident))
    env = next(e for e in source_entities if e.get('classname') == 'light_environment')
    offset = np.asarray(c['offset'], 'f4')
    low, high = np.asarray(c['bounds'], 'f4')
    world_parts = collections.defaultdict(list)
    skipped_world = collections.Counter()
    cached_world = out / 'world.npz'
    if not cached_world.exists() and (out/'scene.json').exists():
        previous=json.loads((out/'scene.json').read_text());old=np.load(out/'scene.npz');n=previous['world_triangles']
        np.savez(cached_world,triangles=old['triangles'][:n],material=old['material'][:n],names=old['names'])
        old.close()
    if cached_world.exists():
        old=np.load(cached_world);data=old['triangles'];mi=old['material'];names=old['names']
        for i in np.unique(mi):world_parts[str(names[i])].append(data[mi==i])
        old.close()
    for i, mesh in enumerate([] if cached_world.exists() else geo.MESHES):
        sort = geo.MATERIAL_SORTS[mesh.material_sort]
        name = geo.texture_data_surface_name(sort.texture_data)
        if name.startswith('tools/') or any(s in name.lower() for s in ('start_barrier', 'dev_gray_512_v_color')):
            skipped_world[name] += mesh.num_triangles
            continue
        start = mesh.first_mesh_index
        indices = np.asarray(geo.MESH_INDICES[start:start + mesh.num_triangles * 3], 'u4') + sort.vertex_offset
        from bsp_tool.branches.respawn.titanfall import MeshFlags
        record_name = (mesh.flags & MeshFlags.MASK_VERTEX).name
        records = getattr(geo, record_name)
        vertices = []
        for j in indices:
            v = records[int(j)]
            colour = list(getattr(v, 'colour', (255, 255, 255, 255)))
            colour[3] = 255
            vertices.append([*geo.VERTICES[v.position_index], *geo.VERTEX_NORMALS[v.normal_index],
                             *v.albedo_uv, *colour])
        t = np.asarray(vertices, 'f4').reshape(-1, 3, 12)
        t[:, :, :3] += offset
        keep = np.all((t[:, :, :3] >= low) & (t[:, :, :3] <= high), axis=(1, 2))
        skipped_world['outside conversion bounds'] += int((~keep).sum())
        if keep.any():
            world_parts[material_basename(name)].append(t[keep])
        if i % 500 == 0:
            print(ident, 'world meshes', i + 1, '/', len(geo.MESHES), flush=True)
    world_parts = {n: np.concatenate(parts) for n, parts in world_parts.items()}
    world_count = sum(len(t) for t in world_parts.values())
    if not cached_world.exists():
        names=list(world_parts)
        np.savez(cached_world,triangles=np.concatenate(list(world_parts.values())),
            material=np.concatenate([np.full(len(t),i,'i4') for i,t in enumerate(world_parts.values())]),names=np.asarray(names))
    props = []
    for i, p in enumerate(sprp.props):
        origin = np.asarray(list(p.origin)) + offset
        props.append(dict(index=i, model=sprp.model_names[p.model_name],
            origin=origin.tolist(), original_apex_origin=list(p.origin),
            angles=[p.angles.y, p.angles.z, p.angles.x], scale=p.scale, skin=p.skin,
            solid=p.solid_mode.value, flags=int(p.flags),
            in_region=bool(np.all(origin >= low) and np.all(origin <= high))))
    # Optional backdrop: named surrounding models (e.g. Thunderdome's stadium stands) beyond the play
    # bounds, kept at their cheapest planned LOD so the arena is not a floating island.
    backdrop = c.get('backdrop')
    if backdrop:
        blo, bhi = np.asarray(backdrop['box'], 'f4')
        for p in props:
            stem = Path(p['model']).stem.lower()
            if not p['in_region'] and any(w in stem for w in backdrop['models']) and                     np.all(np.asarray(p['origin']) >= blo) and np.all(np.asarray(p['origin']) <= bhi):
                p['in_region'] = True; p['backdrop'] = True
    local = [p for p in props if p['in_region']]
    index = asset_index(ident)
    cache, errors = {}, {}
    for model in dict.fromkeys(p['model'] for p in local):
        base = Path(model).stem.lower()
        path = index.get(base)
        if path is None:
            errors[model] = 'Compiled source model not recovered'
            continue
        try:
            from read_vg_static import levels as vg_levels
            levels = vg_levels(path)
            candidates = []
            for lod in range(min(levels, 3) if foliage(model) else levels):  # every author LOD (dense retail maps)
                sections, slots, skins = load(path, lod, with_colors=True)
                secs = [np.asarray(s, 'f4').reshape(-1, 3, 12) for s in sections]
                candidates.append((secs, slots, skins, lod, path))
            # Optional (dense retail maps): meshoptimizer-simplify the cheapest LOD of still-heavy props.
            simplify = c.get('simplify')
            if simplify and candidates and sum(len(s) for s in candidates[-1][0]) >= simplify['min_triangles'] and not foliage(model):
                from simplify_cache import cached
                secs, slots_, skins_, lod_, path_ = candidates[-1]
                simple = cached(path_, lod_, simplify['error'], out/'simplified')
                if simple is not None and len(simple) == len(secs) and sum(map(len, simple)) < sum(map(len, secs)):
                    candidates.append((simple, slots_, skins_, lod_, path_))
            cache[model] = candidates
        except (OSError, ValueError, struct.error) as e:
            errors[model] = str(e)
    counts = collections.Counter(p['model'] for p in local)
    backdrop_models = {p['model'] for p in local if p.get('backdrop')}
    levels = {m: (len(cs)-1 if m in backdrop_models else 0) for m, cs in cache.items()}
    cost = lambda item: sum(len(s) for s in item[0])
    total = sum(cost(cs[0]) * counts[m] for m, cs in cache.items())
    # Leave space for runtime batches, collision repairs and presentation.
    budget = c.get('triangle_budget', 920000) - world_count - len(sky_dome())
    while total > budget:
        savings = [(counts[m] * (cost(cs[levels[m]]) - cost(cs[levels[m] + 1])), m)
                   for m, cs in cache.items() if levels[m] + 1 < len(cs)]
        if not savings:
            break
        saving, model = max(savings)
        if saving <= 0:
            break
        levels[model] += 1
        total -= saving
    parts = collections.defaultdict(list)
    selected, omitted, used = [], [], 0
    local.sort(key=lambda p: (-1 if p.get('backdrop') else priority(p['model']),
                             p['solid'] not in (2, 6, 7), p['index']))
    for p in local:
        cs = cache.get(p['model'])
        if not cs:
            omitted.append(dict(p, reason=errors[p['model']]))
            continue
        sec, slots, skins, lod, path = cs[levels[p['model']]]
        if used + cost(cs[levels[p['model']]]) > budget:
            omitted.append(dict(p, reason='Conservative native draw budget'))
            continue
        skin = skins[min(p['skin'], len(skins) - 1)]
        matrix = np.asarray(rotation(p['angles']))
        count = 0
        for s, slot in zip(sec, slots):
            name = skin[slot]
            if not len(s) or name.lower() in ('toolsblack','toolsskybox') or any(w in name.lower() for w in ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')):
                continue
            t = s.copy()
            t[:, :, :3] = s[:, :, :3] @ matrix.T * p['scale'] + p['origin']
            t[:, :, 3:6] = s[:, :, 3:6] @ matrix.T
            t[:, :, 7] = 1 - s[:, :, 7]
            t[:, :, 11] = 255
            parts[name].append(t)
            count += len(t)
        if count:
            selected.append(dict(p, folder=str(path), lod=lod, triangles=count))
            used += count
        else:
            omitted.append(dict(p,reason='No supported render sections after tool/atmosphere filtering'))
    arrays, ids, names = [], [], []
    for name, t in world_parts.items():
        names.append(name); arrays.append(t); ids.append(np.full(len(t), len(names) - 1, 'i4'))
    sky = np.concatenate((sky_dome(), np.full((len(sky_dome()), 3, 4), 255, 'f4')), axis=2)
    names.append('sky'); arrays.append(sky); ids.append(np.full(len(sky), len(names) - 1, 'i4'))
    for name, sub in parts.items():
        t = np.concatenate(sub)
        if name not in names:
            names.append(name)
        arrays.append(t); ids.append(np.full(len(t), names.index(name), 'i4'))
    triangles = np.concatenate(arrays)
    material = np.concatenate(ids)
    for i, name in enumerate(names):
        if 'decal' in name.lower() or 'btt_wld' in name.lower():
            mask = material == i
            triangles[mask, :, :3] += triangles[mask, :, 3:6] * .12
    np.savez(out / 'scene.npz', triangles=triangles, material=material, names=np.asarray(names))
    report = dict(source_map=c['source'], target_map=c['target'], config=c,
        world_triangles=world_count, triangles=len(triangles), props=len(selected),
        placements=selected, omitted=omitted, source_static_placements=len(props),
        source_local_placements=len(local), source_outside_region=len(props) - len(local),
        source_offset=c['offset'], source_sun=env, source_entities=source_entities,
        model_decode_failures=errors, omitted_world_triangles=dict(skipped_world),
        materials={n: int((material == i).sum()) for i, n in enumerate(names)},
        bounds=[triangles[:, :, :3].min((0, 1)).tolist(), triangles[:, :, :3].max((0, 1)).tolist()],
        policy='Original transforms, source UVs/RGB, native alpha 255; authored LODs, <=920000 triangles; foliage <=LOD2')
    (out / 'scene.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (out / 'source-inventory.json').write_text(json.dumps(dict(props=props, entities=source_entities), indent=2))
    print(ident, 'scene', world_count, 'world;', used, 'prop triangles;', len(selected), 'props;', len(omitted), 'omitted', flush=True)


if __name__ == '__main__':
    for ident in CONFIG if sys.argv[1] == 'all' else [sys.argv[1]]:
        prepare(ident)
