"""How much of World's Edge is visible at once: can culling alone fit the Titanfall 2 world index cap?

Titanfall 2 stops world submission at 3,145,728 indices per frame (audit_world_draw_budget.py). Whole battle
royale maps are 2-2.6x that in brush triangles alone, so a full port needs per-frame culling to bring what is
submitted under the cap. This measures, from worst-case viewpoints, what the best culling could submit.

scene:  every World's Edge world mesh (source BSP, tools materials excluded) and every static prop placement
        (visibility geometry at its last non-empty LOD) as triangles.bin; one culling unit per world mesh or placement.
views:  viewpoints from R5Reloaded's World's Edge deathmatch locations: each location's eye height, the roofs
        around it (97th percentile of up-facing surfaces within 1200 units) and the highest up-facing surfaces
        of the playable area (4096-unit cells inside the locations' hull).
rays:   tools/visibility_rays.exe views: RAYS first-hit rays over the sphere per viewpoint.
report: per viewpoint, the worst of 24 frames (12 yaws x level/-20 pitch, Titanfall fov 90 at 16:9), in indices:
        perfect   units (world mesh / prop placement) with any visible triangle: a lower bound for unit-granular
                  culling (cells, portals and occlusion queries cannot beat it);
        triangles only the triangles actually hit: lower bound for any culling at all;
        frustum   every unit in the frame, no occlusion: what frustum culling alone submits;
        props are costed at their authored LOD for distance (VG switch distances read as metres) - what a real
        static-prop path would draw - and separately at the fixed occluder LOD, as this project bakes them.
Rays miss sub-pixel geometry (RAYS=6M is ~0.08 degrees), so perfect/triangles are slightly low.

  python measure_br_visibility.py scene|views|rays|report
"""
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tools/bsp_tool')); sys.path.insert(0, str(ROOT/'tools/lighting-python'))
MAP = 'mp_rr_desertlands_mu2'
SURVEY = Path('D:/Games/ApexToTitanfallWork/poi-survey')/MAP
WORK = Path('D:/Games/ApexToTitanfallWork/br-visibility')/MAP
FSDM = Path('D:/Games/R5Reloaded/R5R Library/LIVE/platform/scripts/vscripts/gamemodes/fs_tdm/sh_gamemode_fsdm.nut')
CAPACITY = 3145728
RAYS = 6_000_000
EYE = 64.
VANTAGE_CEILING = 10000.
METRE = 39.37
HFOV, VFOV = np.radians(106.26), np.radians(73.74)  # Titanfall fov 90 (4:3) at 16:9
YAWS, PITCHES = range(0, 360, 30), (0., -20.)


def foliage(model):
    return any(w in model.lower() for w in ('foliage/', 'grass', 'flower', 'bush', 'plant', 'tree'))


def padded(n):
    return n*3+(n % 2)*3


