"""Party Crasher 0.6.2: the fourth user report (q34-q40).

Invisible collision at q34-q37 is world-baked collision of omitted source
props (cafe table set, two search lights, concrete rubble); q39 is the second
flower planter. They are drawn at source LOD0 with their source collider.
Budget comes from simplifying over-tessellated single-LOD props in the arena
(hanging wire bundles, ship consoles, pillar signage) with meshoptimizer at a
0.5% relative error: their old triangles are retired from the draw/shadow
streams and the simplified source mesh (same UVs/normals/placement) appended;
collision is unchanged. Menu-stage copies (z < -1000) are left untouched.

q38: the source foam overlay `water_foamy_fountain_01` is animated and faint
in Apex; Titanfall's world shader draws it static, so its opacity map is
scaled to FOAM_OPACITY. q40: the R5Reloaded placeholder panel in
`oasis_signs_ad_atlas_01` is repainted with an original north-star emblem.

Steps: cache (clean process: meshoptimizer faults beside SciPy), plan,
materials, apply, textures, stage.
"""
import argparse
import collections
import json
import shutil
import struct
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
PROJECT = OUT/'report4-recovery'
BACKUP = OUT/'before-0.6.2'
BAKE_BASE = 'column-recovery'
SIMPLIFY = {'catwalk_hanging_wires_01': .005, 'ship_console_control_med_v1_off': .005,
            'party_crashers_pillar_signage': .005}
MENU_Z = -1000
INDEX_CAPACITY = 3145728
INDEX_FRACTION = .98
PLAN_FRACTION = .977  # margin for per-mesh index padding of new geometry
# Reported omitted props (exact source indices) at source LOD0.
REPORTED = {11244: 'q39 flower planter', 13651: 'q37 search light', 13652: 'q35 search light',
            8851: 'q34 cafe table', 6678: 'q34 napkin holder', 6319: 'q34 stool', 6625: 'q34 bowl',
            13690: 'q34 glass', 898: 'q36 rubble', 1777: 'q36 rubble', 12866: 'q36 rubble', 9255: 'q39 speaker'}
# Placements whose source collider (a small IRPS box) misses the drawn structure:
# they collide with their drawn triangles instead, foliage cards excluded.
RENDER_COLLISION = {11244}
NON_SOLID = ('flowers_01_cards', 'leaf', 'leaves', 'foliage', 'glass')
# Then the rest of the cafe furniture nearest the q34 booth, until the ceiling.
CAFE = {'olympus_table_01': 0, 'olympus_stool_01': 1, 'desertlands_napkin_holder_01': 1}
CAFE_CENTRE = np.asarray([2852., -54., 972.])
CAFE_RADIUS = 1200
SKIP_SECTIONS = ('godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')
FOAM = 'water_foamy_fountain_01'
FOAM_OPACITY = .3
ATLAS = 'oasis_signs_ad_atlas_01'
TEXTURES = OUT/'materials/assets/texture/party_crasher'


def configure():
    structure.PROJECT, structure.BACKUP = PROJECT, BACKUP


def place(section, p):
    matrix = np.asarray(rotation(p['angles'])); t = section.copy()
    t[:, :, :3] = section[:, :, :3]@matrix.T*p['scale']+p['origin']; t[:, :, 3:6] = section[:, :, 3:6]@matrix.T
    t[:, :, 7] = 1-section[:, :, 7]; t[:, :, 11] = 255
    return t


def cache():
    """Simplify each SIMPLIFY model section once in local space (run alone, before plan)."""
    from recover_party_columns import simplified
    PROJECT.mkdir(parents=True, exist_ok=True); index = asset_index('party-crasher'); out = {}
    for stem, error in SIMPLIFY.items():
        sections, slots, skins = load(index[stem], 0, True)
        for k, (s, slot) in enumerate(zip(sections, slots)):
            if len(s):
                out[f'{stem}/{k}'] = simplified(np.asarray(s, 'f4').reshape(-1, 3, 12).copy(), error)
    np.savez(PROJECT/'simplified.npz', **out)
    print('Cached', {k: len(v) for k, v in out.items()}, flush=True)


