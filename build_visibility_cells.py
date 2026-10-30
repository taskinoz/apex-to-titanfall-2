"""Split a converted map's single all-visible camera cell into cells that each draw only what can be seen from them.

The conversions draw every world mesh and static prop from one native cell (repair_camera_visibility.py). Native
Titanfall 2 culls by camera cell: the engine finds the camera's cell through the cell BSP (0x6A; plane or -1 leaf,
child 0 the front side, dot >= d) and draws the objects of that cell's access tree (the first len(CELLS) nodes of
0x77 are the per-cell roots, MRVN-Radiant's retail survey), plus whatever its portals reach. Here there are no
portals (the format the single-cell builds already use without problems): each cell's tree holds its potentially
visible set, so the large blockers in an arena hide what is behind them.

* scene: world render triangles (analyse_visibility.render_triangles) and every static prop placement's triangles
  (sprp v13, matched to its source placement by origin; the first LOD with <= PROP_TRIANGLES triangles). See-through
  surfaces (analyse_visibility.see_through, overlay/cutout/foliage props) never block a ray but count as seen.
* viewpoints: analyse_visibility's reachability flood from the spawn points over world and solid-prop floors, at
  VIEW_GRID spacing and HEIGHTS above it (standing, jump, wallrun).
* rays: tools/visibility_rays.exe tiles: RAYS first-hit rays per viewpoint, recorded per TILE x TILE column.
* cells: a kd split of the tile grid. A cell's set is everything seen from its tiles and the tiles around them,
  every object within NEAR of it, and ALWAYS (transparent meshes, props without triangles). Splits are taken
  greedily by the drop in the viewpoint-weighted draw count per added reference, while the references fit the
  uint16 index space (REFERENCE_BUDGET). Outside the tile grid, and above a cell's highest viewpoint plus
  ZMARGIN (spectator and intro cameras), the camera is in a final cell that draws everything.

Object bounds keep the conservative camera-domain widening of the single-cell builds. Shadow (CSM) trees and
collision are not changed.

  python build_visibility_cells.py thunderdome <package>
"""
import functools
import json
import math
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from stage_prop_geometry import rotation
from read_vg_static import load, levels
import analyse_visibility as av
from add_stock_props import sprp
from build_native_props import selection, asset_index, SKIP, OVERLAY
from prepare_new_arena_scene import foliage

PROP_TRIANGLES = 1500
SEE_THROUGH = re.compile(r'glass|fence|grate|holes|chain|wire|leaf|leaves|cutout|holo|_trans|transparent')
VIEW_GRID, VIEW_Z = 128, 96
HEIGHTS = (64, 250, 450)
RAYS = 6000
TILE = 512
NEAR = 512.
ZMARGIN = 512.
REFERENCE_BUDGET = 65000
LEAF = 255
REPORT = 'visibility-cells.json'
NODE = '<3f2BH3f2H'


@functools.lru_cache(None)
def model_triangles(ident, stem):
    """Model-space triangles of the first LOD with <= PROP_TRIANGLES triangles, and which are see-through."""
    path = asset_index(ident)[stem]
    for lod in range(levels(path)):
        sections, slots, skins = load(path, lod, with_colors=True)
        tris, clear = [], []
        for s, k in zip(sections, slots):
            name = skins[0][k].lower()
            if len(s) and not any(x in name for x in SKIP):
                t = np.asarray(s, 'f4').reshape(-1, 3, 12)[:, :, :3]
                tris.append(t); clear.append(np.full(len(t), bool(SEE_THROUGH.search(name) or OVERLAY.search(name))))
        if sum(map(len, tris)) <= PROP_TRIANGLES or lod == levels(path)-1:
            return (np.concatenate(tris).astype('f8'), np.concatenate(clear)) if tris else (np.empty((0, 3, 3)), np.empty(0, bool))


def placements(ident, bsp):
    """sprp placements with their source placement (same float32 origin, model stem a prefix of the compiled name)."""
    names, recs = sprp(bsp); source = {}
    for p in selection(ident, True):
        source.setdefault(tuple(np.float32(p['origin']).round(2)), []).append(p)
    out = []
    for r in recs:
        origin = struct.unpack_from('<3f', r, 0); mdl = Path(names[struct.unpack_from('<H', r, 28)[0]]).stem
        match = [p for p in source.get(tuple(np.float32(origin).round(2)), []) if mdl.startswith(Path(p['model']).stem.lower())]
        out.append(dict(origin=origin, angles=struct.unpack_from('<3f', r, 12), scale=struct.unpack_from('<f', r, 24)[0], mdl=mdl,
                        source=max(match, key=lambda p: len(Path(p['model']).stem)) if match else None))
    return out


