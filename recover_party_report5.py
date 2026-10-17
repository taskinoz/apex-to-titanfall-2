"""Party Crasher 0.6.3: the fifth user report (q41-q50).

Located with survey_party_report5.py and probe_view.py (screenshot view rays):

* q41 invisible object: the omitted bar counter around the pillar
  (party_crashers_pillar_cover_02) and the glasses/bottles on it; their source
  collision is baked into the world.
* q42/q43 invisible geometry: omitted concrete chunks, rebar pieces and rock
  clusters with world-baked collision beside the pool.
* q44-q46 missing tables: the eight upper-cafe olympus_table_01 placements.
* q47 unnecessary details: the cafe table clutter added in 0.6.2 (bowl, beer
  glass, napkin holders) is removed with its appended collider.
* q48 unnecessary details: the out-of-bounds rooftop AC unit, pipes and grime
  decals are no longer drawn (their collision is unreachable and unchanged).
* q49 glowing number: floor_lightstrip_plastic_vert_alpha (the "234" room
  number) has a 20x HDR emissive tint that Apex gates by vertex alpha;
  Titanfall applies it everywhere, so it is scaled to STRIP_EMISSION.
* q50 black water: waterpool_03 uses Apex's refractive water shader whose
  albedo is only a dark base; Titanfall's opaque world shader draws it as a
  black sheet. It uses the world-alpha preset (as the fountain foam does) with
  a water tint and constant opacity so the lit pool floor shows through.

Budget: heavy single-instance meshes (the market sign, glass columns,
windowed walls) use meshoptimizer-simplified source LOD0 at 0.5% relative
error; other reported additions use cheaper author LODs.

Steps: cache (clean process per model), plan, materials, apply, textures, stage.
"""
import argparse
import collections
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import recover_party_structure as structure
from audit_world_draw_budget import audit
from new_arena_ports import ROOT, folder
from prepare_new_arena_scene import asset_index
from read_vg_static import load
from stage_prop_geometry import rotation
import recover_composite_details as recovery

OUT = folder('party-crasher')
PROJECT = OUT/'report5-recovery'
BACKUP = OUT/'before-0.6.3'
BAKE_BASE = 'report4-recovery'  # bake casters of the last append (0.6.2)
VERSION, BASELINE = '0.6.3', '0.6.2'
ERROR = .005
MENU_Z = -1000
INDEX_CAPACITY = 3145728
INDEX_FRACTION = .98
PLAN_FRACTION = .977
# Placed LOD0 meshes replaced by their simplified source mesh (visual only).
# (The glass columns were rebuilt in 0.6.0, so their drawn faces no longer match the source.)
SIMPLIFY = ('ac_genki_market_sign_big_01', 'citymodern_wall_128x384_window_dtown_a',
            'citymodern_wall_128x256_window_dtown_a', 'citymodern_column_128x512_concrete_b')
# Reported omitted placements: index -> (author LOD or 'simplified', report).
REPORTED = {
    13451: ('simplified', 'q41 bar counter'), 13683: (1, 'q41 glass'), 13684: (1, 'q41 glass'), 13680: (1, 'q41 glass'),
    13735: (1, 'q41 glass'), 13732: (1, 'q41 glass'), 6732: (0, 'q41 bottle'), 6733: (0, 'q41 bottle'),
    5317: (1, 'q42 concrete chunk'), 5318: (1, 'q42 concrete chunk'), 8811: ('simplified', 'q42 rebar'),
    9736: (1, 'q42 rock cluster'),
    12830: (1, 'q43 broken concrete'), 1768: (1, 'q43 rebar'), 1776: (1, 'q43 rebar'), 5641: (1, 'q43 concrete chunk'),
    5631: (1, 'q43 concrete chunk'), 9960: (1, 'q43 rock cluster'),
    8848: (0, 'q44 table'), 8835: (0, 'q45 table'), 8829: (0, 'q46 table'), 8852: (0, 'q46 table'),
    8850: (0, 'upper cafe table'), 8841: (0, 'upper cafe table'), 8831: (0, 'upper cafe table'), 8847: (0, 'upper cafe table'),
}
SIMPLIFIED_ADDITIONS = ('party_crashers_pillar_cover_02', 'concrete_piece_07_rebar')
# q47: cafe table clutter added in 0.6.2 (removed with its appended collider).
CLUTTER = ('dirty_bowl_single', 'dive_bar_beer_glass_01_a', 'desertlands_napkin_holder_01')
CAFE_CENTRE, CAFE_RADIUS = np.asarray([2852., -54., 972.]), 1200
# q48: the out-of-bounds rooftop (visual only).
ROOF_BOX = (np.asarray([-5150., 2040., 3050.]), np.asarray([-4440., 2420., 3115.]))
ROOF_EXTRA = {8002: 'rooftop AC unit'}  # grime decals are drawn as offset decals; left as they are
NON_SOLID = ('flowers_01_cards', 'leaf', 'leaves', 'foliage', 'glass')
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')
ON_COLLISION = .2   # share of a prop surface already on native collision: no collider appended
STRIP = 'floor_lightstrip_plastic_vert_alpha'
STRIP_EMISSION = 3.0
WATER = 'waterpool_03'
WATER_OPACITY = 150         # of 255
WATER_TINT = (70, 112, 118)  # mean of waterpool_04 is (51, 70, 70); brighter to read through the alpha
TEXTURES = OUT/'materials/assets/texture/party_crasher'
MATERIALS = OUT/'materials/assets/material/world/party_crasher'
PY = sys.executable


