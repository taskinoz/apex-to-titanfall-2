"""Draw the placements a port's world budget omitted as native Titanfall static props.

prepare_new_arena_scene.py bakes props into world meshes under a triangle budget (920,000 for Thunderdome), and
omits the rest while their collision stays in the world: invisible floors, walls and holes (Thunderdome 0.2.0
user report, docs/candidates/thunderdome-user-report-2026-10-29.md). Static props draw outside the world index
cap with their own LOD switching (docs/candidates/static-prop-conversion-2026-10-24.md), so each omitted model is
compiled once with r2studiomdl and placed natively:

* model: every Apex LOD as an SMD (build_apex_static_prop.smd), `$lod` switch distances from the model radius
  (LOD_NEAR x radius, doubling), one `.mdl` per (model, skin) used, no physics: the world already collides;
* materials: a `fix` and `skn` clone of common.rpak's can_soda per Apex material. Textures already loaded by the
  world RPak (its mapping.json) are referenced by path; others are converted from the export at <= TEXTURE_CAP;
  unresolved materials get a neutral grey;
* BSP: one `sprp` v13 placement per omitted prop (retail template record, source origin/angles/scale, solid 0),
  object references from align64(meshes) (add_stock_props.apply, no 0x60 primitives) and the nearest light
  probe (lump 0x68 positions) per placement.

The package is written beside the source package as <name>-props, with its own `<slug>_props.rpak` loaded after
the world RPak:

  python build_native_props.py thunderdome <source package> [--foliage]
"""
import argparse
import collections
import concurrent.futures
import re
import threading
import csv
import functools
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from read_vg_static import load, levels
from prepare_new_arena_scene import asset_index as _asset_index, foliage
from repair_preview_index_padding import read_lumps
from build_apex_static_prop import smd, pakguid, COMPILER, REPAK, TEMPLATE
from extract_native_material import NativePak
import add_stock_props

NAMESPACE = 'models/apex'
LOD_NEAR = 12.0           # LOD1 switch distance in model radii; each further LOD doubles it
MIN_SWITCH = 384.0
# Foliage fade, as retail does it: the model's $fadedistance and the placement's fade distance (record bytes 36-40,
# which bsp_tool labels forced_fade_scale; -1 = use the model's). Retail small ground plants (radius 34-80) fade at
# 1,035, larger plants and bushes at 2,300-4,100, a birch at 5,520; Homestead grass placements use 1,200-2,800.
# Small foliage also gets flag 0x10 (retail: grass only), Source's no-shadow flag.
FOLIAGE_FADE = ((150., 1500.), (600., 3500.), (float('inf'), 6000.))   # (radius below, fade distance)
NO_SHADOW = 0x10
# Overlay layers (Apex blends them over the surface below by vertex alpha) are coplanar copies here, so they
# z-fight. Their fully transparent triangles (every vertex alpha below OVERLAY_ALPHA) are dropped and the rest are
# lifted OVERLAY_OFFSET units along their normals.
OVERLAY = re.compile(r'transparent|blend_?2_?trans|_trans(?:_|$)|decal|font_|seam|stencil|stain')  # material names; *decal* models are all overlay
OVERLAY_ALPHA, OVERLAY_OFFSET = 64, 0.4
# Two-layer (bm) blends: the fix shader draws one layer, so each blend section is split per triangle. The world's
# native bm equation (apply_layer_blends.py) is w = saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha), ramp 4; at the
# mask's midpoint that is layer 2 where the triangle's mean vertex alpha exceeds one half. Layer-2 triangles use
# `<material>__l2`, built from the second layer's textures.
BLEND = re.compile(r'_bm(?:_|$)|blend|_to_')
LAYER2 = '__l2'
# Unsaturated blends (vertex alpha between BLEND_RANGE) are per-pixel in Apex, driven by the layer-blend mask: layer 1
# is drawn everywhere and a copy lifted OVERLAY_OFFSET carries layer 2 as a cutout whose alpha is the mask above the
# equation's midpoint at the section's mean vertex alpha a: mask > (4.5 - 5a)/4 (BLEND_THRESHOLD, per material).
LAYER2_CUTOUT = '__l2c'
BLEND_RANGE = (0.1, 0.9)
BLEND_THRESHOLD = {}
# Glow materials: holograms (td2_holo_skull_01, td2_holo_signs_01) and every other material that is additive in Apex
# (blend 0xF0138086, RSX_ADDITIVE; td2_metal_sheet_seam_emiss_01). Titanfall's additive templates (crow_dropship_
# afterburner, beacon_big_screen_animation_01) drew nothing at all on the Thunderdome skull (30 October 2026), and
# led_light01 stopped the map loading, so a glow is drawn as a lit cutout: illumination map x the section's constant
# vertex tint (TINTS; the seams are 193, 61, 72) x its mask, keeping texels where the mask, or else the glow, exceeds
# GLOW_CUT.
HOLO = re.compile(r'holo')
GLOW_CUT = 24
TINTS = {}  # material -> uniform non-white vertex RGB, filled by compile_model
# Props larger than LIGHT_RADIUS take their light probe and lighting origin from the top of their bounds: one probe
# at the base of the 2,700-unit skull sat in its shadow and drew it black.
LIGHT_RADIUS = 512.
TEXTURE_CAP = 512
# Alpha-tested (cutout) materials clone Homestead's grass: glue 0x560000B0, two-sided, common.rpak's foliage shader
# set, and per-material shadow/prepass/VSM depth materials that sample the albedo's alpha (all shaders resident in
# common.rpak). An albedo is a cutout when more than CUTOUT_FRACTION of its texels have alpha below 128.
ALPHA_TEMPLATE = 'models\\foliage\\grass_golden_long_01'
CUTOUT_FRACTION = 0.02
DEPTH_PASSES = (('$depthShadowMaterial', 'shadow'), ('$depthPrepassMaterial', 'prepass'), ('$depthVSMMaterial', 'vsm'))
SKIP = ('toolsblack', 'toolsskybox', 'godray', 'ambient_occlusion', 'atmosphere', 'start_barrier')
SEMANTICS = (('0', 'albedo'), ('1', 'normal'), ('2', 'gloss'), ('3', 'spec'))
asset_index = functools.lru_cache(_asset_index)


