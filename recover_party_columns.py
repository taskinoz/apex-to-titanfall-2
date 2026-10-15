"""Party Crasher 0.6.1: glass columns and cafe/planter props from the third user report.

The four `citymodern_column_128x384_concrete_glass_a` columns (q30/q31) are
over-tessellated (6,832 triangles, 5,856 in the window clamps); they are drawn
from the source LOD0 simplified with meshoptimizer at a 0.25-unit error limit,
keeping source UVs/normals. Collision is the full source collider. Then the
cafe booth (q32) and planter (q33) props nearest the reports, under the 98%
ceiling, after upgrade_placement_lods.py has freed budget from far props.
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
PROJECT = OUT/'column-recovery'
BACKUP = OUT/'before-0.6.1'
BAKE_BASE = 'lod-upgrade'
SIMPLIFY = {'citymodern_column_128x384_concrete_glass_a': .25}
INDEX_CAPACITY = 3145728
INDEX_FRACTION = .98
# Priority groups with the authored LOD used for each model. Collision always
# comes from the source PHY/BVH, independent of the visual LOD.
GROUPS = (
    # q33: the flower planter's collision is baked into the Apex world collision,
    # so while it is omitted it stands as an invisible object.
    ('planter-pillar', {'party_crashers_pillar_03': 0}),
    ('glass-column', {'citymodern_column_128x384_concrete_glass_a': 0}),
    ('cafe', {'olympus_table_01': 0, 'olympus_stool_01': 1, 'desertlands_napkin_holder_01': 1}),
    ('planter', {'bush_green_forest_01_red': 2}),
)
REPORTS = np.asarray([s['origin'] for f in ('party-crasher-user-report-3.json',)
                      for s in json.loads((Path(__file__).resolve().parent/'test-harness/routes'/f).read_text())['shots']
                      if s['name'] != 'warmup'])
# Groups restored only at the reported positions (budget goes to reported props first).
NEAR_ONLY = {'planter-pillar': 300}
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')


def simplified(t, error):
    """Index-simplify one placed section, keeping exact source vertices."""
    from simplify_preview_draw import simplifier, simplify
    a = t.reshape(-1, 12); attrs = np.column_stack((a[:, 3:6], a[:, 6:8], a[:, 8:11]/255)).astype('<f4')
    _, first, inv = np.unique(np.column_stack((a[:, :3], attrs)), axis=0, return_index=True, return_inverse=True)
    out, _ = simplify(simplifier(), inv.reshape(-1, 3), a[first, :3], attrs[first], .05, error, options=1)
    return a[first][out.reshape(-1)].reshape(-1, 3, 12)


def cache_simplified():
    """Simplify each SIMPLIFY model section once in local space (run alone, before plan)."""
    PROJECT.mkdir(parents=True, exist_ok=True); index = asset_index('party-crasher'); out = {}
    for stem, error in SIMPLIFY.items():
        sections, slots, skins = load(index[stem], 0, True)
        for s, slot in zip(sections, slots):
            if len(s):
                out[f'{skins[0][slot]}_{slot}'] = simplified(np.asarray(s, 'f4').reshape(-1, 3, 12).copy(), error)
    np.savez(PROJECT/'simplified.npz', **out)
    print('Cached', {k: len(v) for k, v in out.items()}, flush=True)


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
            if kind in NEAR_ONLY and float(np.min(np.linalg.norm(REPORTS-np.asarray(p['origin']), axis=1))) > NEAR_ONLY[kind]:
                skipped.append(dict(index=p['index'], model=p['model'], reason='Not at a reported position')); continue
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
                    if Path(p['model']).stem.lower() in SIMPLIFY:
                        # Simplified in local space by cache_simplified() in a clean process
                        # (meshoptimizer faults when loaded beside SciPy's runtime).
                        cached = np.load(PROJECT/'simplified.npz')[f'{name}_{slot}']
                        t = cached.copy(); t[:, :, :3] = cached[:, :, :3]@matrix.T*p['scale']+p['origin']
                        t[:, :, 3:6] = cached[:, :, 3:6]@matrix.T; t[:, :, 7] = 1-cached[:, :, 7]; t[:, :, 11] = 255
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
    report = dict(version='0.6.1', added_props=len(selected), added_triangles=used,
                  placements=selected, skipped=skipped, baseline_padded_indices=current,
                  categories=dict(collections.Counter(p['category'] for p in selected)),
                  maximum_world_index_fraction=INDEX_FRACTION,
                  policy='Reported flower planter, simplified glass columns, then cafe and planter props nearest report 3; under the ceiling')
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
    if version not in ('0.6.0', '0.6.1'):
        raise ValueError('Unexpected accepted baseline version')
    if version == '0.6.0' and digest(OUT/'before-collision-match/mp_party_crasher.bsp') != digest(accepted/'mod/maps/mp_party_crasher.bsp'):
        raise ValueError('Round baseline is not the accepted 0.6.0 payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run the binary audit first')
    candidate = WORK/'column-candidates'/'ArenaPartyCrasher'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for relative, source in (('mod/maps/mp_party_crasher.bsp', OUT/'mp_party_crasher.bsp'),
                             ('mod/maps/mp_party_crasher.stbsp', OUT/'mp_party_crasher.stbsp'),
                             ('paks/party_crasher_world.rpak', OUT/'materials/build/party_crasher_world.rpak')):
        shutil.copy2(source, candidate/relative)
        if digest(source) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = '0.6.1'
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    pack_audit(candidate/'paks', 'mp_party_crasher')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['cache', 'plan', 'materials', 'append', 'stage'])
    dict(cache=cache_simplified, plan=plan, materials=materials, append=append, stage=stage)[p.parse_args().action]()
