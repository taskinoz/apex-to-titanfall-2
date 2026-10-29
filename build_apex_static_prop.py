"""Smoke test 3 (docs/candidates/static-prop-conversion-2026-10-24.md): one Apex model as a native static prop.

Apex VG geometry (read_vg_static) -> SMD/QC -> r2studiomdl (tools/r2-model-compiler-v0.5.0) -> v53 `.mdl` shipped
loose under the package's `mod/models/apex/`, plus a RePak `fix`/`skn` material pair per Apex material. The
materials clone a retail common.rpak model material (header flags, uber constants, depth materials) and keep its
shader set by GUID: common.rpak is always loaded, so no shader is embedded. The textures are the ones the map's
world RPak already built. add_stock_props.py then places the model beside the stock props.

  python build_apex_static_prop.py thermal-station farmland_crate_md_80x64x72_03
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import ROOT, folder
from read_vg_static import load
from prepare_new_arena_scene import asset_index
from extract_native_material import NativePak

COMPILER = ROOT/'tools/r2-model-compiler-v0.5.0/r2studiomdl.exe'
REPAK = ROOT/'tools/repak/RePak.exe'
# Retail model material whose flags, uber constants and shader sets the clones keep (both fix and skn exist).
TEMPLATE = 'models\\containers\\can_soda'
SEMANTICS = ('albedo', 'normal', 'gloss', 'spec')
NAMESPACE = 'models/apex'


def pakguid(path):
    return int(subprocess.run([str(REPAK), '-pakguid', path], capture_output=True, text=True, check=True).stdout.strip(), 16)


def smd(path, sections, slots, names, namespace=NAMESPACE):
    """studiomdl flips V and (for $staticprop) yaws +90 degrees: write the inverse of each so the compiled vertices
    equal the Apex ones. VG triangles are already counter-clockwise about their normals, as SMD expects."""
    lines = ['version 1', 'nodes', '0 "static_prop" -1', 'end', 'skeleton', 'time 0', '0 0 0 0 0 0 0', 'end', 'triangles']
    for s, slot in zip(sections, slots):
        t = np.asarray(s, 'f8').reshape(-1, 3, 12)
        for tri in t:
            lines.append(f'{namespace}/{names[slot]}')
            for v in tri:
                (x, y, z), (nx, ny, nz), (u, w) = v[:3], v[3:6], v[6:8]
                lines.append(f'0 {y:.6f} {-x:.6f} {z:.6f} {ny:.6f} {-nx:.6f} {nz:.6f} {u:.6f} {1-w:.6f} 1 0 1')
    lines.append('end')
    path.write_text('\n'.join(lines)+'\n')


def hull_smd(path, sections):
    """One convex piece: the hull of the render vertices. The raw render mesh (open shells, coincident faces) is
    rejected by the compiler as degenerate at PHY precision."""
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from scipy.spatial import ConvexHull
    p = np.unique(np.round(np.concatenate([np.asarray(s, 'f8').reshape(-1, 12)[:, :3] for s in sections if s]), 2), axis=0)
    h = ConvexHull(p); tris = []
    for (a, b, c), eq in zip(h.simplices, h.equations):
        if np.dot(np.cross(p[b]-p[a], p[c]-p[a]), eq[:3]) < 0:
            b, c = c, b  # outward counter-clockwise, as an SMD triangle
        tris.append(('phys', [(p[i], eq[:3]) for i in (a, b, c)]))
    lines = ['version 1', 'nodes', '0 "static_prop" -1', 'end', 'skeleton', 'time 0', '0 0 0 0 0 0 0', 'end', 'triangles']
    for name, corners in tris:
        lines.append(name)
        for (x, y, z), (nx, ny, nz) in corners:
            lines.append(f'0 {y:.6f} {-x:.6f} {z:.6f} {ny:.6f} {-nx:.6f} {nz:.6f} 0 0 1 0 1')
    lines.append('end')
    path.write_text('\n'.join(lines)+'\n')
    return len(h.vertices), len(tris)


def materials(ident, names, work):
    """RePak manifest: the map's built textures plus a fix and skn clone of TEMPLATE per Apex material."""
    slug = ident.replace('-', '_'); built = folder(ident)/'materials/assets/texture'/slug
    pak = NativePak(ROOT/'inputs/tf2-rpak-work/common.raw.rpak')
    assets = work/'assets'; files = []
    templates = {}
    for a in pak.assets:
        if a['type'] == 'matl' and a['version'] == 12:
            at = pak.address(a['header'])
            if pak.string(struct.unpack_from('<2I', pak.data, at+24)) == TEMPLATE:
                templates[a['guid']] = pak.material(a)
    for kind in ('fix', 'skn'):
        if pakguid(f'material/{TEMPLATE.replace(chr(92), "/")}_{kind}.rpak') not in templates:
            raise ValueError(f'{TEMPLATE} has no {kind} material in common.rpak')
    for name in names:
        textures = {}
        for slot, semantic in enumerate(SEMANTICS):
            source = built/f'{name}_{semantic}.dds'
            if source.exists():
                path = f'texture/{NAMESPACE}/{name}_{semantic}.rpak'; dest = (assets/path).with_suffix('.dds')
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest)
                files.append({'_type': 'txtr', '_path': path, '$disableStreaming': True}); textures[str(slot)] = path
        if '0' not in textures:
            raise ValueError(f'No built albedo for {name}')
        for kind in ('fix', 'skn'):
            spec, uber = templates[pakguid(f'material/{TEMPLATE.replace(chr(92), "/")}_{kind}.rpak')]
            spec = dict(spec, name=f'{NAMESPACE}/{name}', shaderType=kind, blendStates=spec['blendStates']+['0x0']*4, surfaceProp='plastic', **{'$textures': textures,
                        '$colpassMaterial': '0x0'})
            path = f'material/{NAMESPACE}/{name}_{kind}.json'; target = assets/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(spec, indent=2)); target.with_suffix('.uber').write_bytes(uber)
            files.append({'_type': 'matl', '_path': path.removesuffix('.json')+'.rpak'})
    manifest = dict(version=7, name=slug+'_props', keepDevOnly=True, assetsDir=str(assets), outputDir=str(work/'build'),
                    compressLevel=0, hasDynamicLibrary=False, files=files)
    (work/'build.json').write_text(json.dumps(manifest, indent=2))
    run = subprocess.run([str(REPAK), str(work/'build.json')], capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(run.stdout+run.stderr)
    return work/'build'/(slug+'_props.rpak')


def build(ident, model):
    work = folder(ident)/'apex-props'/model; shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    sections, slots, skins = load(asset_index(ident)[model], 0, with_colors=True)
    names = skins[0]; used = sorted({names[s] for s, sec in zip(slots, sections) if sec})
    smd(work/'body.smd', sections, slots, names)
    hull = hull_smd(work/'phys.smd', sections)
    target = f'apex/{model}.mdl'
    (work/'model.qc').write_text('\n'.join([
        f'$modelname "{target}"', '$cdmaterials ""', '$body "body" "body.smd"', '$staticprop',
        '$surfaceprop "plastic"', '$sequence "idle" "body.smd"',
        '$collisionmodel "phys.smd" { $mass 100 }', '']))
    out = work/'models'/target; out.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run([str(COMPILER), '-o', str(out), str(work/'model.qc')], capture_output=True, text=True)
    (work/'compile.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise RuntimeError(run.stdout+run.stderr)
    rpak = materials(ident, used, work)
    a = np.concatenate([np.asarray(s, 'f4').reshape(-1, 12) for s in sections if s])
    report = dict(model=model, collision_hull=dict(vertices=hull[0], triangles=hull[1]), mdl=str(out), mdl_path='models/'+target, bytes=out.stat().st_size, rpak=str(rpak),
                  materials=[f'{NAMESPACE}/{n}' for n in used], triangles=len(a)//3,
                  apex_bounds=[a[:, :3].min(0).tolist(), a[:, :3].max(0).tolist()])
    (work/'build.json.report').write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
