"""Weld the sun-shadow (CSM) mesh positions, so each opaque shadow mesh stores each position once.

The world builds (build_composite_map.py and the arena-port builds) write each shadow mesh as three fresh positions
per triangle: Thunderdome 0.3.0 has 2,956,071 shadow positions for 663,215 distinct ones (35 MB of lump 0x7C), where
Homestead has 86,042 positions for 384,819 indices. A shadow mesh record (0x7F, `<2I2h`) is its first position, its
triangle count, opaque and material sort; its uint16 indices (0x7E) follow the previous meshes' and are local to that
first position. Each opaque mesh is welded on exact float32 equality in first-use order, and its indices are rewritten
in place, so the index lump keeps its length, triangle order and winding. Alpha shadow meshes (opaque 0) index 0x7D
and are left alone. The shadow environments (0x05) address meshes by number, which does not change.

  python weld_shadow_meshes.py <package or .bsp>
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact

REPORT = 'shadow-weld.json'


def weld_lumps(l):
    """Replacement lumps 0x7C, 0x7E, 0x7F and a report."""
    pos = np.frombuffer(l[0x7C], '<f4').reshape(-1, 3); idx = np.frombuffer(l[0x7E], '<u2').copy()
    meshes = [list(m) for m in struct.iter_unpack('<2I2h', l[0x7F])]; out = []; total = 0; at = 0
    for m in meshes:
        first, count, opaque = m[0], m[1], m[2]; local = idx[at:at+3*count].astype(np.int64)
        if opaque:
            faces = pos[first+local]
            _, first_use, inverse = np.unique(np.ascontiguousarray(faces).view('V12').ravel(), return_index=True,
                                              return_inverse=True)
            order = np.argsort(first_use); rank = np.empty(len(order), np.int64); rank[order] = np.arange(len(order))
            idx[at:at+3*count] = rank[inverse.ravel()]; out.append(faces[first_use[order]])
            m[0] = total; total += len(order)
        at += 3*count
    if at != len(idx):
        raise ValueError('Shadow mesh triangles do not cover the index lump')
    new = np.ascontiguousarray(np.concatenate(out) if out else np.empty((0, 3)), '<f4')
    at = 0  # decode everything again against the originals
    for old, m in zip(struct.iter_unpack('<2I2h', l[0x7F]), meshes):
        if m[2]:
            a = np.frombuffer(l[0x7E], '<u2')[at:at+3*m[1]].astype(np.int64); b = idx[at:at+3*m[1]].astype(np.int64)
            if not np.array_equal(pos[old[0]+a], new[m[0]+b]):
                raise AssertionError('A shadow mesh does not decode to its triangles')
        at += 3*m[1]
    changes = {0x7C: new.tobytes(), 0x7E: idx.tobytes(), 0x7F: b''.join(struct.pack('<2I2h', *m) for m in meshes)}
    return changes, dict(shadow_meshes=len(meshes), positions_before=len(pos), positions_after=len(new),
                         indices=len(idx), bytes_saved=len(l[0x7C])-len(changes[0x7C]))


def weld(target):
    target = Path(target); bsp = target if target.suffix == '.bsp' else next((target/'mod/maps').glob('*.bsp'))
    report_path = (bsp.parent if target.suffix == '.bsp' else target)/REPORT
    if report_path.exists():
        raise ValueError('Shadow meshes already welded: '+str(report_path))
    changes, report = weld_lumps(read_lumps(bsp, (0x7C, 0x7E, 0x7F)))
    before = bsp.stat().st_size
    temp = bsp.with_suffix('.shadow.bsp'); compact(bsp, temp, changes); os.replace(temp, bsp)
    report.update(bsp_bytes_before=before, bsp_bytes_after=bsp.stat().st_size)
    report_path.write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    weld(sys.argv[1])
