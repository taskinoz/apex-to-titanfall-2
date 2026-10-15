"""Stop drawing whole native meshes: coplanar overlay layers and proven-hidden meshes.

Two sources of retired meshes, both conservative:

* overlay materials whose every triangle is backed by another surface within
  3 units (verified by the backing test; e.g. Party Crasher's opaque caustic
  light layer and the dark waterfall layer over the marble orb);
* meshes that analyse_visibility.py never hit from any reachable viewpoint.

Only render data changes. Collision, entities, lights, probes and lightmap
charts stay. Hidden meshes keep casting sun shadows; overlay layers do not. Every corner has its own vertex record, so dropping a
mesh never affects another.
"""
import argparse
import json
import os
import shutil
import struct
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, folder
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder

OVERLAYS = {'party-crasher': ('caustic_water_01', 'waterfall_interior_02')}


def keys(t):
    return np.sort(np.asarray(t, '<f4'), axis=1).reshape(-1, 9).copy().view('V36').reshape(-1)


def retire(ident, use_hidden=True):
    out = folder(ident); bsp = out/(CONFIG[ident]['target']+'.bsp'); work = out/'retire'
    backup = out/'before-retire'
    if (work/'result.json').exists():
        raise ValueError('Already applied; restore before-retire to rebuild')
    if not backup.exists():
        backup.mkdir(parents=True)
        for p in (bsp, out/'scene.json'):
            shutil.copy2(p, backup/p.name)
    work.mkdir(exist_ok=True)
    l = read_lumps(bsp, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    native = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        native.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    from build_composite_map import DT
    rec = np.frombuffer(l[0x49], DT); pos = np.frombuffer(l[3], '<f4').reshape(-1, 3)
    overlays = set(OVERLAYS.get(ident, ()))
    for name in overlays:
        if not (out/f'backed-{name}.npy').exists():
            raise ValueError('Run the backing test before retiring overlay '+name)
    hidden = set()
    if use_hidden:
        analysis = json.loads((out/'visibility/analysis.json').read_text())
        if analysis['meshes'] != len(l[0x50])//28:
            raise ValueError('Visibility analysis is stale for this BSP')
        hidden = set(np.load(out/'visibility/hidden-meshes.npy').tolist())
    keep, bounds, newindices, retired_pts = [], bytearray(), bytearray(), []
    report = dict(overlay_meshes=0, overlay_triangles=0, hidden_meshes=0, hidden_triangles=0, by_material={})
    for i, mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI', l[0x50])):
        sort = sorts[mesh[-2]]; name = native[sort[0]]
        local = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2)
        why = 'overlay' if name in overlays else 'hidden' if i in hidden else None
        if why:
            report[why+'_meshes'] += 1; report[why+'_triangles'] += mesh[1]
            report['by_material'][name] = report['by_material'].get(name, 0)+mesh[1]
            # Hidden meshes still occlude the sun: keep their shadow casters.
            if why == 'overlay':
                retired_pts.append(pos[rec['pi'][local.astype('u4')+sort[-1]]].reshape(-1, 3, 3))
            continue
        record = list(mesh); record[0] = len(newindices)//2
        newindices.extend(local.tobytes())
        if mesh[1] & 1:
            newindices.extend(struct.pack('<3H', *[int(local[-1])]*3))
        keep.append(struct.pack('<I3H6b2h2BHI', *record)); bounds.extend(l[0x51][i*32:i*32+32])
    buf[0x4f] = newindices; buf[0x50] = bytearray(b''.join(keep)); buf[0x51] = bounds
    count = len(keep); struct.pack_into('<2I', buf[0xe], 24, 0, count)
    excluded = keys(np.concatenate(retired_pts)) if retired_pts else np.empty(0, 'V36')
    shv = np.frombuffer(l[0x7c], '<f4').reshape(-1, 3); newv, newix, newrec = bytearray(), bytearray(), bytearray()
    for first, n, page, unused in struct.iter_unpack('<2I2h', l[0x7f]):
        pts = shv[first:first+n*3].reshape(-1, 3, 3); pts = pts[~np.isin(keys(pts), excluded)]
        if not len(pts):
            continue
        newrec.extend(struct.pack('<2I2h', len(newv)//12, len(pts), page, unused)); newv.extend(pts.tobytes())
        newix.extend(np.arange(len(pts)*3, dtype='<u2').tobytes())
    buf[0x7c], buf[0x7e], buf[0x7f] = newv, newix, newrec
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    for at in (0, 36):
        struct.pack_into('<i', buf[5], at+20, len(newrec)//12)
    struct.pack_into('<i', buf[5], 44, len(newrec)//12)
    buf.update(reorder(buf)[0])
    temp = bsp.with_suffix('.retire.bsp'); compact(bsp, temp, buf); os.replace(temp, bsp)
    (work/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'by_material'}), flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('ident', choices=sorted(CONFIG))
    p.add_argument('--no-hidden', action='store_true')
    a = p.parse_args(); retire(a.ident, not a.no_hidden)