def selection(ident, with_foliage):
    """Omitted by the world budget, or because the model was never exported (export_models recovers those)."""
    scene = json.loads((folder(ident)/'scene.json').read_text())
    return [p for p in scene['omitted'] if p['reason'].startswith(('Conservative', 'Compiled source model not recovered'))
            and (with_foliage or not foliage(p['model']))]


MODEL_PAKS = ('common.rpak', 'common(01).rpak', 'common_mp.rpak', 'common_mp(01).rpak')


def export_models(ident):
    """Export from the retail common paks (RSX, Cast) the models the map pak export lacked (Thunderdome: zipline arms,
    barrels, gun racks, a rock, pipe caps), into the Legion model folder asset_index scans."""
    wanted = sorted({Path(p['model']).stem.lower() for p in selection(ident, True)} - set(_asset_index(ident)))
    if not wanted:
        return []
    dest = folder(ident)/'rsx-model-export'; shutil.rmtree(dest, ignore_errors=True); dest.mkdir()
    with (dest/'export.log').open('w') as log:
        subprocess.run([str(RSX), '-nogui', '-nocachedb', '-export', '--exporttypes', 'mdl_', '--exportformats', 'mdl_=CAST',
                        '--exportfilter', ','.join(wanted), '--exportthreads', '8', '--exportdir', str(dest/'raw'),
                        *[str(APEX_PAKS/p) for p in MODEL_PAKS if (APEX_PAKS/p).exists()]],
                       cwd=dest, stdout=log, stderr=subprocess.STDOUT, check=True)
    models = folder(ident)/'legion/exported_files/models'; got = []
    for d in (dest/'raw').rglob('*_LOD0.cast'):
        if d.parent.name.lower() in wanted and not (models/d.parent.name).exists():
            shutil.move(str(d.parent), str(models/d.parent.name)); got.append(d.parent.name)
    asset_index.cache_clear()
    return sorted(got)


def overlay(section):
    t = np.asarray(section, 'f8').reshape(-1, 3, 12)
    t = t[t[:, :, 11].max(1) >= OVERLAY_ALPHA].copy(); t[:, :, :3] += t[:, :, 3:6]*OVERLAY_OFFSET
    return t.reshape(-1)


def variant(name, names):
    """Apex material names carry variant suffixes the Cast export drops (tree_acacia_small_01 ->
    tree_acacia_small_01_wind_avt, antenna_03_colony -> antenna_03_colony_noalpha): the shortest `<name>_...`."""
    return min((n for n in names if n.startswith(name+'_')), key=len, default=None)


