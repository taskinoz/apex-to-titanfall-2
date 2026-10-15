"""Party Crasher 0.6.0: restore source props named in the user's 15 October reports.

Window wall modules and glass columns (p26, p29), the red screen towers that
carry the banners (p28), the rocks around the reported hole (p27) and the
Mirage seating set over the track (p25). Exact source transforms, skins and
PHY/BVH colliders; added in priority order under the 98% world-index ceiling,
after retire_render_meshes.py has freed budget. Reuses the 0.4.0
snapshot/material/append stages with a new immutable snapshot.
"""
import argparse
import collections
import json
import struct
from pathlib import Path

import numpy as np
import recover_party_structure as structure
from audit_world_draw_budget import audit
from new_arena_ports import folder
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
import recover_composite_details as recovery

OUT = folder('party-crasher')
PROJECT = OUT/'reported-recovery'
BACKUP = OUT/'before-0.6.0'
BAKE_BASE = 'detail-recovery'
INDEX_CAPACITY = 3145728
INDEX_FRACTION = .98
# Priority groups with the authored LOD used for each model. Collision always
# comes from the source PHY/BVH, independent of the visual LOD.
GROUPS = (
    ('track-set', {'mirage_tt_seating_area_01': 1}),
    ('screen-tower', {'thunderdome_screen_tower_01': 2}),
    ('window-wall', {'citymodern_wall_128x256_window_dtown_a': 0, 'citymodern_wall_128x384_window_dtown_a': 0,
                     'citymodern_wall_256x384_window_dtown_a': 0, 'citymodern_wall_384x256_window_dtown_a': 0}),
    ('rock', {'olympus_rocks_01': 1}),
    ('glass-column', {'citymodern_column_128x384_concrete_glass_a': 0}),
)
REPORTS = np.asarray([s['origin'] for f in ('party-crasher-user-report.json', 'party-crasher-user-report-2.json')
                      for s in json.loads((Path(__file__).resolve().parent/'test-harness/routes'/f).read_text())['shots']
                      if s['name'] != 'warmup'])
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')


def configure():
    structure.PROJECT, structure.BACKUP = PROJECT, BACKUP