def scene(ident, bsp):
    tris, mesh_of, names = av.render_triangles(bsp); meshes = len(names)
    see = av.see_through(ident, names)
    clear = np.asarray([see[names[m]] or bool(OVERLAY.search(names[m].lower())) for m in mesh_of])
    normals = [av.render_triangles.normals]
    solid = [np.asarray([not any(w in n.lower() for w in ('water', 'sky')) for n in names])[mesh_of]]
    all_tris, units, clears = [tris.astype('f4')], [mesh_of.astype('u4')], [clear]
    props = placements(ident, bsp); radius = np.zeros(len(props)); missing = []
    for k, p in enumerate(props):
        src = p['source']; stem = Path(src['model']).stem.lower() if src else None
        if not src or stem not in asset_index(ident):
            missing.append(k); continue
        t, c = model_triangles(ident, stem)
        if not len(t):
            missing.append(k); continue
        t = t @ np.asarray(rotation(p['angles'])).T * p['scale'] + p['origin']
        radius[k] = np.linalg.norm(t.reshape(-1, 3)-p['origin'], axis=1).max()
        n = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]); n[:, 2] = np.abs(n[:, 2])  # either side of a prop can be stood on
        plant = foliage(src['model'])
        all_tris.append(t.astype('f4')); units.append(np.full(len(t), meshes+k, 'u4')); clears.append(c | plant); normals.append(n)
        solid.append(np.full(len(t), not plant or 'building' in src['model']))
    av.render_triangles.normals = np.concatenate(normals)
    return dict(tris=np.concatenate(all_tris), units=np.concatenate(units), clear=np.concatenate(clears),
                walkable=np.concatenate(solid), meshes=meshes, props=props, radius=radius, missing=missing)


def viewpoints(ident, s):
    seeds = [[float(v) for v in e['origin'].split()] for e in json.loads((folder(ident)/'scene.json').read_text())['source_entities']
             if e.get('classname', '').startswith('info_spawnpoint_human')]
    seeds = [np.add(o, CONFIG[ident]['offset']) for o in seeds]
    _, reach = av.viewpoints(ident, s['tris'], s['walkable'], seeds)
    # Cameras outside the play bounds use the all-visible cell, so only the bounds and the ring of tiles the
    # dilation reads around them are traced (72% of Thunderdome's reachable points are on the stadium ring).
    b = np.asarray(CONFIG[ident]['bounds'], 'f8')
    reach = reach[np.all((reach[:, :2] >= b[0][:2]-2*TILE) & (reach[:, :2] <= b[1][:2]+2*TILE), axis=1)]
    g = np.unique(np.c_[np.floor(reach[:, :2]/VIEW_GRID), np.floor(reach[:, 2]/VIEW_Z)], axis=0, return_index=True)[1]
    return np.concatenate([reach[g]+[0, 0, h] for h in HEIGHTS]).astype('f4'), len(seeds), len(reach)


def unit_boxes(l, s):
    """Geometric xy bounds per unit: mesh bounds (0x51), props as origin +- radius."""
    b = np.frombuffer(l[0x51], '<f4').reshape(-1, 8)[:s['meshes']]
    lo, hi = b[:, :3]-b[:, 4:7], b[:, :3]+b[:, 4:7]
    o = np.asarray([p['origin'] for p in s['props']]).reshape(-1, 3); r = s['radius'][:, None]
    return np.r_[lo, o-r], np.r_[hi, o+r]


def dilate(seen):
    """The tiles around a tile count as part of it: a camera near its border sees what they see."""
    X, Y, _ = seen.shape; dil = seen.copy()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            dil[max(dx, 0):X+min(dx, 0), max(dy, 0):Y+min(dy, 0)] |= seen[max(-dx, 0):X+min(-dx, 0), max(-dy, 0):Y+min(-dy, 0)]
    return dil