def compile_model(ident, model, skin, out, work):
    """One .mdl for (model, skin); returns its materials and bounding radius, or None if nothing drawable."""
    path = asset_index(ident)[model]; target = f'apex/{ident}/{model}' + (f'_skin{skin}' if skin else '') + '.mdl'
    w = work/(Path(target).stem); w.mkdir(parents=True, exist_ok=True)
    used, lods, radius = set(), [], 0.
    for lod in range(levels(path)):
        sections, slots, skins = load(path, lod, with_colors=True); names = skins[min(skin, len(skins)-1)]
        keep = [(overlay(s) if 'decal' in model or OVERLAY.search(names[k].lower()) else s, k) for s, k in zip(sections, slots)
                if len(s) and not any(x in names[k].lower() for x in SKIP)]
        keep = [(s, k) for s, k in keep if len(s)]
        names = list(names); split = []
        for s, k in keep:
            if BLEND.search(names[k].lower()):
                t = np.asarray(s, 'f8').reshape(-1, 3, 12); a = float(t[:, :, 11].mean())/255
                if BLEND_RANGE[0] < a < BLEND_RANGE[1]:
                    name2 = names[k]+LAYER2_CUTOUT; BLEND_THRESHOLD.setdefault(name2, min(1., max(0., (4.5-5*a)/4)))
                    if name2 not in names:
                        names.append(name2)
                    lifted = t.copy(); lifted[:, :, :3] += lifted[:, :, 3:6]*OVERLAY_OFFSET
                    split += [(t.reshape(-1), k), (lifted.reshape(-1), names.index(name2))]
                    continue
                second = t[:, :, 11].mean(1) > 127.5
                if second.any():
                    if names[k]+LAYER2 not in names:
                        names.append(names[k]+LAYER2)
                    split.append((t[second].reshape(-1), names.index(names[k]+LAYER2)))
                s = t[~second].reshape(-1)
            if len(s):
                split.append((s, k))
        keep = split
        if not keep:
            break
        smd(w/f'lod{lod}.smd', [s for s, _ in keep], [k for _, k in keep], names, NAMESPACE+'/'+ident)
        used.update(names[k] for _, k in keep); lods.append(lod)
        if lod == 0:
            verts = np.concatenate([np.asarray(s, 'f4').reshape(-1, 12) for s, _ in keep])
            radius = float(np.linalg.norm(verts[:, :3], axis=1).max())
            top = [*((verts[:, :2].min(0)+verts[:, :2].max(0))/2).tolist(), float(verts[:, 2].max())]
            for s, k in keep:
                rgb = np.asarray(s, 'f4').reshape(-1, 12)[:, 8:11]
                if rgb.std(0).max() < 2 and rgb.mean() < 250:
                    TINTS.setdefault(names[k], tuple(rgb.mean(0).round().astype(int).tolist()))
    if not lods:
        return None
    qc = [f'$modelname "{target}"', '$cdmaterials ""', '$body "body" "lod0.smd"', '$staticprop', '$surfaceprop "default"',
          '$sequence "idle" "lod0.smd"']
    for i, lod in enumerate(lods[1:], 1):
        qc.append(f'$lod {max(MIN_SWITCH, radius*LOD_NEAR)*2**(i-1):.0f} {{ replacemodel "lod0.smd" "lod{lod}.smd" }}')
    fade = next(d for r, d in FOLIAGE_FADE if radius < r) if foliage(model) and 'building' not in model else None
    if fade:
        qc.append(f'$fadedistance {fade:.0f}')
    (w/'model.qc').write_text('\n'.join(qc)+'\n')
    mdl = out/'models'/target; mdl.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([str(COMPILER), '-o', str(mdl), str(w/'model.qc')], capture_output=True, text=True)
    (w/'compile.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise RuntimeError(f'{model}: '+run.stdout[-2000:]+run.stderr)
    return dict(mdl='models/'+target, materials=sorted(used), radius=radius, top=top, lods=len(lods), bytes=mdl.stat().st_size, fade=fade)


DXGI = {71: 'BC1_UNORM', 72: 'BC1_UNORM_SRGB', 74: 'BC2_UNORM', 75: 'BC2_UNORM_SRGB', 77: 'BC3_UNORM', 78: 'BC3_UNORM_SRGB',
        80: 'BC4_UNORM', 83: 'BC5_UNORM', 95: 'BC6H_UF16', 98: 'BC7_UNORM', 99: 'BC7_UNORM_SRGB'}
FOURCC = {b'DXT1': 'BC1_UNORM', b'DXT3': 'BC2_UNORM', b'DXT5': 'BC3_UNORM', b'ATI1': 'BC4_UNORM', b'BC4U': 'BC4_UNORM',
          b'ATI2': 'BC5_UNORM', b'BC5U': 'BC5_UNORM'}


def convert(src, dest, srgb):
    """Keep the source format (as repair_thunderdome.py does), at most TEXTURE_CAP, albedo as sRGB."""
    head = src.read_bytes()[:148]; height, width = struct.unpack_from('<2I', head, 12)
    fmt = DXGI[struct.unpack_from('<I', head, 128)[0]] if head[84:88] == b'DX10' else FOURCC[head[84:88]]
    scale = min(1, TEXTURE_CAP/max(width, height))
    temp = dest.parent/('conv-'+dest.stem); temp.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f', fmt,
                          '-dx10', '-w', str(max(4, int(width*scale))), '-h', str(max(4, int(height*scale))),
                          '-o', str(temp), str(src)], capture_output=True, text=True)
    if run.returncode:
        raise ValueError(run.stdout+run.stderr)
    data = bytearray((temp/src.name).read_bytes()); shutil.rmtree(temp)
    if srgb and struct.unpack_from('<I', data, 128)[0] in (71, 74, 77, 98):
        struct.pack_into('<I', data, 128, struct.unpack_from('<I', data, 128)[0]+1)
    dest.write_bytes(data)