def plan():
    configure()
    if (PROJECT/'result.json').exists():
        raise ValueError('Already applied; use the immutable snapshot to rebuild')
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
    pieces, retire, physics, selected, skipped = [], [], [], [], []
    freed = 0
    # 1. Simplified replacements (visual only; existing collider retained).
    for p in scene['placements']:
        stem = Path(p['model']).stem.lower()
        if stem not in SIMPLIFY or p.get('lod', 0) != 0 or p['origin'][2] < MENU_Z:
            continue
        old, _ = geometry(p, 0); new = []
        for name, s, k in old:
            new.append((name, place(simple[f'{stem}/{k}'], p)))
        oldn = sum(len(s) for _, s, _ in old); newn = sum(len(t) for _, t in new)
        retire.append(np.concatenate([place(s, p)[:, :, :3] for _, s, _ in old])); pieces.extend(new); freed += oldn-newn
        selected.append(dict(p, triangles=newn, retired_triangles=oldn, replacement=True, category='simplified',
                             recovery='Source LOD0 simplified by meshoptimizer at %.1f%% relative error' % (SIMPLIFY[stem]*100),
                             collision_triangles=0, collision_recovery='Existing source collider retained; visual only'))
    current = audit(OUT/'mp_party_crasher.bsp')['native_padded_indices']
    # Retired triangles are credited in full; their simplified replacements count as new below.
    room = INDEX_CAPACITY*PLAN_FRACTION-current+3*sum(len(r) for r in retire)
    from append_free_charts import free_tiles
    chart_room = len(free_tiles(OUT/'mp_party_crasher.bsp'))+sum(len(r) for r in retire)
    used = sum(len(t) for _, t in pieces); meshes = len(pieces)
    # 2. Reported props first, then cafe furniture nearest the q34 booth.
    omitted = {p['index']: p for p in scene['omitted']}
    queue = [(p, 0, REPORTED[i]) for i, p in ((i, omitted.get(i)) for i in REPORTED) if p]
    missing = [i for i in REPORTED if i not in omitted]
    if missing:
        raise ValueError(f'Reported placements not omitted: {missing}')
    cafe = sorted((p for p in scene['omitted'] if Path(p['model']).stem.lower() in CAFE and p['index'] not in REPORTED
                   and np.linalg.norm(np.asarray(p['origin'])-CAFE_CENTRE) < CAFE_RADIUS),
                  key=lambda p: (np.linalg.norm(np.asarray(p['origin'])-CAFE_CENTRE), p['index']))
    queue += [(p, CAFE[Path(p['model']).stem.lower()], 'cafe') for p in cafe]
    for p, lod, kind in queue:
        try:
            path = index[Path(p['model']).stem.lower()]
            levels = struct.unpack_from('<18Q', (path/(path.name+'.vg')).read_bytes(), 16)[13]
            lod = min(lod, levels-1); local, raw = geometry(dict(p, folder=str(path)), lod)
            local = [(name, place(s, p)) for name, s, _ in local]
            for name, _ in local:
                if name not in mapping and not (OUT/'legion/exported_files/materials'/name/(name+'_albedoTexture.dds')).is_file():
                    raise ValueError('Source texture unavailable: '+name)
            count = sum(len(t) for _, t in local)
            cost = 3*(used+count)+3*(meshes+len(local)+(used+count)//512+1)
            if cost > room or used+count > chart_room:
                raise ValueError('Exceeds the %.0f%% native world index ceiling' % (INDEX_FRACTION*100))
            row = dict(p, folder=str(path), lod=lod, triangles=count, category=kind,
                       recovery='Exact source VG author LOD, skin, UV and placement')
            if p['index'] in RENDER_COLLISION:
                col = np.concatenate([t[:, :, :3] for name, t in local if not any(w in name.lower() for w in NON_SOLID)]).astype('f4')
                method = 'Drawn structural triangles (source collider misses the drawn shape)'
            else:
                col, method = recovery.collision(row, [np.asarray(s, 'f4') for s in raw])
            row.update(collision_triangles=len(col), collision_recovery=method)
            selected.append(row); pieces.extend(local); physics.append(col); used += count; meshes += len(local)
        except (KeyError, ValueError, OSError, struct.error) as error:
            skipped.append(dict(index=p['index'], model=p['model'], reason=str(error), category=kind))
    names = list(dict.fromkeys(n for n, _ in pieces))
    np.savez(PROJECT/'addition.npz', triangles=np.concatenate([t for _, t in pieces]),
             material=np.concatenate([np.full(len(t), names.index(n), 'i4') for n, t in pieces]),
             names=names, collision=np.concatenate(physics) if physics else np.empty((0, 3, 3), 'f4'))
    np.save(PROJECT/'retire-points.npy', np.concatenate(retire))
    added = [p for p in selected if not p.get('replacement')]
    report = dict(version='0.6.2', added_props=len(selected), added_triangles=used, freed_triangles=freed,
                  placements=selected, skipped=skipped, baseline_padded_indices=current,
                  categories=dict(collections.Counter(p['category'] for p in selected)),
                  restored=len(added), simplified=len(selected)-len(added), maximum_world_index_fraction=INDEX_FRACTION,
                  policy='Simplify single-LOD heavy props in the arena; reported omitted props, then cafe furniture')
    structure.write(PROJECT/'plan.json', report)
    print(json.dumps({k: report[k] for k in ('restored', 'simplified', 'added_triangles', 'freed_triangles', 'categories')}),
          'skipped', [(s['index'], s['reason'][:40]) for s in skipped if s['category'] != 'cafe'], flush=True)


def materials():
    configure()
    structure.materials()


def apply():
    from upgrade_placement_lods import retire
    configure()
    recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP = OUT, PROJECT, OUT/'mp_party_crasher.bsp', BACKUP
    retire('party-crasher', PROJECT)
    direction = -np.asarray(json.loads((OUT/'environment.json').read_text())['native_sun_normal'])
    from append_free_charts import append as append_free
    append_free(OUT/BAKE_BASE, INDEX_FRACTION, str(structure.WORK/'tools/bake_arena_environment.exe'), direction.tolist())
    scene = json.loads((OUT/'scene.json').read_text())
    scene['placements'] = list({p['index']: p for p in scene['placements']}.values()); scene['props'] = len(scene['placements'])
    structure.write(OUT/'scene.json', scene)
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_party_crasher', 'party_crasher_world')


# --- Texture fixes ---------------------------------------------------------

def bc4_decode(raw, w, h):
    blocks = np.frombuffer(raw, 'u1')[:(w//4)*(h//4)*8].reshape(-1, 8)
    e0 = blocks[:, 0].astype('f4'); e1 = blocks[:, 1].astype('f4')
    bits = blocks[:, 2:8].astype('u8'); idx = np.zeros(len(blocks), 'u8')
    for i in range(6):
        idx |= bits[:, i] << np.uint64(8*i)
    codes = ((idx[:, None] >> (np.arange(16, dtype='u8')*np.uint64(3))) & np.uint64(7)).astype('i4')
    pal = np.empty((len(blocks), 8), 'f4'); pal[:, 0] = e0; pal[:, 1] = e1
    big = e0 > e1
    for k in range(1, 7):
        pal[:, k+1] = np.where(big, ((7-k)*e0+k*e1)/7, 0)
    for k in range(1, 5):
        pal[:, k+1] = np.where(big, pal[:, k+1], ((5-k)*e0+k*e1)/5)
    pal[:, 6] = np.where(big, pal[:, 6], 0); pal[:, 7] = np.where(big, pal[:, 7], 255)
    v = np.take_along_axis(pal, codes, 1).reshape(h//4, w//4, 4, 4)
    return v.transpose(0, 2, 1, 3).reshape(h, w)


def bc4_encode(img):
    h, w = img.shape; b = img.reshape(h//4, 4, w//4, 4).transpose(0, 2, 1, 3).reshape(-1, 16).astype('f4')
    hi = b.max(1); lo = b.min(1); e0 = np.rint(hi).astype('u1'); e1 = np.rint(lo).astype('u1')
    flat = e0 == e1; e0 = np.where(flat & (e0 < 255), e0+1, e0); e1 = np.where(flat & (e0 == e1), e1-1, e1)
    a, c = e0.astype('f4'), e1.astype('f4')
    pal = np.stack([a, c]+[((7-k)*a+k*c)/7 for k in range(1, 7)], 1)
    codes = np.abs(b[:, :, None]-pal[:, None, :]).argmin(2).astype('u8')
    idx = np.zeros(len(b), 'u8')
    for i in range(16):
        idx |= codes[:, i] << np.uint64(3*i)
    out = np.zeros((len(b), 8), 'u1'); out[:, 0] = e0; out[:, 1] = e1
    for i in range(6):
        out[:, 2+i] = ((idx >> np.uint64(8*i)) & np.uint64(255)).astype('u1')
    return out.tobytes()


def scale_bc4(path, factor):
    raw = bytearray(path.read_bytes()); assert raw[84:88] == b'DX10' and struct.unpack_from('<I', raw, 128)[0] == 80
    h, w, mips = struct.unpack_from('<I', raw, 12)[0], struct.unpack_from('<I', raw, 16)[0], struct.unpack_from('<I', raw, 28)[0]
    at = 148; parts = [bytes(raw[:148])]
    for m in range(max(mips, 1)):
        mw, mh = max(1, w >> m), max(1, h >> m); bw, bh = max(4, mw), max(4, mh); n = (bw//4)*(bh//4)*8
        level = bc4_decode(bytes(raw[at:at+n]), bw, bh); parts.append(bc4_encode(np.clip(level*factor, 0, 255))); at += n
    assert at == len(raw)
    path.write_bytes(b''.join(parts))


def emblem(size):
    """An original north-star emblem: a long four-point star over a short diagonal one, in a ring."""
    import math
    from PIL import Image, ImageDraw
    s = size*4; im = Image.new('L', (s, s), 0); d = ImageDraw.Draw(im); c = s/2
    def star(long, short, turn):
        points = []
        for i in range(8):
            r = long if i % 2 == 0 else short; a = math.radians(turn+45*i-90)
            points.append((c+r*math.cos(a), c+r*math.sin(a)))
        d.polygon(points, fill=255)
    star(s*.47, s*.07, 0)
    star(s*.24, s*.05, 45)
    ring = s*.31
    d.ellipse((c-ring, c-ring, c+ring, c+ring), outline=255, width=int(s*.024))
    d.ellipse((c-s*.035, c-s*.035, c+s*.035, c+s*.035), fill=0)
    return im.resize((size, size), Image.Resampling.LANCZOS)


def atlas_image():
    from PIL import Image
    src = Image.open(OUT/'legion/exported_files/materials'/ATLAS/(ATLAS+'_albedoTexture.dds')).convert('RGBA')
    a = np.asarray(src).astype('f4'); W = src.width
    # The placeholder panel: the uniform pink rectangle right of the OASIS poster.
    region = a[int(W*.36):int(W*.58), int(W*.62):]; pink = np.median(region.reshape(-1, 4), 0)
    mask = (np.abs(a[:, :, :3]-pink[:3]).max(2) < 14)
    sub = mask[int(W*.30):int(W*.62), int(W*.6):]
    rows = np.flatnonzero(sub.mean(1) > .5); cols = np.flatnonzero(sub.mean(0) > .5)
    y0, y1 = rows.min()+int(W*.30), rows.max()+int(W*.30); x0, x1 = cols.min()+int(W*.6), cols.max()+int(W*.6)
    panel = a[y0:y1+1, x0:x1+1].copy(); dark = np.percentile(panel[:, :, :3].reshape(-1, 3), 2, axis=0)
    panel[:, :, :3] = pink[:3]
    size = int(min(y1-y0, x1-x0)*.78); mark = np.asarray(emblem(size)).astype('f4')/255
    oy, ox = (panel.shape[0]-size)//2, (panel.shape[1]-size)//2
    for ch in range(3):
        sub = panel[oy:oy+size, ox:ox+size, ch]; sub[:] = sub*(1-mark)+dark[ch]*mark
    a[y0:y1+1, x0:x1+1] = panel
    return Image.fromarray(np.clip(a, 0, 255).astype('u1')), (int(x0), int(y0), int(x1), int(y1))


def replace_bc3(path, image):
    """Re-encode an sRGB BC3 (DXGI 78) texture keeping its DX10 header and mip count."""
    import io
    from PIL import Image
    raw = path.read_bytes(); assert raw[84:88] == b'DX10' and struct.unpack_from('<I', raw, 128)[0] == 78
    h, w, mips = struct.unpack_from('<I', raw, 12)[0], struct.unpack_from('<I', raw, 16)[0], struct.unpack_from('<I', raw, 28)[0]
    current = image.convert('RGBA').resize((w, h), Image.Resampling.LANCZOS); parts = [raw[:148]]
    for m in range(max(mips, 1)):
        b = io.BytesIO(); current.save(b, format='DDS', pixel_format='DXT5'); parts.append(b.getvalue()[128:])
        current = current.resize((max(1, current.width//2), max(1, current.height//2)), Image.Resampling.BOX)
    out = b''.join(parts)
    if len(out) != len(raw):
        raise ValueError('Re-encoded texture size differs')
    path.write_bytes(out)


def textures():
    from recover_arena_atmosphere import NativeMaterials
    keep = BACKUP/'texture-originals'; keep.mkdir(parents=True, exist_ok=True)
    foam = TEXTURES/(FOAM+'_opacityMultiply.dds'); atlas = TEXTURES/(ATLAS+'_albedo.dds')
    for p in (foam, atlas):
        if (keep/p.name).exists():
            shutil.copy2(keep/p.name, p)  # rebuilds start from the original asset
        else:
            shutil.copy2(p, keep/p.name)
    scale_bc4(foam, FOAM_OPACITY)
    image, box = atlas_image(); replace_bc3(atlas, image)
    image.resize((1024, 1024)).save(PROJECT/'atlas-preview.png')
    manifest = json.loads((OUT/'materials/build.json').read_text())
    NativeMaterials(OUT/'materials', 'party_crasher', manifest).finish(manifest)
    from build_preview_stbsp import build
    build(OUT, OUT/'materials', 'mp_party_crasher', 'party_crasher_world')
    structure.write(PROJECT/'textures.json', dict(foam_opacity_scale=FOAM_OPACITY, foam_texture=foam.name,
                                                  atlas_texture=atlas.name, atlas_panel_source_pixels=box,
                                                  originals=str(keep)))
    print('Foam opacity x', FOAM_OPACITY, '; atlas panel', box, flush=True)


def stage():
    """Copy the accepted 0.6.1 mod and swap only the rebuilt map/STBSP/world pack."""
    from map_pack_lifetime import audit as pack_audit
    from new_arena_ports import WORK
    from package_player_mods import digest
    accepted = ROOT/'northstar/ArenaPartyCrasher'
    if json.loads((accepted/'mod.json').read_text())['Version'] != '0.6.1':
        raise ValueError('Unexpected accepted baseline version')
    if digest(BACKUP/'mp_party_crasher.bsp') != digest(accepted/'mod/maps/mp_party_crasher.bsp'):
        raise ValueError('Round baseline is not the accepted 0.6.1 payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run the binary audit first')
    candidate = WORK/'report4-candidates'/'ArenaPartyCrasher'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for relative, source in (('mod/maps/mp_party_crasher.bsp', OUT/'mp_party_crasher.bsp'),
                             ('mod/maps/mp_party_crasher.stbsp', OUT/'mp_party_crasher.stbsp'),
                             ('paks/party_crasher_world.rpak', OUT/'materials/build/party_crasher_world.rpak')):
        shutil.copy2(source, candidate/relative)
        if digest(source) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = '0.6.2'
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    pack_audit(candidate/'paks', 'mp_party_crasher')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['cache', 'plan', 'materials', 'apply', 'textures', 'stage'])
    dict(cache=cache, plan=plan, materials=materials, apply=apply, textures=textures, stage=stage)[p.parse_args().action]()