def lod_table(folder):
    d = (folder/(folder.name+'.vg')).read_bytes(); h = struct.unpack_from('<18Q', d, 16); rows = []
    for i in range(h[13]):
        first, count, dist = struct.unpack_from('<2hf', d, h[12]+i*8)
        rows.append((dist*METRE, sum(struct.unpack_from('<I', d, h[2]+j*72+36)[0]//3 for j in range(first, first+count))))
    return rows


def scene():
    import bsp_tool
    from bsp_tool.branches.respawn.apex_legends import GameLump_SPRP
    from read_vg_static import load
    from stage_prop_geometry import rotation
    WORK.mkdir(parents=True, exist_ok=True)
    g = bsp_tool.load_bsp(str(SURVEY/'maps'/(MAP+'.bsp'))).external
    if not hasattr(g.GAME_LUMP.sprp, 'props'):
        g.GAME_LUMP.sprp = GameLump_SPRP.from_bytes(bytes(g.GAME_LUMP.sprp))
    V = np.asarray([list(v) for v in g.VERTICES], 'f4'); MI = np.asarray(list(g.MESH_INDICES), 'u4'); L = {}
    for k, lump in {0x200: 'VERTEX_LIT_BUMP', 0x400: 'VERTEX_UNLIT', 0x600: 'VERTEX_UNLIT_TS', 0: 'VERTEX_LIT_FLAT'}.items():
        try:
            L[k] = np.asarray([x.position_index for x in getattr(g, lump)], 'u4')
        except Exception:
            pass
    tris, unit, units = [], [], []
    for i, m in enumerate(g.MESHES):
        s = g.MATERIAL_SORTS[m.material_sort]; kind = int(m.flags) & 0x600; name = g.texture_data_surface_name(s.texture_data)
        if kind not in L or not m.num_triangles or name.lower().startswith('tools/'):
            continue
        t = V[L[kind][MI[m.first_mesh_index:m.first_mesh_index+m.num_triangles*3]+s.vertex_offset]].reshape(-1, 3, 3)
        tris.append(t); unit.append(np.full(len(t), len(units), 'i4'))
        units.append(dict(kind='world', triangles=len(t), cost=padded(len(t)), centre=t.reshape(-1, 3).mean(0).tolist(), material=name))
    world = len(units)
    sp = g.GAME_LUMP.sprp
    index = {f.name.lower(): f for f in (SURVEY/'legion/exported_files/models').iterdir() if f.is_dir()}
    cache, missing = {}, 0
    for k, p in enumerate(sp.props):
        model = sp.model_names[p.model_name]; stem = Path(model).stem.lower()
        if stem not in cache:
            try:
                table = lod_table(index[stem]); filled = [i for i, (_, n) in enumerate(table) if n] or [0]
                # Visibility geometry only (costs keep every LOD): the last non-empty LOD. All props at LOD0 are
                # 405M triangles; even their last LODs are 49M, the most this build machine can raycast.
                lod = filled[-1]
                sec = [np.asarray(s, 'f4').reshape(len(s), 3, -1)[:, :, :3] for s in load(index[stem], lod)[0] if len(s)]
                cache[stem] = (table, lod, np.concatenate(sec) if sec else np.empty((0, 3, 3), 'f4'), foliage(model))
            except (KeyError, OSError, ValueError, struct.error, IndexError):
                cache[stem] = None
        if cache[stem] is None:
            missing += 1; continue
        table, lod, geo, leaf = cache[stem]
        origin = np.asarray(list(p.origin), 'f4'); m = np.asarray(rotation([p.angles.y, p.angles.z, p.angles.x]), 'f4')
        t = geo @ m.T*p.scale+origin
        if len(t):
            tris.append(t.astype('f4')); unit.append(np.full(len(t), len(units), 'i4'))
        units.append(dict(kind='prop', model=stem, centre=origin.tolist(), lods=[[round(d), n] for d, n in table],
                          occluder_lod=lod, foliage=bool(leaf)))
        if k % 5000 == 0:
            print('placements', k, '/', len(sp.props), flush=True)
    t = np.concatenate(tris); t.tofile(WORK/'triangles.bin'); np.save(WORK/'unit.npy', np.concatenate(unit))
    (WORK/'units.json').write_text(json.dumps(units))
    info = dict(world_meshes=world, world_triangles=int(sum(u['triangles'] for u in units[:world])),
                world_indices=int(sum(u['cost'] for u in units[:world])), placements=len(units)-world,
                placements_without_export=missing, scene_triangles=len(t))
    (WORK/'scene.json').write_text(json.dumps(info, indent=2)); print(info, flush=True)


def locations():
    lines = FSDM.read_text(encoding='utf-8', errors='replace').splitlines()
    start = next(i for i, l in enumerate(lines) if 'eMaps.mp_rr_desertlands_64k_x_64k:' in l)
    end = next((i for i in range(start+3, len(lines)) if re.search(r'case eMaps\.|default\s*:', lines[i]) and 'desertlands' not in lines[i]), len(lines))
    text = '\n'.join(l.split('//')[0] for l in lines[start:end])
    out = {}
    for m in re.finditer(r'NewLocationSettings\(\s*"([^"]+)"\s*,\s*\[(.*?)\]', text, re.S):
        pts = [tuple(map(float, v)) for v in re.findall(r'NewLocPair\(\s*<\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*>', m.group(2))]
        if pts and m.group(1) != 'Movement Gym' and ' By ' not in m.group(1):  # community prop builds, not World's Edge
            out.setdefault(m.group(1), []).extend(pts)
    return {k: np.asarray(v) for k, v in out.items()}


def views():
    from scipy.spatial import ConvexHull, Delaunay
    t = np.fromfile(WORK/'triangles.bin', 'f4').reshape(-1, 3, 3)
    n = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]); up = n[:, 2] > .7*np.linalg.norm(n, axis=1)
    tops = t[up].mean(1); points = []
    locs = locations(); centres = np.asarray([v.mean(0) for v in locs.values()])
    for name, pts in locs.items():
        c = pts.mean(0); points.append(dict(name=name, kind='ground', eye=[float(c[0]), float(c[1]), float(pts[:, 2].mean())+EYE]))
        near = tops[np.hypot(*(tops[:, :2]-c[:2]).T) < 1200]
        if len(near):
            k = np.argsort(near[:, 2])[int(.97*(len(near)-1))]
            points.append(dict(name=name, kind='roof', eye=[float(near[k, 0]), float(near[k, 1]), float(near[k, 2])+EYE]))
    hull = Delaunay(centres[:, :2][ConvexHull(centres[:, :2]).vertices])
    inside = tops[hull.find_simplex(tops[:, :2]) >= 0]; cell = np.floor(inside[:, :2]/4096).astype(int); best = {}
    for p, c in zip(inside, map(tuple, cell)):
        if c not in best or p[2] > best[c][2]:
            best[c] = p
    chosen = []
    for p in sorted(best.values(), key=lambda p: -p[2]):
        # Below the sky geometry (space elevator top and dome reach 40000) and 3000 apart.
        if p[2] < VANTAGE_CEILING and all(np.hypot(*(p[:2]-q[:2])) > 3000 for q in chosen):
            chosen.append(p)
    for p in chosen[:8]:
        points.append(dict(name=f'vantage {p[0]:.0f},{p[1]:.0f}', kind='vantage', eye=[float(p[0]), float(p[1]), float(p[2])+EYE]))
    (WORK/'views.json').write_text(json.dumps(points, indent=2))
    np.asarray([p['eye'] for p in points], 'f4').tofile(WORK/'points.bin'); print(len(locs), 'locations', len(points), 'viewpoints', flush=True)


def rays():
    out = WORK/'hits'; out.mkdir(exist_ok=True)
    subprocess.run([str(ROOT/'tools/visibility_rays.exe'), 'views', str(WORK/'triangles.bin'), str(WORK/'points.bin'), str(RAYS), str(out)], check=True)


def frames():
    for yaw in YAWS:
        for pitch in PITCHES:
            y, p = np.radians(yaw), np.radians(pitch)
            f = np.array([np.cos(p)*np.cos(y), np.cos(p)*np.sin(y), np.sin(p)])
            r = np.array([np.sin(y), -np.cos(y), 0.]); u = np.cross(r, f)
            yield yaw, pitch, f, r, u


def in_frame(d, f, r, u):
    z = d @ f
    return (z > 1e-6) & (np.abs(d @ r) <= np.tan(HFOV/2)*z) & (np.abs(d @ u) <= np.tan(VFOV/2)*z)


def report():
    t = np.fromfile(WORK/'triangles.bin', 'f4').reshape(-1, 3, 3); unit = np.load(WORK/'unit.npy')
    units = json.loads((WORK/'units.json').read_text()); info = json.loads((WORK/'scene.json').read_text())
    pts = json.loads((WORK/'views.json').read_text()); U = len(units)
    centre = np.asarray([u['centre'] for u in units], 'f4'); world = np.asarray([u['kind'] == 'world' for u in units])
    leaf = np.asarray([u.get('foliage', False) for u in units])
    fixed = np.asarray([u['cost'] if u['kind'] == 'world' else padded(u['lods'][u['occluder_lod']][1]) for u in units], 'f8')
    lods = [u.get('lods') for u in units]
    rows = []
    for i, p in enumerate(pts):
        eye = np.asarray(p['eye'], 'f4'); ids = np.fromfile(WORK/'hits'/f'view_{i}.bin', '<u4')
        hit_dir = t[ids].mean(1)-eye; hit_unit = unit[ids]
        dist = np.linalg.norm(centre-eye, axis=1); udir = centre-eye
        dyn = fixed.copy()  # props at authored distance LOD (a static-prop path), world fixed
        for k in np.where(~world)[0]:
            n = lods[k][0][1]
            for d, c in lods[k]:
                if dist[k] >= d:
                    n = c
            dyn[k] = padded(n)
        worst = None
        for yaw, pitch, f, r, u in frames():
            seen_t = in_frame(hit_dir, f, r, u); seen = np.zeros(U, bool); seen[hit_unit[seen_t]] = True
            frame = in_frame(udir, f, r, u)
            row = dict(yaw=yaw, pitch=pitch,
                       world_perfect=float(fixed[seen & world].sum()), world_frustum=float(fixed[frame & world].sum()),
                       props_perfect_lod=float(dyn[seen & ~world].sum()), props_perfect_baked=float(fixed[seen & ~world].sum()),
                       props_frustum_lod=float(dyn[frame & ~world].sum()), props_frustum_baked=float(fixed[frame & ~world].sum()),
                       foliage_perfect_lod=float(dyn[seen & leaf].sum()),
                       triangles=float(3*seen_t.sum()), units_seen=int(seen.sum()))
            row['total_perfect_baked'] = row['world_perfect']+row['props_perfect_baked']
            if worst is None or row['total_perfect_baked'] > worst['total_perfect_baked']:
                worst = row
        rows.append(dict(p, worst=worst)); w = worst
        print(f"{p['kind']:7s} {p['name'][:28]:28s} yaw {w['yaw']:3d} pitch {w['pitch']:+3.0f}  world perfect {w['world_perfect']/CAPACITY:6.1%} "
              f"frustum {w['world_frustum']/CAPACITY:6.1%} | +props perfect baked {w['total_perfect_baked']/CAPACITY:6.1%} "
              f"(static-prop LOD {w['props_perfect_lod']/CAPACITY:5.1%}) | triangles-only {w['triangles']/CAPACITY:5.1%}", flush=True)
    (WORK/'report.json').write_text(json.dumps(dict(capacity=CAPACITY, rays=RAYS, scene=info, views=rows), indent=2))


if __name__ == '__main__':
    {'scene': scene, 'views': views, 'rays': rays, 'report': report}[sys.argv[1]]()
