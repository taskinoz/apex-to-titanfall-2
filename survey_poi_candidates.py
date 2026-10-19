"""Bounded feasibility survey of battle royale areas Apex itself used as arenas.

Artillery (Kings Canyon), Thermal Station and The Dome (World's Edge) and
Golden Gardens (Olympus). Area centres and extents come from R5Reloaded's own
mode scripts (CTF ring/flag points and Flowstate deathmatch spawns), not
guesses. For each area:

* play box: the hull of those points plus PLAY_MARGIN horizontally (a
  playable arena footprint); backdrop box: plus BACKDROP_MARGIN (what a
  player sees past the boundary and must be cut or replaced);
* world mesh triangles (by triangle centroid) and padded native indices
  inside each box, from the source BSP;
* static placements, unique models and their triangle cost at LOD0 and at
  LOD min(3, last), from a models-only Legion export of the map RPak;
* materials and entity classes inside the play box.

Read-only with respect to the game install. Work files live on the build drive.

  python survey_poi_candidates.py extract|export|survey
"""
import collections
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
GAME = Path('D:/Games/R5Reloaded/R5R Library/LIVE')
WORK = Path('D:/Games/ApexToTitanfallWork/poi-survey')
CAPACITY = 3145728
TARGET = .95
PLAY_MARGIN = 2000.0
BACKDROP_MARGIN = 6000.0
SCRIPTS = 'platform/scripts/vscripts/gamemodes'
# Area -> (source map, points from R5R scripts: file, location label).
AREAS = {
    'artillery': ('Artillery', 'mp_rr_canyonlands_mu2', 'custom_ctf/sh_gamemode_custom_ctf.nut', 'Artillery'),
    'thermal-station': ('Thermal Station', 'mp_rr_desertlands_mu2', 'fs_tdm/sh_gamemode_fsdm.nut', 'Thermal Station'),
    'dome': ('The Dome', 'mp_rr_desertlands_mu2', 'fs_tdm/sh_gamemode_fsdm.nut', 'Dome'),
    'golden-gardens': ('Golden Gardens', 'mp_rr_olympus', 'custom_ctf/sh_gamemode_custom_ctf.nut', 'Gardens'),
}
MAPS = sorted({a[1] for a in AREAS.values()})


def points(script, label):
    """Every <x, y, z> vector in the location block that starts with "label"."""
    text = (GAME/SCRIPTS/script).read_text(encoding='utf-8', errors='replace')
    start = text.index(f'"{label}"')
    nxt = re.compile(r'^\s*"[A-Za-z][A-Za-z \']+",\s*$', re.M).search(text, start+len(label)+2)
    block = text[start:nxt.start() if nxt else start+6000]
    # Positions only: drop death-camera lines and commented-out vectors.
    block = '\n'.join(line.split('//')[0] for line in block.splitlines() if 'deathcam' not in line.lower())
    vecs = [tuple(float(v) for v in m) for m in re.findall(r'<\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*>', block)]
    # Angles and offsets share the syntax; positions have non-zero x and y beyond +-360.
    return np.asarray([v for v in vecs if abs(v[0]) > 360 and abs(v[1]) > 360])


def extract():
    from extract_map import extract as vpk_extract
    for name in MAPS:
        dest = WORK/name
        if not (dest/'maps'/(name+'.bsp')).exists():
            vpk_extract(GAME/'vpk'/('englishclient_'+name+'.bsp.pak000_dir.vpk'), dest, 'maps/*')
        print(name, len(list((dest/'maps').glob('*'))), 'files', flush=True)


def export():
    """Models only (no textures): enough for per-LOD triangle counts."""
    for name in MAPS:
        dest = WORK/name; tool = dest/'legion'; tool.mkdir(parents=True, exist_ok=True)
        for f in ('LegionPlus.exe', 'LegionPlus.cfg', 'binkawin64.dll', 'mileswin64.dll'):
            if not (tool/f).exists():
                shutil.copy2(ROOT/'tools/composite-legion'/f, tool/f)
        pak = dest/'paks'/(name+'.rpak'); pak.parent.mkdir(exist_ok=True)
        if not pak.exists():
            original = GAME/'paks/Win64'/(name+'.rpak'); flags = struct.unpack_from('<H', original.read_bytes()[:8], 6)[0]
            if flags & 0x8000:
                from decompress_rpak import decompress  # needs Python 3.14 (compression.zstd)
                decompress(original, pak, normalize=True)
            elif not flags & 0x100:
                shutil.copy2(original, pak)
            else:
                raise ValueError('Unsupported compressed RPak: '+name)
        if not pak.with_suffix('.streams.json').exists():
            from stage_rpak_streams import stage
            stage(pak, GAME/'paks/Win64')  # links the starpaks that hold model vertex data
        marker = dest/'export.json'
        if not marker.exists():
            with (dest/'export.log').open('w', encoding='utf-8') as log:
                run = subprocess.run([str(tool/'LegionPlus.exe'), '--export', str(pak), '--loadmodels', '--mdlfmt', 'rmdl'],
                                     cwd=tool, stdout=log, stderr=subprocess.STDOUT)
            if run.returncode:
                raise RuntimeError('Legion export failed: '+name)
            marker.write_text(json.dumps(dict(models=len(list((tool/'exported_files/models').glob('*/*.vg'))))))
        print(name, json.loads(marker.read_text()), flush=True)


def lods(folder):
    from audit_conversion_candidates import lod_counts
    return lod_counts(folder)