RSX_ROOTS = [Path('D:/Games/ApexToTitanfallWork/apex-current'), *sorted((ROOT/'output').glob('thunderdome-*'))]
RSX_SEMANTICS = (('0', 'albedo', '_col'), ('1', 'normal', '_nml'), ('2', 'gloss', '_gls'), ('3', 'spec', '_spc'))


def rsx_index(work):
    """RSX material exports (current Apex, and the shared/source exports of the Thunderdome repairs), keyed by
    material GUID (pak GUID of `material/<json name>_<shader>.rpak`) and by base name (rigid `_rgdp` preferred);
    each value lists (slot, semantic, first-layer DDS) for the fix shader's four slots."""
    folders = [p for root in RSX_ROOTS for p in root.glob('**/exported_files/material/*') if (p/(p.name+'.json')).exists()]
    RSX_LAYER2.clear(); RSX_ILM.clear(); RSX_MASK.clear(); RSX_ADDITIVE.clear()

    def entry(p):
        try:
            spec = json.loads((p/(p.name+'.json')).read_text())
        except ValueError:
            return None
        types, refs = spec.get('$textureTypes', {}), spec.get('$textures', {}); out = []
        second = []
        for slot, semantic, kind in RSX_SEMANTICS:
            found = [p/(Path(refs[k]).stem+'.dds') for k in sorted((k for k, t in types.items() if t == kind), key=int)]
            found = [f for f in found if f.exists()]
            if found:
                out.append((slot, semantic, found[0]))
            if len(found) > 1:
                second.append((slot, semantic, found[1]))
        if not spec.get('name') or '_colpass' in p.name:
            return None
        base = spec['name'].rsplit('/', 1)[-1]
        # A projection layer with its coverage mask (td2_holo_skull_01_1_ilm / _1_msk; the skull's unnumbered _ilm is
        # a dot-grid scanline overlay), else the first illumination map (the seams' _ilm strip; their 1 x 2048 _msk is
        # a pulse ramp, not a UV mask).
        layer = sorted(p.glob('*_1_msk.dds'))
        ilm = [p/(layer[0].name.replace('_msk', '_ilm'))] if layer else sorted(p.glob('*_ilm.dds'), key=lambda f: ('_1_' in f.name, f.name))
        if ilm and ilm[0].exists() and (base not in RSX_ILM or layer and RSX_ILM[base][1] is None):  # another export may lack the mask
            RSX_ILM[base] = (ilm[0], layer[0] if layer else None)
        if spec.get('blendStates', ['0x0'])[0] == '0xF0138086':
            RSX_ADDITIVE.add(base)
        if second:
            RSX_LAYER2.setdefault(base, second)
        mask = [p/(Path(refs[k]).stem+'.dds') for k, t in sorted(types.items(), key=lambda x: int(x[0])) if t == '_bm']
        if mask and mask[0].exists():
            RSX_MASK.setdefault(base, mask[0])
        if not any(s == '0' for s, _, _ in out):
            return None
        # Unpadded, as Cast's numeric material names: 0x034717147C928E10 is `0x34717147C928E` (td2_rui_screen_bg).
        return f'{pakguid("material/"+spec["name"]+"_"+p.name.rsplit("_", 1)[1]+".rpak"):X}', spec['name'].rsplit('/', 1)[-1], p.name, out

    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        entries = [e for e in pool.map(entry, folders) if e]
    by_guid = {g: out for g, _, _, out in entries}; by_name = {}
    for _, name, shader, out in sorted(entries, key=lambda e: not e[2].endswith('_rgdp')):
        by_name.setdefault(name, out)
    work.mkdir(parents=True, exist_ok=True); (work/'rsx-index.json').write_text(json.dumps({g: [str(s) for _, _, s in o] for g, o in by_guid.items()}, indent=0))
    return by_guid, by_name


RSX_LAYER2, RSX_ILM, RSX_MASK = {}, {}, {}  # filled by rsx_index: base name -> second-layer (slot, semantic, DDS) / (_ilm, _msk) DDS
RSX_ADDITIVE = set()  # base names whose Apex material is additive
RSX = Path('D:/Games/ApexToTitanfallWork/rsx-latest/bin/Release_NoGui/rsx.exe')
APEX_PAKS = Path('D:/Games/Apex/paks/Win64')
ASSET_LIST = ROOT/'output/thunderdome-repair-2026-10-29/shared-export/all-assets.csv'  # repair_thunderdome.py --list


