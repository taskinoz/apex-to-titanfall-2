"""Draw omitted source props whose collision is baked into the world ("invisible objects").

An omitted static prop keeps its world-BVH collision, so players bump into
something that is not drawn (Party Crasher reports q33-q37). For a
new_arena_ports map this finds every omitted placement near reachable ground
whose own LOD0 surface lies on active collision but not on any drawn surface,
and draws it from its source VG (exact LOD, skin, UV, placement) in released
lightmap tiles. No collision is added: it already exists.

  python recover_invisible_props.py plan|materials|append overflow
"""
import argparse
import collections
import json
import struct
import sys
from pathlib import Path

import numpy as np
import recover_party_structure as structure
import recover_composite_details as recovery
from audit_world_draw_budget import audit
from new_arena_ports import CONFIG, ROOT, folder
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree

INDEX_CAPACITY = 3145728
INDEX_FRACTION = .98
PLAN_FRACTION = .975
NEAR = 6.0         # a prop surface sample "on" collision / a drawn surface
MIN_SAMPLES = 40
MIN_FRACTION = .3  # share of the prop surface on undrawn collision
REACH = 400
MAX_TRIANGLES = 3000  # larger LOD0 meshes use LOD1
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier', 'shimmer')


def paths(ident):
    out = folder(ident)
    return out, out/'invisible-props', out/'before-invisible-props', out/(CONFIG[ident]['target']+'.bsp')


def configure(ident):
    out, project, backup, bsp = paths(ident)
    structure.OUT, structure.PROJECT, structure.BACKUP = out, project, backup
    structure.TARGET, structure.SLUG, structure.SOURCE = CONFIG[ident]['target'], ident.replace('-', '_'), CONFIG[ident]['source']
    return out, project, backup, bsp


def surface(t, spacing=8.):
    from audit_collision_visibility import sample
    return sample(t, spacing)