def survey():
    import bsp_tool
    from bsp_tool.branches.respawn.apex_legends import GameLump_SPRP
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    report = dict(date='2026-10-19', capacity=CAPACITY, target_fraction=TARGET, play_margin=PLAY_MARGIN,
                  backdrop_margin=BACKDROP_MARGIN, areas=[])
    loaded = {}
    for ident, (label, name, script, key) in AREAS.items():
        pts = points(script, key)
        if len(pts) < 2:
            raise ValueError('No coordinates for '+label)
        if name not in loaded:
            bsp = bsp_tool.load_bsp(str(WORK/name/'maps'/(name+'.bsp'))); g = bsp.external
            if not hasattr(g.GAME_LUMP.sprp, 'props'):
                g.GAME_LUMP.sprp = GameLump_SPRP.from_bytes(bytes(g.GAME_LUMP.sprp))
            V = np.asarray([list(v) for v in g.VERTICES], 'f4'); MI = np.asarray(list(g.MESH_INDICES), 'u4'); L = {}
            for k, lump in {0x200: 'VERTEX_LIT_BUMP', 0x400: 'VERTEX_UNLIT', 0x600: 'VERTEX_UNLIT_TS', 0: 'VERTEX_LIT_FLAT'}.items():
                try:
                    L[k] = np.asarray([x.position_index for x in getattr(g, lump)], 'u4')
                except Exception:
                    pass
            cents, mesh_id, mat = [], [], []
            for i, m in enumerate(g.MESHES):
                s = g.MATERIAL_SORTS[m.material_sort]; kind = int(m.flags) & 0x600
                if kind not in L or not m.num_triangles:
                    continue
                ix = MI[m.first_mesh_index:m.first_mesh_index+m.num_triangles*3]+s.vertex_offset
                cents.append(V[L[kind][ix]].reshape(-1, 3, 3).mean(1)); mesh_id.append(np.full(m.num_triangles, i, 'i4'))
                mat.append(np.full(m.num_triangles, s.texture_data, 'i4'))
            sp = g.GAME_LUMP.sprp
            props = [(sp.model_names[p.model_name], np.asarray(list(p.origin), 'f4'), int(p.solid_mode.value)) for p in sp.props]
            index = {f.name.lower(): f for f in (WORK/name/'legion/exported_files/models').glob('*') if f.is_dir()}
            ents = []
            for path in (WORK/name/'maps').glob(name+'*.ent'):
                for blk in re.findall(r'\{[^{}]*\}', path.read_text(encoding='latin1')):
                    m = re.search(r'"origin" "([-\d.e]+) ([-\d.e]+) ([-\d.e]+)"', blk); c = re.search(r'"classname" "([^"]+)"', blk)
                    if m and c:
                        ents.append((c.group(1), np.asarray([float(v) for v in m.groups()])))
            loaded[name] = (np.concatenate(cents), np.concatenate(mesh_id), np.concatenate(mat), props, index, g, ents)
        cents, mesh_id, mat, props, index, g, ents = loaded[name]
        lo, hi = pts.min(0), pts.max(0); row = dict(id=ident, name=label, source_map=name, script_points=len(pts),
                                                     point_bounds=[lo.round().tolist(), hi.round().tolist()])
        for scope, margin in (('play', PLAY_MARGIN), ('backdrop', BACKDROP_MARGIN)):
            blo = lo-[margin, margin, 1500]; bhi = hi+[margin, margin, 6000]
            inside = np.all((cents >= blo) & (cents <= bhi), 1)
            per_mesh = collections.Counter(mesh_id[inside].tolist())
            padded = sum(n*3+(n % 2)*3 for n in per_mesh.values())
            sel = [p for p in props if np.all((p[1] >= blo) & (p[1] <= bhi))]
            models = collections.Counter(Path(p[0]).stem.lower() for p in sel)
            t0 = t3 = 0; missing = 0
            for stem, n in models.items():
                try:
                    c = lods(index[stem]); t0 += n*c[0]; t3 += n*c[min(3, len(c)-1)]
                except (KeyError, OSError, ValueError, struct.error):
                    missing += n
            prop_indices = 3*t3
            row[scope] = dict(box=[blo.round().tolist(), bhi.round().tolist()], world_triangles=int(inside.sum()),
                              world_meshes=len(per_mesh), world_padded_indices=padded,
                              world_fraction=round(padded/CAPACITY, 4), placements=len(sel), unique_models=len(models),
                              prop_triangles_lod0=t0, prop_triangles_lod3=t3, placements_without_export=missing,
                              total_fraction_lod3=round((padded+prop_indices)/CAPACITY, 4),
                              materials=len(set(mat[inside].tolist())))
            if scope == 'play':
                row['play']['entity_classes'] = dict(collections.Counter(c for c, o in ents if np.all((o >= blo) & (o <= bhi))).most_common(15))
                row['play']['top_models_lod3'] = sorted(((m, n) for m, n in models.items()), key=lambda x: -x[1])[:12]
        report['areas'].append(row)
        p, b = row['play'], row['backdrop']
        print(f"{label:16s} play: world {p['world_fraction']*100:5.1f}%  props {p['placements']:5d} ({p['unique_models']} models, "
              f"{p['prop_triangles_lod3']:,} tris @LOD3)  total {p['total_fraction_lod3']*100:5.1f}%  | backdrop total "
              f"{b['total_fraction_lod3']*100:5.1f}%  missing-export placements {p['placements_without_export']}", flush=True)
    out = ROOT/'docs/candidates/poi-survey-2026-10-19.json'; out.write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    {'extract': extract, 'export': export, 'survey': survey}[sys.argv[1]]()