def export_missing(ident, names, world_mapping):
    """Export from the retail Apex paks (RSX) the materials no existing export has, found by name or GUID prefix in
    the repair's asset list. RSX writes under its working directory, so it runs from the (D:) destination."""
    by_guid, by_name = rsx_index(folder(ident)/'native-props')
    exported = folder(ident)/'legion/exported_files/materials'
    missing = [n for n in names if not (n in world_mapping and world_mapping[n].get('recovered')) and n not in by_name and not variant(n, by_name)
               and not any((exported/v/f'{v}_albedoTexture.dds').exists() for v in (n, n+'_avt'))
               and not (n.startswith('0x') and any(g.startswith(n[2:].upper()) for g in by_guid))]
    rows = [r for r in csv.DictReader(ASSET_LIST.open()) if r['type'] == 'matl']
    wanted, packs = set(), set()
    for n in missing:
        for r in rows:
            base = r['asset_name'].replace('\\', '/').rsplit('/', 1)[-1].removesuffix('.rpak').rsplit('_', 1)[0]
            if (r['guid'].upper().startswith(n[2:].upper()) if n.startswith('0x') else base == n or base.startswith(n+'_')):
                wanted.add(base); packs.add(r['file_name'])
    if not wanted:
        return dict(missing=len(missing), exported=0)
    destination = folder(ident)/'rsx-props-export'; destination.mkdir(exist_ok=True)
    inputs = [APEX_PAKS/p for p in ('common_early.rpak', 'common.rpak', 'common(01).rpak', 'common_mp.rpak', 'common_mp(01).rpak',
                                    CONFIG[ident]['source']+'.rpak') if (APEX_PAKS/p).exists()]
    with (destination/'export.log').open('w') as log:
        subprocess.run([str(RSX), '-nogui', '-nocachedb', '-export', '-matltextures', '--texnames', 'semantic',
                        '--exportformats', 'txtr=DDS (Highest Mip),matl=Uber (Raw)', '--exporttypes', 'matl',
                        '--exportfilter', ','.join(sorted(wanted)), '--exportthreads', '4', '--exportdir', str(destination),
                        *map(str, inputs)], cwd=destination, stdout=log, stderr=subprocess.STDOUT, check=True)
    return dict(missing=len(missing), exported=len(wanted), packs=sorted(packs))


