"""Invisible-collision audit for the older Phase Runner and Drop-Off builds.

Reuses the Party Crasher / Firing Range tooling on maps outside new_arena_ports:
reachable ground is flooded from the BSP's own spawn points (no out-of-bounds
volumes are applied, so reach is generous), active native collision is sampled,
and samples more than GAP units from any drawn surface within REACH of
reachable ground are attributed to the source placement whose transformed
LOD0 bounds contain them: an omitted prop (world-baked collision with nothing
drawn) or a drawn prop (collider larger than its drawn LOD).

  python audit_legacy_collision.py phase-runner drop-off
"""
import collections
import json
import re
import struct
import sys
from pathlib import Path

import numpy as np
import analyse_visibility as vis
from audit_collision_visibility import native_collision, sample, GAP, SPACING
from new_arena_ports import ROOT
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
from scipy.spatial import cKDTree

STORE = Path('D:/Games/ApexToTitanfallWork/project-storage/output')
WORK = Path('D:/Games/ApexToTitanfallWork/legacy-audit')
REACH = 400
MAPS = {
    'phase-runner': dict(bsp=ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'),
    'drop-off': dict(bsp=ROOT/'northstar/ArenaComposite/mod/maps/mp_arena_composite.bsp'),
}


def placements(ident):
    """(index, model, origin, angles, scale, status) for every local source placement."""
    if ident == 'phase-runner':
        props = {p['index']: p for p in json.loads((STORE/'phase-runner/static-props.json').read_text())}
        status = {p['source_index']: p['status'] for p in json.loads((ROOT/'docs/conversion/static-placement-inventory.json').read_text())['placements']}
        fill = ROOT/'docs/scenery-fill/phase-runner-recovered-placements.json'
        if fill.exists():
            rows = json.loads(fill.read_text()); rows = rows.get('placements', rows) if isinstance(rows, dict) else rows
            for r in rows:
                status[r.get('index', r.get('source_index'))] = 'rendered'
        return [(i, p['model'], p['origin'], p['angles'], p.get('scale', 1), status.get(i, 'outside')) for i, p in props.items()
                if status.get(i) != 'outside_arena_not_imported']
    scene = json.loads((STORE/'composite/scene.json').read_text())
    inv = {p['index']: p for p in json.loads((STORE/'composite/source-inventory.json').read_text())['props']}
    drawn = {p['index'] for p in scene['placements']}; omitted = {p['index']: p.get('reason') for p in scene['omitted']}
    return [(i, p['model'], p['origin'], p['angles'], p.get('scale', 1), 'rendered' if i in drawn else 'omitted' if i in omitted else 'outside')
            for i, p in inv.items() if i in drawn or i in omitted]


def spawns(bsp):
    from repair_preview_index_padding import read_lumps
    text = read_lumps(bsp, (0,))[0].decode('latin-1')
    out = []
    for block in re.findall(r'\{[^{}]*\}', text):
        if re.search(r'"classname"\s+"info_spawnpoint_(human|human_start)"', block):
            o = re.search(r'"origin"\s+"([^"]+)"', block)
            if o:
                out.append([float(v) for v in o.group(1).split()])
    return out


def reachable(ident, bsp, tris):
    work = WORK/ident; work.mkdir(parents=True, exist_ok=True)
    probes = [dict(origin=p) for p in spawns(bsp)]
    if not probes:
        raise ValueError('No spawn points in '+str(bsp))
    (work/'native-spawn-candidates.json').write_text(json.dumps(dict(regions=[dict(probes=probes)])))
    lo = tris.reshape(-1, 3).min(0)
    vis.CONFIG = {ident: dict(bounds=[lo.tolist(), lo.tolist()], offset=[0, 0, 0])}
    vis.folder = lambda _: work
    vis.triggers = lambda _: []
    from analyse_visibility import render_triangles
    _, mesh_of, names = render_triangles(bsp)
    solid = np.asarray([not any(w in n.lower() for w in ('water', 'sky')) for n in names])[mesh_of]
    _, reach = vis.viewpoints(ident, tris, solid)
    np.save(work/'reachable.npy', reach)
    return reach, len(probes)


def model_points(model, cache, index):
    from read_vg_static import load
    stem = Path(model).stem.lower()
    if stem not in cache:
        cache[stem] = None
        if stem in index:
            try:
                raw, _, _ = load(index[stem], 0, True)
                cache[stem] = np.concatenate([np.asarray(s, 'f4').reshape(-1, 12)[:, :3] for s in raw if len(s)]).astype('f8')
            except Exception:
                pass
    return cache[stem]


def audit(ident):
    from analyse_visibility import render_triangles
    from plan_arena_fill import model_index
    from stage_prop_geometry import rotation
    bsp = MAPS[ident]['bsp']
    tris, mesh_of, names = render_triangles(bsp); tris = tris.astype('f8')
    reach, nspawn = reachable(ident, bsp, tris)
    see = np.asarray([not any(w in n.lower() for w in ('sky', 'water')) for n in names])[mesh_of]
    tree = cKDTree(sample(tris[see], SPACING/2))
    coll = native_collision(bsp)
    rd, _ = cKDTree(reach).query(coll.mean(1)); coll = coll[rd < REACH]
    pts = sample(coll, SPACING)
    near_reach = cKDTree(reach).query(pts)[0] < REACH
    pts = pts[near_reach]
    d, _ = tree.query(pts, distance_upper_bound=GAP*4); bad = pts[d > GAP]
    # Attribute invisible samples to placements whose transformed LOD0 bounds contain them.
    rows = placements(ident); centres = np.asarray([r[2] for r in rows]); ctree = cKDTree(centres)
    index = model_index(); cache = {}; owner = collections.Counter(); example = {}; bounds = {}
    for p in bad:
        for j in ctree.query_ball_point(p, 900):
            i, model, origin, angles, scale, status = rows[j]
            if i not in bounds:
                v = model_points(model, cache, index)
                bounds[i] = None if v is None else (lambda w: (w.min(0)-6, w.max(0)+6))(v@np.asarray(rotation(angles)).T*scale+np.asarray(origin))
            b = bounds[i]
            if b is not None and np.all(p >= b[0]) and np.all(p <= b[1]):
                owner[(i, Path(model).stem, status)] += 1; example.setdefault((i, Path(model).stem, status), [round(float(x)) for x in p])
                break
    attributed = sum(owner.values())
    summary = collections.Counter()
    for (i, m, s), n in owner.items():
        summary[s] += n
    report = dict(map=ident, spawns=nspawn, reachable_cells=len(reach), collision_samples=int(len(pts)),
                  invisible_samples=int(len(bad)), fraction=round(len(bad)/max(1, len(pts)), 4),
                  attributed=attributed, by_status=dict(summary),
                  placements=[dict(index=k[0], model=k[1], status=k[2], samples=n, example=example[k]) for k, n in owner.most_common(80)])
    (WORK/ident/'collision-visibility.json').write_text(json.dumps(report, indent=2))
    print(ident, 'samples', len(pts), 'invisible', len(bad), report['fraction'], 'attributed', attributed, dict(summary), flush=True)
    for r in report['placements'][:20]:
        print(f"  {r['samples']:6d} {r['index']:6d} {r['model']:45s} {r['status']:9s} {r['example']}")
    return report


if __name__ == '__main__':
    for ident in sys.argv[1:]:
        audit(ident)