def plan(dil, weight, lo, hi, grid, always):
    """Greedy kd split of the tile grid. dil: [X][Y][U] bool (dilated), weight: viewpoints per tile."""
    X, Y, U = dil.shape
    ux0, ux1 = (lo[:, 0]-grid[0]-NEAR)/TILE, (hi[:, 0]-grid[0]+NEAR)/TILE  # unit bounds +- NEAR in tile units
    uy0, uy1 = (lo[:, 1]-grid[1]-NEAR)/TILE, (hi[:, 1]-grid[1]+NEAR)/TILE

    def members(r):
        x0, x1, y0, y1 = r
        near = (ux1 > x0) & (ux0 < x1) & (uy1 > y0) & (uy0 < y1)
        return dil[x0:x1, y0:y1].any((0, 1)) | near | always

    def best_split(r):
        x0, x1, y0, y1 = r; here = int(members(r).sum()); options = []
        for axis in (0, 1):
            a, b = (x0, x1) if axis == 0 else (y0, y1)
            for cut in range(a+1, b):
                ra = (x0, cut, y0, y1) if axis == 0 else (x0, x1, y0, cut); rb = (cut, x1, y0, y1) if axis == 0 else (x0, x1, cut, y1)
                options.append((ra, rb))
        best = None
        for ra, rb in options:
            ma, mb = members(ra), members(rb)
            wa, wb = weight[ra[0]:ra[1], ra[2]:ra[3]].sum(), weight[rb[0]:rb[1], rb[2]:rb[3]].sum()
            if not wa or not wb:
                continue
            benefit = (wa+wb)*here-(wa*ma.sum()+wb*mb.sum())  # draws saved, summed over viewpoints
            cost = int(ma.sum()+mb.sum()-here)
            score = benefit/max(cost, 1)
            if best is None or score > best[0]:
                best = (score, ra, rb, cost, benefit)
        return best

    root = (0, X, 0, Y); leaves = {root: None}; tree = {}; total = int(members(root).sum())+U  # + the all-visible cell
    while True:
        for r in leaves:
            if leaves[r] is None:
                leaves[r] = best_split(r) or (0,)
        r = max((r for r in leaves if len(leaves[r]) > 1 and total+leaves[r][3] <= REFERENCE_BUDGET), key=lambda r: leaves[r][0], default=None)
        if r is None:
            break
        _, ra, rb, cost, _ = leaves.pop(r); tree[r] = (ra, rb); leaves[ra] = leaves[rb] = None; total += cost
    return tree, {r: members(r) for r in leaves}, total


def encode(tree, sets, points, tile_of, grid, X, Y, planes, refs_of, boxes):
    """Cell BSP, cells, access trees. Cells: kd leaves in order, then the all-visible cell."""
    cells = list(sets); full = len(cells); bsp = []; plane_ids = {}

    def plane(axis, d):
        if (axis, d) not in plane_ids:
            n = [0., 0., 0.]; n[axis] = 1.; plane_ids[(axis, d)] = len(planes)//16; planes.extend(struct.pack('<4f', *n, d))
        return plane_ids[(axis, d)]

    def node(axis, d, front, back):
        # front: dot >= d (child 0), back: child 1; children are consecutive records
        at = len(bsp); bsp.append(None); first = len(bsp); bsp.extend([None, None])
        bsp[at] = (plane(axis, d), first); front(first); back(first+1)

    def leaf(cell):
        return lambda at: bsp.__setitem__(at, (-1, cell))

    tops = {}
    for c, r in enumerate(cells):
        inside = (tile_of[:, 0] >= r[0]) & (tile_of[:, 0] < r[1]) & (tile_of[:, 1] >= r[2]) & (tile_of[:, 1] < r[3])
        tops[r] = float(points[inside, 2].max())+ZMARGIN if inside.any() else None

    def kd(r):
        def fill(at):
            if r in tree:
                ra, rb = tree[r]; axis = 0 if ra[1] != r[1] else 1
                cut = grid[axis]+TILE*(ra[1] if axis == 0 else ra[3])
                bsp[at] = None; first = len(bsp); bsp.extend([None, None]); bsp[at] = (plane(axis, float(cut)), first)
                kd(rb)(first); kd(ra)(first+1)
            elif tops[r] is None:
                leaf(full)(at)
            else:
                first = len(bsp); bsp.extend([None, None]); bsp[at] = (plane(2, tops[r]), first)
                leaf(full)(first); leaf(cells.index(r))(first+1)
        return fill

    x0, y0 = grid; x1, y1 = x0+TILE*X, y0+TILE*Y
    bsp.append(None)
    # x >= x0, x < x1, y >= y0, y < y1 select the tile grid; anywhere else is the all-visible cell.
    def inside_x1(at):
        first = len(bsp); bsp.extend([None, None]); bsp[at] = (plane(0, float(x1)), first); leaf(full)(first); inside_y0(first+1)
    def inside_y0(at):
        first = len(bsp); bsp.extend([None, None]); bsp[at] = (plane(1, float(y0)), first); inside_y1(first); leaf(full)(first+1)
    def inside_y1(at):
        first = len(bsp); bsp.extend([None, None]); bsp[at] = (plane(1, float(y1)), first); leaf(full)(first); kd((0, X, 0, Y))(first+1)
    first = len(bsp); bsp.extend([None, None]); bsp[0] = (plane(0, float(x0)), first); inside_x1(first); leaf(full)(first+1)

    members = [np.flatnonzero(sets[r]) for r in cells]+[np.arange(len(refs_of))]
    nodes, refs, objects = [None]*len(members), [], []
    for c, m in enumerate(members):
        ids = [refs_of[u] for u in m]; start = len(refs); first_child = len(nodes)
        batches = [ids[i:i+LEAF] for i in range(0, len(ids), LEAF)]
        if len(batches) > 255:
            raise ValueError('Cell access tree exceeds 255 children')
        for b in batches:
            lo = np.min([boxes[i][0] for i in b], 0); hi = np.max([boxes[i][1] for i in b], 0)
            nodes.append(struct.pack(NODE, *lo, 0, len(b), len(b), *hi, 0, len(refs)))
            refs.extend(b); objects.extend(struct.pack('<3fI3fI', *boxes[i][0], 0, *boxes[i][1], 0) for i in b)
        lo = np.min([boxes[i][0] for i in ids], 0); hi = np.max([boxes[i][1] for i in ids], 0)
        nodes[c] = struct.pack(NODE, *lo, len(batches), 0, len(ids), *hi, first_child, start)
    if len(refs) > 65535+LEAF or len(nodes) > 65535 or max(struct.unpack_from(NODE, n)[10] for n in nodes) > 65535:
        raise ValueError('Cell references exceed the uint16 index space')
    return dict(bsp=bsp, cells=len(members), nodes=nodes, refs=refs, objects=objects, members=members)