def materials(ident, names, world_mapping, world_assets, work):
    slug = ident.replace('-', '_'); assets = work/'assets'; files = []; report = collections.Counter()
    pak = NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak'); templates = {}
    for a in pak.assets:
        if a['type'] == 'matl' and a['version'] == 12:
            at = pak.address(a['header'])
            if pak.string(struct.unpack_from('<2I', pak.data, at+24)) == TEMPLATE:
                templates[a['guid']] = pak.material(a)
    exported = folder(ident)/'legion/exported_files/materials'; cutout = {}
    home = NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak'); alpha = {}
    for kind_guid in (pakguid(f'material/{ALPHA_TEMPLATE.replace(chr(92), "/")}_fix.rpak'),):
        alpha['fix'] = home.material(next(a for a in home.assets if a['guid'] == kind_guid))
        for field, label in DEPTH_PASSES:
            g = int(alpha['fix'][0][field], 16); alpha[label] = home.material(next(a for a in home.assets if a['guid'] == g))
    # The pak carries its own copy of every world texture it uses (at TEXTURE_CAP): referencing the world RPak's
    # textures by GUID instead left the map load spinning before it started (both paks load after mp_coliseum).
    locks = collections.defaultdict(threading.Lock)

    def own(path):
        target = f'texture/{NAMESPACE}/{slug}/world_{Path(path).stem}.rpak'; dest = (assets/target).with_suffix('.dds')
        with locks[target]:  # once per texture, also across workers
            if target not in cutout:
                dest.parent.mkdir(parents=True, exist_ok=True); convert((world_assets/path).with_suffix('.dds'), dest, False)
                files.append({'_type': 'txtr', '_path': target, '$disableStreaming': True}); cutout[target] = is_cutout(dest)
        return target
    neutral = {k: own(f'texture/{slug}/neutral_{s}.rpak') for k, s in (('1', 'normal'), ('2', 'gloss'), ('3', 'spec'))}
    grey = f'texture/{NAMESPACE}/{slug}/neutral_albedo.rpak'
    from PIL import Image
    g = (assets/grey).with_suffix('.dds'); g.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (16, 16), (128, 128, 128)).save(g.with_suffix('.png'))
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f', 'BC1_UNORM_SRGB', '-o', str(g.parent),
                    str(g.with_suffix('.png'))], check=True, capture_output=True); g.with_suffix('.png').unlink()
    files.append({'_type': 'txtr', '_path': grey, '$disableStreaming': True})

    by_guid, by_name = rsx_index(work)


    def add(name, semantic, src):
        """Convert once per destination: a layer-2 lookup can fall back to layer 1 in another worker."""
        path = f'texture/{NAMESPACE}/{slug}/{name}_{semantic}.rpak'; dest = (assets/path).with_suffix('.dds')
        with locks[path]:
            if path not in cutout and not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True); convert(src, dest, semantic == 'albedo')
                files.append({'_type': 'txtr', '_path': path, '$disableStreaming': True})
                cutout[path] = is_cutout(dest) if semantic == 'albedo' else False
        return path

    def resolve(name):
        if name.endswith(LAYER2_CUTOUT):
            return resolve_cutout_layer2(name)
        if name.endswith(LAYER2):
            return resolve_layer2(name.removesuffix(LAYER2))
        base = name if name in RSX_ILM else variant(name, RSX_ILM) or name  # td2_holo_skull_01, not its _uh variant
        if (HOLO.search(name.lower()) or base in RSX_ADDITIVE) and base in RSX_ILM:
            report['glow'] += 1
            return dict(neutral, **{'0': glow(name, *RSX_ILM[base])})
        if name in world_mapping and world_mapping[name].get('recovered'):
            report['world'] += 1  # the fix shader has slots 0-3 only (no blend layers)
            return dict(neutral, **{k: own(v) for k, v in world_mapping[name]['textures'].items() if k in ('0', '1', '2', '3')})
        for v in (name, name+'_avt'):  # Legion layout: <name>/<name>_<semantic>Texture.dds
            source = exported/v
            if (source/f'{v}_albedoTexture.dds').exists():
                report['converted'] += 1
                return dict(neutral, **{slot: add(name, semantic, source/f'{v}_{semantic}Texture.dds') for slot, semantic in SEMANTICS
                                        if (source/f'{v}_{semantic}Texture.dds').exists()})
        # RSX layout: Cast names unexported materials by the top digits of their GUID (0x40AEDBA289B54).
        rsx = by_name.get(name) or by_name.get(variant(name, by_name) or '') or \
            next((v for g, v in by_guid.items() if name.startswith('0x') and g.startswith(name[2:].upper())), None)
        if rsx:
            report['rsx'] += 1
            return dict(neutral, **{slot: add(name, semantic, src) for slot, semantic, src in rsx})
        report['neutral'] += 1; return dict(neutral, **{'0': grey})

    def resolve_layer2(base):
        """The second layer: world mapping slots 23-26, Legion `<semantic>2Texture`, or the RSX second layer."""
        if base in world_mapping and world_mapping[base].get('recovered') and '23' in world_mapping[base]['textures']:
            report['layer2'] += 1; t = world_mapping[base]['textures']
            return dict(neutral, **{str(i): own(t[str(23+i)]) for i in range(4) if str(23+i) in t})
        for v in (base, base+'_avt'):
            source = exported/v
            if (source/f'{v}_albedo2Texture.dds').exists():
                report['layer2'] += 1
                return dict(neutral, **{slot: add(base+LAYER2, semantic, source/f'{v}_{semantic}2Texture.dds') for slot, semantic in SEMANTICS
                                        if (source/f'{v}_{semantic}2Texture.dds').exists()})
        second = RSX_LAYER2.get(base) or RSX_LAYER2.get(variant(base, RSX_LAYER2) or '')
        if second and any(s == '0' for s, _, _ in second):
            report['layer2'] += 1; return dict(neutral, **{slot: add(base+LAYER2, semantic, src) for slot, semantic, src in second})
        return resolve(base)  # no second layer found: draw layer 1

    def mask_source(base):
        if base in world_mapping and world_mapping[base].get('recovered') and '22' in world_mapping[base]['textures']:
            return (world_assets/world_mapping[base]['textures']['22']).with_suffix('.dds')
        for v in (base, base+'_avt'):
            if (exported/v/f'{v}_layerBlendTexture.dds').exists():
                return exported/v/f'{v}_layerBlendTexture.dds'
        return RSX_MASK.get(base) or RSX_MASK.get(variant(base, RSX_MASK) or '')

    def resolve_cutout_layer2(name):
        """Layer 2's textures with an albedo whose alpha is the thresholded blend mask (a cutout)."""
        from restore_banner_display_textures import image_dds
        base = name.removesuffix(LAYER2_CUTOUT); layer2 = resolve_layer2(base); mask = mask_source(base)
        if not mask or layer2 is None:
            return None
        albedo = (assets/layer2['0']).with_suffix('.dds')
        rgb = image_dds(albedo).convert('RGB'); m = image_dds(mask).convert('L').resize(rgb.size, Image.Resampling.BILINEAR)
        alpha = np.where(np.asarray(m, 'f4')/255 > BLEND_THRESHOLD[name], 255, 0).astype('u1')
        path = f'texture/{NAMESPACE}/{slug}/{name}_albedo.rpak'; dest = (assets/path).with_suffix('.dds')
        with locks[path]:
            if path not in cutout:
                png = dest.with_suffix('.png'); Image.fromarray(np.dstack([np.asarray(rgb), alpha])).save(png)
                subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f', 'BC3_UNORM_SRGB', '-srgb',
                                '-o', str(dest.parent), str(png)], check=True, capture_output=True); png.unlink()
                files.append({'_type': 'txtr', '_path': path, '$disableStreaming': True}); cutout[path] = True
        report['blend_cutout'] += 1
        return dict(layer2, **{'0': path})

    def glow(name, ilm, mask):
        """Cutout albedo: illumination x vertex tint x mask, alpha from the mask (or the glow) above GLOW_CUT."""
        from restore_banner_display_textures import image_dds
        rgb = np.asarray(image_dds(ilm).convert('RGB'), 'f4')*np.asarray(TINTS.get(name, (255, 255, 255)), 'f4')/255
        m = np.asarray(image_dds(mask).convert('L').resize(rgb.shape[1::-1], Image.Resampling.BILINEAR), 'f4') if mask else rgb.max(2)
        if mask:
            rgb *= m[..., None]/255
        path = f'texture/{NAMESPACE}/{slug}/{name}_glow.rpak'; dest = (assets/path).with_suffix('.dds')
        with locks[path]:
            if path not in cutout:
                dest.parent.mkdir(parents=True, exist_ok=True); png = dest.with_suffix('.png')
                Image.fromarray(np.dstack([rgb.clip(0, 255), np.where(m > GLOW_CUT, 255, 0)]).astype('u1')).save(png)
                subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f', 'BC3_UNORM_SRGB', '-srgb',
                                '-o', str(dest.parent), str(png)], check=True, capture_output=True); png.unlink()
                files.append({'_type': 'txtr', '_path': path, '$disableStreaming': True}); cutout[path] = True
        return path

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        resolved = dict(zip(names, pool.map(resolve, names)))
    # A cutout second layer without a blend mask draws layer 1 again (its lifted copy then matches the surface).
    resolved = {n: (t if t is not None else resolved.get(n.removesuffix(LAYER2_CUTOUT)) or resolve(n.removesuffix(LAYER2_CUTOUT)))
                for n, t in resolved.items()}
    def write(path, spec, uber):
        target = assets/path; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(spec, indent=2)); target.with_suffix('.uber').write_bytes(uber)

    for name, textures in resolved.items():
        cut = cutout.get(textures['0'], False); report['cutout'] += cut
        for kind in ('fix', 'skn'):
            spec, uber = alpha['fix'] if cut and kind == 'fix' else templates[pakguid(f'material/{TEMPLATE.replace(chr(92), "/")}_{kind}.rpak')]
            spec = dict(spec, name=f'{NAMESPACE}/{ident}/{name}', shaderType=kind, blendStates=spec['blendStates']+['0x0']*4,
                        **{'$textures': textures, '$colpassMaterial': '0x0'})
            if cut and kind == 'fix':  # depth passes are auto-added by RePak from these paths
                for field, label in DEPTH_PASSES:
                    dspec, duber = alpha[label]; depth = f'material/depth/{NAMESPACE}/{ident}/{name}_{label}_fix.rpak'
                    write(depth.removesuffix('.rpak')+'.json', dict(dspec, name=f'depth/{NAMESPACE}/{ident}/{name}_{label}', shaderType='fix',
                          blendStates=dspec['blendStates']+['0x0']*4, **{'$textures': {'0': textures['0']}}), duber)
                    spec[field] = depth
            path = f'material/{NAMESPACE}/{ident}/{name}_{kind}.json'; write(path, spec, uber)
            files.append({'_type': 'matl', '_path': path.removesuffix('.json')+'.rpak'})
    files = list({f['_path']: f for f in files}.values())  # own() can race in the pool
    manifest = dict(version=7, name=slug+'_props', keepDevOnly=True, assetsDir=str(assets), outputDir=str(work/'build'),
                    compressLevel=0, hasDynamicLibrary=False, files=files)
    (work/'build.json').write_text(json.dumps(manifest, indent=2))
    run = subprocess.run([str(REPAK), str(work/'build.json')], capture_output=True, text=True)
    (work/'repak.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise RuntimeError(run.stdout[-3000:]+run.stderr)
    return work/'build'/(slug+'_props.rpak'), dict(report)


def is_cutout(dds_path):
    from restore_banner_display_textures import image_dds
    a = np.asarray(image_dds(dds_path).convert('RGBA'))[..., 3]
    return bool((a < 128).mean() > CUTOUT_FRACTION)


def lighting_point(p, b):
    """The placement origin, or for a prop over LIGHT_RADIUS the top centre of its bounds plus 64 units."""
    if b['radius']*p['scale'] <= LIGHT_RADIUS:
        return list(p['origin'])
    from stage_prop_geometry import rotation
    return (np.asarray(rotation(p['angles'])) @ np.asarray(b['top'])*p['scale']+np.asarray(p['origin'])+[0, 0, 64]).tolist()


def nearest_probes(bsp, points):
    """Nearest lit probe. Probes on the baked grid that sit inside geometry keep a flat default record (first eight
    int16 values 0, 0, 0, 180, 0, 0, 0, 213); a prop given one draws black (Thunderdome grass on dirt)."""
    l = read_lumps(bsp, (0x65, 0x68)); refs = np.array([r[:4] for r in struct.iter_unpack('<3fIi', l[0x68])])
    lit = np.array([any(struct.unpack_from('<8h', l[0x65], int(k)*48)[i] for i in (0, 1, 2, 4, 5, 6)) for k in refs[:, 3]])
    refs = refs[lit]; out = []
    for p in points:
        out.append(int(refs[np.argmin(((refs[:, :3]-p)**2).sum(1)), 3]))
    return out


def build(ident, source, with_foliage):
    source = Path(source); slug = ident.replace('-', '_')
    dst = source.parent/(source.name+'-props'); work = folder(ident)/'native-props'
    for d in (dst, work):
        shutil.rmtree(d, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copytree(source, dst, copy_function=lambda a, b: shutil.copy2(a, b) if a.endswith(('.bsp', '.json')) else os.link(a, b))
    props = selection(ident, with_foliage)
    recovered_models = export_models(ident); print('Exported models', recovered_models, flush=True)
    props = [p for p in props if Path(p['model']).stem.lower() in asset_index(ident)]
    combos = sorted({(Path(p['model']).stem.lower(), int(p['skin'])) for p in props})
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        built = dict(zip(combos, pool.map(lambda c: compile_model(ident, c[0], c[1], dst/'mod', work/'models'), combos)))
    print('Compiled', sum(1 for b in built.values() if b), 'of', len(combos), 'models', flush=True)
    # The installed world RPak's manifest: Thunderdome's is the 0.2.0 shared-material repair.
    built_world = ROOT/'output/thunderdome-repair-2026-10-29/materials' if ident == 'thunderdome' else folder(ident)/'materials'
    world = json.loads((built_world/'mapping.json').read_text())['materials']
    world_assets = Path(json.loads((built_world/'build.json').read_text())['assetsDir'])
    names = sorted({m for b in built.values() if b for m in b['materials']})
    RSX_ROOTS.append(folder(ident)/'rsx-props-export'); exported = export_missing(ident, names, world)
    rpak, texture_report = materials(ident, names, world, world_assets, work/'materials')
    shutil.copy2(rpak, dst/'paks')
    manifest = json.loads((dst/'paks/rpak.json').read_text())
    # Keyed to the game pak the world RPak follows (a mod pak as the key never loaded it); listed after the world
    # RPak, whose textures it references.
    manifest.setdefault('Postload', {})[rpak.name] = manifest['Postload'][slug+'_world.rpak']
    (dst/'paks/rpak.json').write_text(json.dumps(manifest, indent=2))
    # Placements: retail template record with the source transform; the world already owns collision.
    record = add_stock_props.template('models/containers/pelican_case_large.mdl')
    models = sorted({b['mdl'] for b in built.values() if b}); placements, points = [], []
    for p in props:
        b = built.get((Path(p['model']).stem.lower(), int(p['skin'])))
        if not b:
            continue
        r = bytearray(record)
        struct.pack_into('<7f', r, 0, *p['origin'], *p['angles'], p['scale'])
        flags = r[31] | (NO_SHADOW if b['fade'] and b['radius'] < FOLIAGE_FADE[0][0] else 0)
        struct.pack_into('<HBB', r, 28, models.index(b['mdl']), 0, flags); struct.pack_into('<HH', r, 32, 0, 0xffff)
        struct.pack_into('<f', r, 36, b['fade']*p['scale'] if b['fade'] else -1.)
        light = lighting_point(p, b)
        struct.pack_into('<3f', r, 40, *light)
        placements.append(bytes(r)); points.append(light)
    bsp = next((dst/'mod/maps').glob('*.bsp'))
    result = add_stock_props.apply(bsp, models, placements, solid=False, probes=nearest_probes(bsp, np.asarray(points)))
    report = dict(result, source=str(source), selected=len(props), foliage=with_foliage, models=len(models),
                  mdl_bytes=sum(b['bytes'] for b in built.values() if b), skipped=[list(c) for c, b in built.items() if not b],
                  materials=len(names), textures=texture_report, rsx_export=exported, exported_models=recovered_models, rpak_bytes=rpak.stat().st_size,
                  lod_near=LOD_NEAR, texture_cap=TEXTURE_CAP,
                  faded=collections.Counter(str(b['fade']) for b in built.values() if b and b['fade']))
    (dst/'native-props.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__); a.add_argument('ident'); a.add_argument('source')
    a.add_argument('--foliage', action='store_true'); args = a.parse_args()
    build(args.ident, args.source, args.foliage)