def plan():
    configure()
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; use the immutable snapshot to rebuild')
    PROJECT.mkdir(parents=True, exist_ok=True)
    scene = json.loads((OUT/'scene.json').read_text())
    index = asset_index('party-crasher')
    mapping = json.loads((OUT/'materials/mapping.json').read_text())['materials']
    current = audit(OUT/'mp_party_crasher.bsp')['native_padded_indices']
    room = INDEX_CAPACITY*INDEX_FRACTION-current
    # New charts go into released tiles on any page (append_free_charts).
    from append_free_charts import free_tiles
    chart_room = len(free_tiles(OUT/'mp_party_crasher.bsp'))
    recovery.ARMS = set()
    selected, skipped, pieces, physics, cache = [], [], [], [], {}
    used = meshes = 0
    for kind, models in GROUPS:
        # Nearest to the user's reported camera positions first.
        group = sorted((p for p in scene['omitted'] if Path(p['model']).stem.lower() in models),
                       key=lambda p: (list(models).index(Path(p['model']).stem.lower()),
                                      float(np.min(np.linalg.norm(REPORTS-np.asarray(p['origin']), axis=1))), p['index']))
        for p in group:
            try:
                path = index[Path(p['model']).stem.lower()]
                lod = models[Path(p['model']).stem.lower()]
                if path not in cache:
                    levels = struct.unpack_from('<18Q', (path/(path.name+'.vg')).read_bytes(), 16)[13]
                    lod = min(lod, levels-1); raw, slots, skins = load(path, lod, True)
                    cache[path] = [np.asarray(s, 'f4').reshape(-1, 3, 12) for s in raw], slots, skins, lod
                raw, slots, skins, lod = cache[path]
                skin = skins[min(p['skin'], len(skins)-1)]
                matrix = np.asarray(rotation(p['angles']))
                local = []
                for section, slot in zip(raw, slots):
                    name = skin[slot]
                    if not len(section) or any(s in name.lower() for s in SKIP_SECTIONS):
                        continue
                    if name not in mapping and not (OUT/'legion/exported_files/materials'/name/
                                                   (name+'_albedoTexture.dds')).is_file():
                        raise ValueError('Source texture unavailable: '+name)
                    t = section.copy()
                    t[:, :, :3] = section[:, :, :3] @ matrix.T * p['scale'] + p['origin']
                    t[:, :, 3:6] = section[:, :, 3:6] @ matrix.T
                    t[:, :, 7] = 1-section[:, :, 7]
                    t[:, :, 11] = 255
                    local.append((name, t))
                count = sum(len(t) for _, t in local)
                if not count:
                    raise ValueError('No supported surface')
                cost = 3*(used+count)+3*(meshes+len(local)+(used+count)//512+1)
                if cost > room or used+count > chart_room:
                    raise ValueError('Exceeds the %.0f%% native world index ceiling' % (INDEX_FRACTION*100))
                row = dict(p, folder=str(path), lod=lod, triangles=count, category=kind,
                           recovery='Exact source VG author LOD, skin, UV and placement')
                col, method = recovery.collision(row, raw)
                row.update(collision_triangles=len(col), collision_recovery=method)
                selected.append(row); pieces.extend(local); physics.append(col)
                used += count; meshes += len(local)
            except (KeyError, ValueError, OSError, struct.error) as error:
                skipped.append(dict(index=p['index'], model=p['model'], reason=str(error)))
    if not selected:
        raise ValueError('No source geometry recovered')
    names = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(PROJECT/'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names.index(n), 'i4') for n, t in pieces]),
             names=names, collision=np.concatenate(physics))
    report = dict(version='0.6.0', added_props=len(selected), added_triangles=used,
                  placements=selected, skipped=skipped, baseline_padded_indices=current,
                  categories=dict(collections.Counter(p['category'] for p in selected)),
                  maximum_world_index_fraction=INDEX_FRACTION,
                  policy='User-reported window walls, glass columns, screen towers, track set, rocks; under the ceiling')
    structure.write(PROJECT/'plan.json', report)
    print(json.dumps({k: report[k] for k in ('added_props', 'added_triangles', 'categories')}),
          'skipped', len(skipped), flush=True)


def materials():
    configure()
    structure.materials()


def append():
    configure()
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = OUT, PROJECT, OUT/'mp_party_crasher.bsp', BACKUP
    direction = -np.asarray(json.loads((OUT/'environment.json').read_text())['native_sun_normal'])
    # The previous incremental bake owns the caster ledger for the 0.4.0 scene.
    from append_free_charts import append as append_free
    append_free(OUT/BAKE_BASE, INDEX_FRACTION,
                    str(structure.WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_party_crasher', 'party_crasher_world')


def stage():
    """Copy the accepted 0.4.0 mod and swap only the rebuilt map/STBSP/world pack."""
    import shutil
    from map_pack_lifetime import audit as pack_audit
    from new_arena_ports import ROOT, WORK
    from package_player_mods import digest
    accepted = ROOT/'northstar/ArenaPartyCrasher'
    # A local 0.6.0 may be replaced: its first culling pass was rejected (see port-0.6.0 README).
    version = json.loads((accepted/'mod.json').read_text())['Version']
    if version not in ('0.5.1', '0.6.0'):
        raise ValueError('Unexpected accepted baseline version')
    if version == '0.5.1' and digest(OUT/'before-layer-blend/mp_party_crasher.bsp') != digest(accepted/'mod/maps/mp_party_crasher.bsp'):
        raise ValueError('Round baseline is not the accepted 0.5.1 payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run the binary audit first')
    candidate = WORK/'reported-candidates'/'ArenaPartyCrasher'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for relative, source in (('mod/maps/mp_party_crasher.bsp', OUT/'mp_party_crasher.bsp'),
                             ('mod/maps/mp_party_crasher.stbsp', OUT/'mp_party_crasher.stbsp'),
                             ('paks/party_crasher_world.rpak', OUT/'materials/build/party_crasher_world.rpak')):
        shutil.copy2(source, candidate/relative)
        if digest(source) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = '0.6.0'
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    pack_audit(candidate/'paks', 'mp_party_crasher')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'materials', 'append', 'stage'])
    dict(plan=plan, materials=materials, append=append, stage=stage)[p.parse_args().action]()
