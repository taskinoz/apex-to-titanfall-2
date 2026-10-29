"""Give world materials still drawn with the fallback texture their source textures, and rebuild the world RPak.

The 0.2.0 shared-material repair (repair_thunderdome.py) deferred "transparent"/"_trans" materials, so
`road_tracks_dry_03_blend_2_trans` (the grey paths) and `sand_desert_02_bm_transparent` kept
`composite_fallback_albedo`. Their textures come from the RSX exports (build_native_props.rsx_index), exported
from the retail paks when missing, and are converted at <= TEXTURE_CAP (source format, albedo sRGB). Only the
patched materials' JSON is rewritten; every other asset of the 0.2.0 manifest is linked unchanged, and the rebuilt
`thunderdome_world.rpak` replaces the package's.

  python patch_world_materials.py thunderdome <package>
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from new_arena_ports import ROOT, folder
import build_native_props as props

SOURCE = ROOT/'output/thunderdome-repair-2026-10-29/materials'
TEXTURE_CAP = 1024
FALLBACK = 'composite_fallback_albedo.rpak'
REPORT = 'world-material-patch.json'
DECAL_TEMPLATE = 'slum_grime_decal_01'  # a 0.2.0 world-alpha decal


def link_tree(src, dst):
    for p in src.rglob('*'):
        t = dst/p.relative_to(src)
        if p.is_dir():
            t.mkdir(parents=True, exist_ok=True)
        elif not t.exists():
            t.parent.mkdir(parents=True, exist_ok=True); os.link(p, t)


def alpha_decals(ident, mapping, assets, files):
    """Opaque world overlays whose albedo alpha carries their shape (stain_ground_01: 98.7% of texels below 128, a
    puddle drawn as a dark square) become world-alpha decals: the flags, uber and depth materials of the 0.2.0
    decal DECAL_TEMPLATE, plus an opacity texture (slot 13) from the albedo alpha."""
    import numpy as np
    from PIL import Image
    from restore_banner_display_textures import image_dds
    template = assets/f'material/{mapping["materials"][DECAL_TEMPLATE]["name"]}_wld.json'
    decal = json.loads(template.read_text()); keys = ('shaderSet', 'glueFlags', 'glueFlags2', 'blendStates', 'blendStateMask',
                                                      'depthStencilFlags', 'rasterizerFlags', '$depthShadowMaterial',
                                                      '$depthPrepassMaterial', '$depthVSMMaterial')
    changed = {}
    for name, r in mapping['materials'].items():
        j = assets/f'material/{r["name"]}_wld.json'
        if not props.OVERLAY.search(name.lower()) or not j.exists():
            continue
        spec = json.loads(j.read_text())
        if spec['shaderSet'] == decal['shaderSet'] or '13' in spec['$textures'] or '0' not in spec['$textures']:
            continue
        albedo = image_dds((assets/spec['$textures']['0']).with_suffix('.dds')).convert('RGBA')
        alpha = np.asarray(albedo)[..., 3]
        if (alpha < 128).mean() <= props.CUTOUT_FRACTION:
            continue
        path = f'texture/{ident}/patch_{name}_opacity.rpak'; dest = (assets/path).with_suffix('.dds')
        dest.parent.mkdir(parents=True, exist_ok=True); png = dest.with_suffix('.png'); Image.fromarray(alpha).save(png)
        subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', '0', '-f', 'BC4_UNORM', '-o', str(dest.parent), str(png)],
                       check=True, capture_output=True); png.unlink()
        files[path] = {'_type': 'txtr', '_path': path, '$disableStreaming': True}
        spec.update({k: decal[k] for k in keys if k in decal}); spec['$textures']['13'] = path
        j.unlink(); j.write_text(json.dumps(spec, indent=2))
        uber = j.with_suffix('.uber'); uber.unlink(); shutil.copy2(template.with_suffix('.uber'), uber)
        changed[name] = dict(transparent_fraction=round(float((alpha < 128).mean()), 3), opacity=path)
    return changed


def patch(ident, package):
    package = Path(package)
    if (package/REPORT).exists():
        raise ValueError('World materials already patched: '+str(package/REPORT))
    mapping = json.loads((SOURCE/'mapping.json').read_text()); manifest = json.loads((SOURCE/'build.json').read_text())
    work = folder(ident)/'world-material-patch'; assets = work/'assets'
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    link_tree(Path(manifest['assetsDir']), assets)
    # Overlay layers only: other fallback materials (exhaust glow, objective borders) were deferred on purpose
    # because they need an emission or coverage shader.
    targets = sorted(n for n, r in mapping['materials'].items()
                     if r['textures'].get('0', '').endswith(FALLBACK) and props.OVERLAY.search(n.lower()))
    props.RSX_ROOTS.append(folder(ident)/'rsx-props-export')
    exported = props.export_missing(ident, targets, mapping['materials'])
    by_guid, by_name = props.rsx_index(work)
    cap, props.TEXTURE_CAP = props.TEXTURE_CAP, TEXTURE_CAP
    files = {f['_path']: f for f in manifest['files']}; patched = {}
    try:
        for name in targets:
            rsx = by_name.get(name) or by_name.get(props.variant(name, by_name) or '')
            if not rsx:
                continue
            textures = {}
            for slot, semantic, src in rsx:
                path = f'texture/{ident}/patch_{name}_{semantic}.rpak'; dest = (assets/path).with_suffix('.dds')
                props.convert(src, dest, semantic == 'albedo'); textures[slot] = path
                files[path] = {'_type': 'txtr', '_path': path, '$disableStreaming': True}
            native = mapping['materials'][name]['name']
            for suffix in ('', '_colpass'):
                j = (assets/f'material/{native}{suffix}_wld.json')
                if not j.exists():
                    continue
                spec = json.loads(j.read_text()); spec['$textures'].update(textures)
                j.unlink(); j.write_text(json.dumps(spec, indent=2))  # replace the link, not the 0.2.0 file
            patched[name] = textures
    finally:
        props.TEXTURE_CAP = cap
    decals = alpha_decals(ident, mapping, assets, files)
    # New textures first, as repair_thunderdome.py orders resident textures.
    original = {f['_path'] for f in manifest['files']}
    manifest = dict(manifest, assetsDir=str(assets), outputDir=str(work/'build'),
                    files=[f for p, f in files.items() if p not in original]+[f for p, f in files.items() if p in original])
    (work/'build.json').write_text(json.dumps(manifest, indent=2))
    run = subprocess.run([str(props.REPAK), str(work/'build.json')], capture_output=True, text=True)
    (work/'repak.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise RuntimeError(run.stdout[-3000:]+run.stderr)
    rpak = work/'build'/(manifest['name']+'.rpak'); target = package/'paks'/rpak.name
    if target.exists():
        target.unlink()
    shutil.copy2(rpak, target)
    report = dict(targets=targets, patched=patched, alpha_decals=decals, unresolved=sorted(set(targets)-set(patched)), rsx_export=exported,
                  rpak_bytes=rpak.stat().st_size)
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    patch(sys.argv[1], sys.argv[2])