def configure():
    structure.PROJECT, structure.BACKUP = PROJECT, BACKUP


def place(section, p):
    matrix = np.asarray(rotation(p['angles'])); t = section.copy()
    t[:, :, :3] = section[:, :, :3]@matrix.T*p['scale']+p['origin']; t[:, :, 3:6] = section[:, :, 3:6]@matrix.T
    t[:, :, 7] = 1-section[:, :, 7]; t[:, :, 11] = 255
    return t


def cache_one(stem, out):
    from recover_party_columns import simplified
    sections, slots, skins = load(asset_index('party-crasher')[stem], 0, True); res = {}
    for k, s in enumerate(sections):
        if len(s):
            res[f'{stem}/{k}'] = simplified(np.asarray(s, 'f4').reshape(-1, 3, 12).copy(), ERROR)
    np.savez(out, **res)


def cache():
    """Simplify each model in its own process (meshoptimizer can fault on large inputs)."""
    PROJECT.mkdir(parents=True, exist_ok=True); merged = {}
    for stem in SIMPLIFY+SIMPLIFIED_ADDITIONS:
        part = PROJECT/f'simplified-{stem}.npz'
        for attempt in range(3):  # the native simplifier faults intermittently
            if not part.exists():
                subprocess.run([PY, __file__, 'cache-one', stem, str(part)])
        if not part.exists():
            raise RuntimeError('Simplification failed: '+stem)
        with np.load(part) as z:
            merged.update({k: z[k] for k in z.files})
    np.savez(PROJECT/'simplified.npz', **merged)
    print('Cached', {k: len(v) for k, v in merged.items()}, flush=True)


