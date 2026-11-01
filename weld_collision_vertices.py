"""Weld the vertex positions of a BSP's triangle collision, so each collision header stores each position once.

native_triangle_collision.encode writes three fresh positions per triangle, so Thunderdome's 59,122 headers held
19.96M of the 22.97M positions in lump 0x3 (276 MB), although only 3.68M positions are distinct. A triangle word
stores its first vertex as a 10-bit index from the header's vertex base and the other two as 7-bit forward deltas,
so positions can be shared within a header (at most 288 per header here) as long as each triangle's indices span at
most 127. Each header is welded on exact float32 equality, in first-use order; a header whose spans would exceed
127 is welded greedily, re-emitting a position once its last copy is more than 125 back. A triangle is rotated
(keeping its winding) to put its lowest index first, and its low/high-Z flag bits (28..30, as encode) are recomputed
for the new order.

Lump 0x3 is rebuilt as the positions the render vertices (0x47..0x4B) use, in their old order, then the welded
collision positions header by header; render vertices are re-pointed, and positions nothing uses are dropped. A
header whose flags do not follow encode's rule (other flag bits set, or a different Z order) keeps its positions
unwelded. Every triangle and render vertex is decoded again and compared with the original before writing.

  python weld_collision_vertices.py <package>
"""
import json
import os
import struct
import sys
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact

STRIDE = {0x47: 20, 0x48: 36, 0x49: 44, 0x4a: 28, 0x4b: 92}  # render vertex lumps; the position index comes first
HEADER = '<6h4i4f'
SPAN = 127
OPTIONS = np.array([[1, 2], [0, 2], [1, 0]])  # encode's remaining pair for each lowest-Z vertex
REPORT = 'collision-weld.json'


def z_flags(faces):
    """Bits 28..30 of each triangle word, as native_triangle_collision.encode sets them."""
    z = faces[:, :, 2]; low = z.argmin(1); high = z.argmax(1)
    pick = (OPTIONS[low, 1] == high) & (low != high)
    return (low | pick.astype(np.int64) << 2).astype('<u4') << 28


def decode(words, base):
    i0 = (words & 1023).astype(np.int64)
    return base + np.stack((i0, i0+(words >> 10 & 127), i0+(words >> 17 & 127)), 1)


def weld_group(faces):
    """(positions to keep, as indices into faces' flattened vertices; per-triangle local indices)."""
    flat = np.ascontiguousarray(faces.reshape(-1, 3)); keys = flat.view('V12').ravel()
    _, first, inverse = np.unique(keys, return_index=True, return_inverse=True)
    order = np.argsort(first); rank = np.empty(len(first), np.int64); rank[order] = np.arange(len(first))
    local = rank[inverse.ravel()].reshape(-1, 3)
    if (local.max(1)-local.min(1)).max() <= SPAN:
        return first[order], local
    slots, keep, local = {}, [], []
    for t in range(len(faces)):
        tri = []
        for j in range(3):
            k = keys[3*t+j].tobytes(); i = slots.get(k)
            if i is None or len(keep)-i > SPAN-2:  # keeps the span within SPAN with up to two new positions after it
                i = slots[k] = len(keep); keep.append(3*t+j)
            tri.append(i)
        local.append(tri)
    return np.array(keep), np.array(local)


def weld_lumps(l):
    """Replacement lumps 0x3, 0x42, 0x45 and the render vertex lumps, and a report."""
    pos = np.frombuffer(l[3], '<f4').reshape(-1, 3); words = np.frombuffer(l[0x42], '<u4').copy()
    used = np.zeros(len(pos), bool); verts = {}
    for k, s in STRIDE.items():
        if l.get(k):
            verts[k] = np.frombuffer(l[k], '<u4').reshape(-1, s//4).copy(); used[verts[k][:, 0]] = True
    remap = np.cumsum(used)-1; old_render = {k: v[:, 0].copy() for k, v in verts.items()}
    for v in verts.values():
        v[:, 0] = remap[v[:, 0]]
    out = [pos[used]]; total = int(used.sum()); headers = bytearray(l[0x45]); expected = []; unwelded = 0
    for at in range(0, len(headers), 44):
        h = list(struct.unpack_from(HEADER, headers, at)); count, base, first = h[4], h[6], h[7]
        w = words[first:first+count]; faces = pos[decode(w, base)]
        if (w & 0x8F000000).any() or (w & 0x70000000 != z_flags(faces)).any():
            out.append(pos[base:base+h[3]]); h[6] = total; total += h[3]; unwelded += 1
            expected.append(faces); struct.pack_into(HEADER, headers, at, *h); continue
        keep, local = weld_group(faces); out.append(faces.reshape(-1, 3)[keep])
        roll = (local.argmin(1)[:, None]+np.arange(3)) % 3; rows = np.arange(count)[:, None]
        local = local[rows, roll]; faces = faces[rows, roll]
        words[first:first+count] = (local[:, 0] | (local[:, 1]-local[:, 0]) << 10 | (local[:, 2]-local[:, 0]) << 17
                                    ).astype('<u4') | z_flags(faces)
        h[3] = len(keep); h[6] = total; total += len(keep); expected.append(faces)
        struct.pack_into(HEADER, headers, at, *h)
    new = np.ascontiguousarray(np.concatenate(out), '<f4')
    # Decode everything again from the new lumps.
    for at, faces in zip(range(0, len(headers), 44), expected):
        h = struct.unpack_from(HEADER, headers, at); w = words[h[7]:h[7]+h[4]]; ix = decode(w, h[6])
        if ix.max() >= h[6]+h[3] or not np.array_equal(new[ix], faces):
            raise AssertionError(f'Header {at//44} does not decode to its triangles')
    for k, v in verts.items():
        if not np.array_equal(new[v[:, 0]], pos[old_render[k]]):
            raise AssertionError(f'Render vertex lump {k:#x} moved')
    changes = {3: new.tobytes(), 0x42: words.tobytes(), 0x45: bytes(headers)}
    changes.update({k: v.tobytes() for k, v in verts.items()})
    report = dict(positions_before=len(pos), positions_after=len(new), render_positions=int(used.sum()),
                  collision_positions_before=int(sum(h[3] for h in struct.iter_unpack(HEADER, l[0x45]))),
                  collision_positions_after=len(new)-int(used.sum()), headers=len(headers)//44, unwelded_headers=unwelded,
                  bytes_saved=len(l[3])-len(changes[3]))
    return changes, report


def weld(package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    if (package/REPORT).exists():
        raise ValueError('Collision already welded: '+str(package/REPORT))
    changes, report = weld_lumps(read_lumps(bsp, (3, 0x42, 0x45, *STRIDE)))
    before = bsp.stat().st_size
    temp = bsp.with_suffix('.weld.bsp'); compact(bsp, temp, changes); os.replace(temp, bsp)
    report.update(bsp_bytes_before=before, bsp_bytes_after=bsp.stat().st_size)
    (package/REPORT).write_text(json.dumps(report, indent=2)); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    weld(sys.argv[1])