def plan(ident):
    from analyse_visibility import render_triangles
    from audit_collision_visibility import native_collision
    out, project, backup, bsp = configure(ident)
    if (project/'result.json').exists():
        raise ValueError('Already applied; restore the snapshot to rebuild')
    project.mkdir(parents=True, exist_ok=True)
    scene = json.loads((out/'scene.json').read_text()); index = asset_index(ident)
    mapping = json.loads((out/'materials/mapping.json').read_text())['materials']
    reach = cKDTree(np.load(out/'visibility/reachable.npy'))
    tris, mesh_of, names = render_triangles(bsp)
    see = np.asarray([not any(w in n.lower() for w in ('sky', 'water')) for n in names])[mesh_of]
    drawn = cKDTree(surface(tris[see].astype('f8'), 8.)); coll = cKDTree(surface(native_collision(bsp), 8.))
    current = audit(bsp)['native_padded_indices']; room = INDEX_CAPACITY*PLAN_FRACTION-current
    from append_free_charts import free_tiles
    chart_room = len(free_tiles(bsp)); cache = {}; candidates = []
    for p in scene['omitted']:
        stem = Path(p['model']).stem.lower()
        if stem not in index or 'origin' not in p or reach.query(p['origin'])[0] > REACH+600:
            continue
        try:
            if (stem, 0) not in cache:
                cache[stem, 0] = load(index[stem], 0, True)
            raw, slots, skins = cache[stem, 0]
        except Exception:
            continue
        m = np.asarray(rotation(p['angles']))
        t = [np.asarray(s, 'f8').reshape(-1, 3, 12)[:, :, :3] for s in raw if len(s)]
        if not t:
            continue
        t = np.concatenate(t)@m.T*p['scale']+np.asarray(p['origin'])
        pts = surface(t); near_reach = reach.query(pts)[0] < REACH
        if near_reach.sum() < MIN_SAMPLES:
            continue
        on_coll = coll.query(pts)[0] < NEAR; on_drawn = drawn.query(pts)[0] < NEAR
        invisible = on_coll & ~on_drawn & near_reach
        if invisible.sum() >= MIN_SAMPLES and invisible.mean() >= MIN_FRACTION:
            candidates.append((int(invisible.sum()), p, round(float(invisible.mean()), 3)))
    candidates.sort(key=lambda c: (-c[0], c[1]['index']))
    selected, skipped, pieces = [], [], []; used = meshes = 0
    for score, p, frac in candidates:
        stem = Path(p['model']).stem.lower(); path = index[stem]
        try:
            levels = struct.unpack_from('<18Q', (path/(path.name+'.vg')).read_bytes(), 16)[13]
            raw, slots, skins = cache[stem, 0]; lod = 0
            if sum(len(s) for s in raw) > MAX_TRIANGLES and levels > 1:
                lod = 1; raw, slots, skins = load(path, 1, True)
            skin = skins[min(p['skin'], len(skins)-1)]; m = np.asarray(rotation(p['angles'])); local = []
            for section, slot in zip(raw, slots):
                name = skin[slot]
                if not len(section) or any(s in name.lower() for s in SKIP_SECTIONS):
                    continue
                if name not in mapping and not (out/'legion/exported_files/materials'/name/(name+'_albedoTexture.dds')).is_file():
                    raise ValueError('Source texture unavailable: '+name)
                s = np.asarray(section, 'f4').reshape(-1, 3, 12); t = s.copy()
                t[:, :, :3] = s[:, :, :3]@m.T*p['scale']+p['origin']; t[:, :, 3:6] = s[:, :, 3:6]@m.T
                t[:, :, 7] = 1-s[:, :, 7]; t[:, :, 11] = 255
                local.append((name, t))
            count = sum(len(t) for _, t in local)
            if not count:
                raise ValueError('No supported surface')
            cost = 3*(used+count)+3*(meshes+len(local)+(used+count)//512+1)
            if cost > room or used+count > chart_room:
                raise ValueError('Exceeds the %.1f%% planning ceiling' % (PLAN_FRACTION*100))
            selected.append(dict(p, folder=str(path), lod=lod, triangles=count, category='invisible-object', invisible_samples=score,
                                 invisible_fraction=frac, recovery='Exact source VG author LOD, skin, UV and placement',
                                 collision_triangles=0, collision_recovery='Existing world collision retained'))
            pieces.extend(local); used += count; meshes += len(local)
        except (KeyError, ValueError, OSError, struct.error) as error:
            skipped.append(dict(index=p['index'], model=p['model'], reason=str(error)))
    if not selected:
        raise ValueError('No invisible objects recovered')
    names_ = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(project/'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names_.index(n), 'i4') for n, t in pieces]),
             names=names_, collision=np.empty((0, 3, 3), 'f4'))
    report = dict(version=ident+'-invisible-props', added_props=len(selected), added_triangles=used, placements=selected,
                  skipped=skipped, candidates=len(candidates), baseline_padded_indices=current,
                  categories=dict(collections.Counter(Path(p['model']).stem for p in selected)),
                  maximum_world_index_fraction=INDEX_FRACTION)
    structure.write(project/'plan.json', report)
    print(json.dumps({k: report[k] for k in ('candidates', 'added_props', 'added_triangles')}), 'skipped', len(skipped), flush=True)
    for k, v in collections.Counter(Path(p['model']).stem for p in selected).most_common(20):
        print(f'  {v:3d} {k}')


def materials(ident):
    configure(ident); structure.materials()


def append(ident, bake_base):
    out, project, backup, bsp = configure(ident)
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = out, project, bsp, backup
    direction = -np.asarray(json.loads((out/'environment.json').read_text())['native_sun_normal'])
    from append_free_charts import append as append_free
    append_free(Path(bake_base), INDEX_FRACTION, str(structure.WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    from build_preview_stbsp import build
    build(out, out/'materials', CONFIG[ident]['target'], ident.replace('-', '_')+'_world')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'materials', 'append']); p.add_argument('ident', choices=sorted(CONFIG))
    p.add_argument('--bake-base')
    a = p.parse_args()
    if a.action == 'append':
        append(a.ident, a.bake_base or str(folder(a.ident)))
    else:
        dict(plan=plan, materials=materials)[a.action](a.ident)