def plan():
    from package_player_mods import digest
    from analyse_visibility import render_triangles  # noqa: F401  (loads before SciPy users)
    from audit_collision_visibility import native_collision, sample
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from scipy.spatial import cKDTree
    configure()
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; use the immutable snapshot to rebuild')
    accepted = ROOT/'northstar/ArenaPartyCrasher/mod/maps/mp_party_crasher.bsp'
    if digest(OUT/'mp_party_crasher.bsp') != digest(accepted):
        raise ValueError('Working map is not the accepted '+BASELINE+' payload')
    scene = json.loads((OUT/'scene.json').read_text()); index = asset_index('party-crasher')
    mapping = json.loads((OUT/'materials/mapping.json').read_text())['materials']
    simple = np.load(PROJECT/'simplified.npz'); cache = {}
    def geometry(p, lod):
        f = p['folder'] if 'folder' in p else str(index[Path(p['model']).stem.lower()])
        if (f, lod) not in cache:
            cache[f, lod] = load(Path(f), lod, True)
        sections, slots, skins = cache[f, lod]; skin = skins[min(p['skin'], len(skins)-1)]
        return [(skin[slot], np.asarray(s, 'f4').reshape(-1, 3, 12), k) for k, (s, slot) in enumerate(zip(sections, slots))
                if len(s) and not any(w in skin[slot].lower() for w in SKIP_SECTIONS)], cache[f, lod][0]
    pieces, retire, physics, selected, skipped, removed = [], [], [], [], [], []
    freed = 0
    # 1. Simplified replacements and removals (retired from draw and shadow streams).
    for p in scene['placements']:
        stem = Path(p['model']).stem.lower(); o = np.asarray(p['origin']); lod = p.get('lod', 0)
        roof = bool(np.all(o >= ROOF_BOX[0]) and np.all(o <= ROOF_BOX[1]) and stem.startswith('pipe_modular')) or p['index'] in ROOF_EXTRA
        clutter = stem in CLUTTER and np.linalg.norm(o-CAFE_CENTRE) < CAFE_RADIUS
        if stem in SIMPLIFY and lod == 0 and o[2] > MENU_Z:
            old, _ = geometry(p, 0); new = [(name, place(simple[f'{stem}/{k}'], p)) for name, s, k in old]
            oldn = sum(len(s) for _, s, _ in old); newn = sum(len(t) for _, t in new)
            retire.append(np.concatenate([place(s, p)[:, :, :3] for _, s, _ in old])); pieces.extend(new); freed += oldn-newn
            selected.append(dict(p, triangles=newn, retired_triangles=oldn, replacement=True, category='simplified',
                                 recovery='Source LOD0 simplified by meshoptimizer at %.1f%% relative error' % (ERROR*100),
                                 collision_triangles=0, collision_recovery='Existing collider retained; visual only'))
        elif roof or clutter:
            old, raw = geometry(p, lod)
            retire.append(np.concatenate([place(s, p)[:, :, :3] for _, s, _ in old])); n = sum(len(s) for _, s, _ in old); freed += n
            row = dict(p, retired_triangles=n, category='q48 rooftop' if roof else 'q47 table clutter')
            if clutter:
                row['collider'] = recovery.collision(dict(p, folder=str(index[stem])), [np.asarray(s, 'f4') for s in raw])[0].tolist()
            removed.append(row)
    current = audit(OUT/'mp_party_crasher.bsp')['native_padded_indices']
    room = INDEX_CAPACITY*PLAN_FRACTION-current+3*sum(len(r) for r in retire)
    from append_free_charts import free_tiles
    chart_room = len(free_tiles(OUT/'mp_party_crasher.bsp'))+sum(len(r) for r in retire)
    used = sum(len(t) for _, t in pieces); meshes = len(pieces)
    # 2. Reported omitted props; collision is appended only where none exists yet.
    coll = cKDTree(sample(native_collision(OUT/'mp_party_crasher.bsp'), 6.))
    omitted = {p['index']: p for p in scene['omitted']}
    missing = [i for i in REPORTED if i not in omitted]
    if missing:
        raise ValueError(f'Reported placements not omitted: {missing}')
    for i, (lod, kind) in REPORTED.items():
        p = omitted[i]; stem = Path(p['model']).stem.lower()
        try:
            path = index[stem]; levels = struct.unpack_from('<18Q', (path/(path.name+'.vg')).read_bytes(), 16)[13]
            if lod == 'simplified':
                full, raw = geometry(dict(p, folder=str(path)), 0)
                local = [(name, place(simple[f'{stem}/{k}'], p)) for name, s, k in full]
                how = 'Source LOD0 simplified by meshoptimizer at %.1f%% relative error' % (ERROR*100); lod = 0
            else:
                lod = min(lod, levels-1); local, raw = geometry(dict(p, folder=str(path)), lod)
                local = [(name, place(s, p)) for name, s, _ in local]; how = 'Exact source VG author LOD, skin, UV and placement'
            for name, _ in local:
                if name not in mapping and not (OUT/'legion/exported_files/materials'/name/(name+'_albedoTexture.dds')).is_file():
                    raise ValueError('Source texture unavailable: '+name)
            count = sum(len(t) for _, t in local)
            cost = 3*(used+count)+3*(meshes+len(local)+(used+count)//512+1)
            if cost > room or used+count > chart_room:
                raise ValueError('Exceeds the %.1f%% planning ceiling' % (PLAN_FRACTION*100))
            surface = np.concatenate([t[:, :, :3] for name, t in local if not any(w in name.lower() for w in NON_SOLID)] or
                                     [np.concatenate([t[:, :, :3] for _, t in local])]).astype('f8')
            on = float((coll.query(sample(surface, 4.))[0] < 5).mean())
            row = dict(p, folder=str(path), lod=lod, triangles=count, category=kind, recovery=how, surface_on_collision=round(on, 3))
            if on >= ON_COLLISION:
                col, method = np.empty((0, 3, 3), 'f4'), 'Existing world-baked source collision retained'
            else:
                col, method = recovery.collision(row, [np.asarray(s, 'f4') for s in raw])
            row.update(collision_triangles=len(col), collision_recovery=method)
            selected.append(row); pieces.extend(local); physics.append(np.asarray(col, 'f4')); used += count; meshes += len(local)
        except (KeyError, ValueError, OSError, struct.error) as error:
            skipped.append(dict(index=i, model=p['model'], reason=str(error), category=kind))
    if skipped:
        raise ValueError('Reported placements skipped: '+json.dumps(skipped))
    names = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(PROJECT/'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names.index(n), 'i4') for n, t in pieces]),
             names=names, collision=np.concatenate(physics) if physics else np.empty((0, 3, 3), 'f4'))
    np.save(PROJECT/'retire-points.npy', np.concatenate(retire))
    added = [p for p in selected if not p.get('replacement')]
    report = dict(version=VERSION, added_props=len(selected), added_triangles=used, freed_triangles=freed,
                  placements=selected, removed=removed, skipped=skipped, baseline_padded_indices=current,
                  categories=dict(collections.Counter(p['category'] for p in selected)),
                  removed_categories=dict(collections.Counter(p['category'] for p in removed)),
                  restored=len(added), simplified=len(selected)-len(added), maximum_world_index_fraction=INDEX_FRACTION)
    structure.write(PROJECT/'plan.json', report)
    print(json.dumps({k: report[k] for k in ('restored', 'simplified', 'added_triangles', 'freed_triangles',
                                             'categories', 'removed_categories')}), flush=True)
    for p in added:
        print(f"  {p['index']:6d} {Path(p['model']).stem:40s} lod{p['lod']} {p['triangles']:5d} tris  on-collision "
              f"{p['surface_on_collision']:.2f}  {p['collision_recovery']}")


def materials():
    configure()
    structure.materials()


def write_bsp(bsp, buf):
    import os
    from compact_preview_bsp import compact
    temp = bsp.with_suffix('.report5.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)


def disable_clutter_colliders():
    """Drop the grid membership of 0.6.2-appended headers that lie inside removed clutter colliders."""
    from repair_preview_index_padding import read_lumps
    from match_collision_to_render import replace_collision
    from build_center_detail import active
    bsp = OUT/'mp_party_crasher.bsp'
    plan_ = json.loads((PROJECT/'plan.json').read_text())
    boxes = [np.asarray(r['collider']).reshape(-1, 3) for r in plan_['removed'] if r.get('collider')]
    boxes = [(b.min(0)-2, b.max(0)+2) for b in boxes if len(b)]
    first = len(read_lumps(OUT/'before-0.6.2/mp_party_crasher.bsp', (0x45,))[0x45])//44
    l = read_lumps(bsp, tuple(range(128))); buf = {k: bytearray(v) for k, v in l.items()}
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3); words = np.frombuffer(l[0x42], '<u4'); act = active(l); drop = []
    for i, h in enumerate(struct.iter_unpack('<6h4i4f', l[0x45])):
        if i < first or (0x40, i) not in act:
            continue
        w = words[h[7]:h[7]+h[4]]; ix = w & 1023
        c = pos[h[6]+np.stack((ix, ix+(w >> 10 & 127), ix+(w >> 17 & 127)), 1)].mean(1)
        inside = np.zeros(len(c), bool)
        for lo, hi in boxes:
            inside |= np.all((c >= lo) & (c <= hi), 1)
        if inside.mean() >= .9:
            drop.append(i)
    replace_collision(l, buf, set(), set(drop), np.empty((0, 3, 3), 'f4'))
    write_bsp(bsp, buf)
    return drop


def water_flags():
    """waterpool_03 surfaces join the alpha pass: texdata and mesh alpha flags (0x10)."""
    from repair_preview_index_padding import read_lumps
    bsp = OUT/'mp_party_crasher.bsp'; l = read_lumps(bsp, (2, 0x2b, 0x2c, 0x50, 0x52)); buf = {k: bytearray(v) for k, v in l.items()}
    target = 'world\\party_crasher\\'+WATER; texdata = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        if l[0x2b][off:l[0x2b].index(0, off)].decode() == target:
            texdata.append(at//36); struct.pack_into('<I', buf[2], at+32, struct.unpack_from('<I', l[2], at+32)[0] | 0x10)
    if len(texdata) != 1:
        raise ValueError(f'Expected one {WATER} texdata, found {len(texdata)}')
    sorts = {i for i, s in enumerate(struct.iter_unpack('<3hHI', l[0x52])) if s[0] == texdata[0]}; meshes = 0
    for at in range(0, len(l[0x50]), 28):
        r = struct.unpack_from('<I3H6b2h2BHI', l[0x50], at)
        if r[-2] in sorts:
            struct.pack_into('<I', buf[0x50], at+24, r[-1] | 0x10); meshes += 1
    write_bsp(bsp, {k: buf[k] for k in (2, 0x50)})
    return dict(texdata=texdata[0], meshes=meshes)


def apply():
    from upgrade_placement_lods import retire
    configure()
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = OUT, PROJECT, OUT/'mp_party_crasher.bsp', BACKUP
    retire('party-crasher', PROJECT)
    direction = -np.asarray(json.loads((OUT/'environment.json').read_text())['native_sun_normal'])
    from append_free_charts import append as append_free
    append_free(OUT/BAKE_BASE, INDEX_FRACTION, str(structure.WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    dropped = disable_clutter_colliders(); flags = water_flags()
    scene = json.loads((OUT/'scene.json').read_text())
    gone = {r['index'] for r in json.loads((PROJECT/'plan.json').read_text())['removed']}
    scene['omitted'] += [dict(p, reason='Removed in 0.6.3 (user report: unnecessary detail)') for p in scene['placements'] if p['index'] in gone]
    scene['placements'] = list({p['index']: p for p in scene['placements'] if p['index'] not in gone}.values())
    scene['props'] = len(scene['placements'])
    structure.write(OUT/'scene.json', scene)
    result = json.loads((PROJECT/'result.json').read_text())
    result.update(clutter_headers_disabled=dropped, water_alpha=flags); structure.write(PROJECT/'result.json', result)
    print('Disabled', len(dropped), 'clutter collision headers; water alpha', flags, flush=True)


# --- Materials --------------------------------------------------------------

def bc4(path, value, size):
    """A constant single-channel BC4 texture with a full mip chain."""
    import io
    from PIL import Image
    tmp = PROJECT/'opacity.png'; Image.new('L', (size, size), value).save(tmp)
    texconv = ROOT/'tools/directxtex/texconv.exe'
    subprocess.run([str(texconv), '-nologo', '-y', '-f', 'BC4_UNORM', '-o', str(PROJECT), str(tmp)], check=True, capture_output=True)
    shutil.move(str(PROJECT/'opacity.dds'), str(path))


def textures():
    from recover_arena_atmosphere import NativeMaterials
    from PIL import Image
    keep = BACKUP/'material-originals'; keep.mkdir(parents=True, exist_ok=True)
    files = [MATERIALS/f'{STRIP}_wld.uber', MATERIALS/f'{STRIP}_colpass_wld.uber', MATERIALS/f'{WATER}_wld.json',
             MATERIALS/f'{WATER}_wld.uber', TEXTURES/f'{WATER}_albedo.dds']
    for p in files:
        if (keep/p.name).exists():
            shutil.copy2(keep/p.name, p)  # rebuilds start from the 0.6.2 asset
        else:
            shutil.copy2(p, keep/p.name)
    # q49: scale the HDR emission tint (constant buffer offset 160) of the light strip.
    for p in files[:2]:
        b = bytearray(p.read_bytes()); old = struct.unpack_from('<3f', b, 160)
        if old != (20.0, 20.0, 20.0):
            raise ValueError(f'Unexpected light-strip emission {old}')
        struct.pack_into('<3f', b, 160, *(STRIP_EMISSION,)*3); p.write_bytes(b)
    # q50: waterpool_03 on the tested world-alpha preset of the fountain foam.
    foam = json.loads((MATERIALS/'water_foamy_fountain_01_wld.json').read_text())
    water = json.loads((MATERIALS/f'{WATER}_wld.json').read_text())
    spec = dict(foam); spec['name'] = water['name']; spec['surfaceProp'] = water['surfaceProp']
    opacity = 'texture/party_crasher/'+WATER+'_opacityMultiply.rpak'
    spec['$textures'] = {'0': water['$textures']['0'], '1': water['$textures']['1'],
                         '2': 'texture/party_crasher/water_foamy_fountain_01_gloss.rpak',
                         '3': 'texture/party_crasher/water_foamy_fountain_01_spec.rpak', '13': opacity}
    (MATERIALS/f'{WATER}_wld.json').write_text(json.dumps(spec, indent=2))
    shutil.copy2(MATERIALS/'water_foamy_fountain_01_wld.uber', MATERIALS/f'{WATER}_wld.uber')
    bc4(TEXTURES/(WATER+'_opacityMultiply.dds'), WATER_OPACITY, 256)
    albedo = TEXTURES/f'{WATER}_albedo.dds'; png = PROJECT/f'{WATER}_albedo.png'
    texconv = ROOT/'tools/directxtex/texconv.exe'
    subprocess.run([str(texconv), '-nologo', '-y', '-ft', 'png', '-f', 'R8G8B8A8_UNORM_SRGB', '-o', str(PROJECT), str(albedo)],
                   check=True, capture_output=True)
    shutil.move(str(PROJECT/f'{WATER}_albedo.png'), str(png))
    a = np.asarray(Image.open(png).convert('RGB')).astype('f4'); lum = a.mean(2, keepdims=True)
    tinted = np.clip(lum/max(float(lum.mean()), 1)*np.asarray(WATER_TINT, 'f4'), 0, 255).astype('u1')
    Image.fromarray(tinted).save(png)
    raw = albedo.read_bytes(); fmt = struct.unpack_from('<I', raw, 128)[0] if raw[84:88] == b'DX10' else None
    names = {72: 'BC1_UNORM_SRGB', 71: 'BC1_UNORM', 78: 'BC3_UNORM_SRGB', 98: 'BC7_UNORM', 99: 'BC7_UNORM_SRGB'}
    mips = struct.unpack_from('<I', raw, 28)[0]
    subprocess.run([str(texconv), '-nologo', '-y', '-srgb', '-f', names[fmt], '-m', str(mips), '-dx10', '-o', str(PROJECT), str(png)],
                   check=True, capture_output=True)
    shutil.move(str(PROJECT/f'{WATER}_albedo.dds'), str(albedo))
    manifest = json.loads((OUT/'materials/build.json').read_text())
    builder = NativeMaterials(OUT/'materials', 'party_crasher', manifest)
    builder.files[opacity] = dict(_type='txtr', _path=opacity, **{'$disableStreaming': True})
    mapping_path = OUT/'materials/mapping.json'; mapping = json.loads(mapping_path.read_text())
    rec = mapping['materials'][WATER]; rec.update(textures=spec['$textures'], transparent=True,
                                                   native_source_channels='World-alpha water: source normal, tint and constant opacity')
    mapping['materials'][STRIP]['native_source_channels'] += f'; emission x{STRIP_EMISSION}/20 (source vertex-alpha gate)'
    mapping_path.write_text(json.dumps(mapping, indent=2))
    builder.finish(manifest)
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_party_crasher', 'party_crasher_world')
    structure.write(PROJECT/'textures.json', dict(strip_emission=STRIP_EMISSION, water_opacity=WATER_OPACITY/255,
                                                  water_tint=WATER_TINT, originals=str(keep)))
    print('Light strip emission', STRIP_EMISSION, '; water opacity', round(WATER_OPACITY/255, 3), flush=True)


def stage():
    """Copy the accepted 0.6.2 mod and swap only the rebuilt map/STBSP/world pack."""
    from map_pack_lifetime import audit as pack_audit
    from new_arena_ports import WORK
    from package_player_mods import digest
    accepted = ROOT/'northstar/ArenaPartyCrasher'
    if json.loads((accepted/'mod.json').read_text())['Version'] != BASELINE:
        raise ValueError('Unexpected accepted baseline version')
    if digest(BACKUP/'mp_party_crasher.bsp') != digest(accepted/'mod/maps/mp_party_crasher.bsp'):
        raise ValueError('Round baseline is not the accepted payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run the binary audit first')
    candidate = WORK/'report5-candidates'/'ArenaPartyCrasher'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for relative, source in (('mod/maps/mp_party_crasher.bsp', OUT/'mp_party_crasher.bsp'),
                             ('mod/maps/mp_party_crasher.stbsp', OUT/'mp_party_crasher.stbsp'),
                             ('paks/party_crasher_world.rpak', OUT/'materials/build/party_crasher_world.rpak')):
        shutil.copy2(source, candidate/relative)
        if digest(source) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = VERSION
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    pack_audit(candidate/'paks', 'mp_party_crasher')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    if sys.argv[1:2] == ['cache-one']:
        cache_one(sys.argv[2], sys.argv[3]); sys.exit()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['cache', 'plan', 'materials', 'apply', 'textures', 'stage'])
    dict(cache=cache, plan=plan, materials=materials, apply=apply, textures=textures, stage=stage)[p.parse_args().action]()