def locate(bsp, planes, point):
    at = 0
    while bsp[at][0] != -1:
        n = struct.unpack_from('<4f', planes, bsp[at][0]*16); at = bsp[at][1]+int(np.dot(n[:3], point) < n[3])
    return bsp[at][1]


def build(ident, package):
    package = Path(package); bsp_path = next((package/'mod/maps').glob('*.bsp')); work = folder(ident)/'visibility-cells'
    if (package/REPORT).exists():
        raise ValueError('Cells already built: '+str(package/REPORT))
    work.mkdir(exist_ok=True)
    l = read_lumps(bsp_path, (1, 0x50, 0x51, 0x6a, 0x6b, 0x6c, 0x77, 0x78, 0x79, 0x7b))
    if len(l[0x6b]) != 8 or l[0x6c]:
        raise ValueError('Expected the single all-visible cell of the conversions')
    info = struct.unpack('<4I3f', l[0x7b][:28]); base = (info[2]+63) & ~63
    s = scene(ident, bsp_path); U = s['meshes']+len(s['props'])
    points, seeds, reach = viewpoints(ident, s)
    print(ident, 'triangles', len(s['tris']), 'units', U, 'seeds', seeds, 'reachable', reach, 'viewpoints', len(points), flush=True)
    grid = (math.floor(points[:, 0].min()/TILE)*TILE-TILE, math.floor(points[:, 1].min()/TILE)*TILE-TILE)
    X = int((points[:, 0].max()-grid[0])//TILE)+2; Y = int((points[:, 1].max()-grid[1])//TILE)+2
    tile_of = np.c_[(points[:, 0]-grid[0])//TILE, (points[:, 1]-grid[1])//TILE].astype('i8')
    inputs = {'triangles.bin': s['tris'].astype('<f4'), 'occluders.bin': (~s['clear']).astype('u1'), 'units.bin': s['units'].astype('<u4'),
              'points.bin': points, 'tiles.bin': (tile_of[:, 0]*Y+tile_of[:, 1]).astype('<u4')}
    # The rays depend only on these inputs: an unchanged scene and viewpoint set reuses seen.bin.
    cached = (work/'seen.bin').exists() and (work/'seen.bin').stat().st_size == X*Y*U and \
        all((work/f).exists() and (work/f).read_bytes() == a.tobytes() for f, a in inputs.items())
    for f, a in inputs.items():
        a.tofile(work/f)
    if not cached:
        subprocess.run([str(ROOT/'tools/visibility_rays.exe'), 'tiles', *(str(work/f) for f in ('triangles.bin', 'occluders.bin', 'units.bin', 'points.bin', 'tiles.bin')),
                       str(X*Y), str(U), str(RAYS), str(work/'seen.bin')], check=True)
    seen = np.fromfile(work/'seen.bin', 'u1').reshape(X, Y, U).astype(bool)
    weight = np.bincount(tile_of[:, 0]*Y+tile_of[:, 1], minlength=X*Y).reshape(X, Y)
    always = np.zeros(U, bool); always[info[1]:s['meshes']] = True  # transparent and sky meshes
    always[[s['meshes']+k for k in s['missing']]] = True
    lo, hi = unit_boxes(l, s)
    # Cells cover the play bounds; cameras outside them (out of bounds, the stadium ring) see everything.
    b = np.asarray(CONFIG[ident]['bounds'], 'f8')
    sx0, sy0 = [max(0, int((b[0][k]-grid[k])//TILE)) for k in (0, 1)]
    sx1, sy1 = min(X, int(-(-(b[1][0]-grid[0])//TILE))), min(Y, int(-(-(b[1][1]-grid[1])//TILE)))
    sub = (grid[0]+sx0*TILE, grid[1]+sy0*TILE); sub_tile = tile_of-[sx0, sy0]
    tree, sets, total = plan(dilate(seen)[sx0:sx1, sy0:sy1], weight[sx0:sx1, sy0:sy1], lo, hi, sub, always)
    # Object bounds: the existing camera-domain-widened boxes, by reference.
    old = {r: (o[:3], o[4:7]) for r, o in zip(struct.unpack(f'<{len(l[0x78])//2}H', l[0x78]), struct.iter_unpack('<3fI3fI', l[0x79]))}
    refs_of = list(range(s['meshes']))+[base+k for k in range(len(s['props']))]
    if set(refs_of) != set(old):
        raise ValueError('Units differ from the existing object references')
    planes = bytearray(l[1]); e = encode(tree, sets, points, sub_tile, sub, sx1-sx0, sy1-sy0, planes, refs_of, old)
    # Every viewpoint's cell draws everything seen from its tile; every object is in the all-visible cell.
    cells_of = [locate(e['bsp'], planes, p) for p in points]
    for c, tx, ty in {(c, t[0], t[1]) for c, t in zip(cells_of, tile_of)}:
        if not np.all(np.isin(np.flatnonzero(seen[tx, ty]), e['members'][c])):
            raise ValueError('A viewpoint cell misses what its tile sees')
    sizes = [len(m) for m in e['members']]; per_view = np.asarray([sizes[c] for c in cells_of])
    out = bsp_path.with_suffix('.cells.bsp')
    compact(bsp_path, out, {1: bytes(planes), 0x6a: b''.join(struct.pack('<iI', *n) for n in e['bsp']),
                            0x6b: b''.join(struct.pack('<2H2h', 0, 0, 1, -1) for _ in range(e['cells'])),
                            0x77: b''.join(e['nodes']), 0x78: struct.pack(f'<{len(e["refs"])}H', *e['refs']), 0x79: b''.join(e['objects'])})
    out.replace(bsp_path)
    report = dict(units=U, meshes=s['meshes'], props=len(s['props']), props_without_triangles=len(s['missing']), triangles=int(len(s['tris'])),
                  viewpoints=int(len(points)), rays_per_viewpoint=RAYS, tile=TILE, grid=dict(origin=sub, tiles=[sx1-sx0, sy1-sy0]), near=NEAR,
                  cells=e['cells'], cell_sizes=sizes, cell_bsp_nodes=len(e['bsp']), references=len(e['refs']), access_nodes=len(e['nodes']),
                  mean_drawn_per_viewpoint=round(float(per_view.mean()), 1), max_drawn_per_viewpoint=int(per_view.max()),
                  mean_drawn_fraction=round(float(per_view.mean()/U), 3),
                  cell_rects=[dict(x=[sub[0]+TILE*r[0], sub[0]+TILE*r[1]], y=[sub[1]+TILE*r[2], sub[1]+TILE*r[3]], objects=int(sets[r].sum()))
                              for r in sets])
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps({k: v for k, v in report.items() if k != 'cell_rects'}, indent=2))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
