"""Read RSX Cast model exports (current Apex models) into the pipeline's section format.

Current Apex vertex groups (`.vg`) no longer use the `0tVG` layout read by
read_vg_static.py. RSX exports every LOD as `<model>_LOD<n>.cast`
(https://github.com/dtzxporter/cast), with positions, normals, UV layers,
vertex colours and per-mesh materials. `load(folder, lod)` returns the same
`(sections, slots, skins)` shape as read_vg_static.load(..., with_colors=True):
each section is a flat float list of 12 values per vertex (x y z, nx ny nz,
u v, r g b a) in triangle order, `slots` index into `skins[0]`, the material names.
Cast carries one material set, so only skin 0 exists.
"""
import re
import struct
from pathlib import Path

import numpy as np

MAGIC = 0x74736163  # 'cast'
TYPES = {0x62: ('<B', 1), 0x68: ('<H', 1), 0x69: ('<I', 1), 0x6C: ('<Q', 1), 0x66: ('<f', 1), 0x64: ('<d', 1),
         0x7632: ('<f', 2), 0x7633: ('<f', 3), 0x7634: ('<f', 4)}


def _node(b, at):
    ident, size, hash_, nprops, nchildren = struct.unpack_from('<2IQ2I', b, at); end = at+size; at += 24; props = {}
    for _ in range(nprops):
        pid, nlen, count = struct.unpack_from('<2HI', b, at); at += 8
        name = b[at:at+nlen].decode(); at += nlen
        if pid == 0x73:  # 's' null-terminated string
            stop = b.index(0, at); props[name] = b[at:stop].decode(errors='replace'); at = stop+1; continue
        fmt, width = TYPES[pid]; n = count*width; item = struct.calcsize(fmt)
        props[name] = np.frombuffer(b, fmt, n, at).reshape(count, width) if width > 1 else np.frombuffer(b, fmt, n, at)
        at += n*item
    children = []
    for _ in range(nchildren):
        child, at = _node(b, at); children.append(child)
    return dict(id=struct.pack('<I', ident).decode(errors='replace'), hash=hash_, props=props, children=children), end


def parse(path):
    b = Path(path).read_bytes(); magic, version, roots, flags = struct.unpack_from('<4I', b)
    if magic != MAGIC:
        raise ValueError('Not a Cast file: '+str(path))
    at = 16; nodes = []
    for _ in range(roots):
        n, at = _node(b, at); nodes.append(n)
    return nodes


def walk(node, kind):
    if node['id'] == kind:
        yield node
    for c in node['children']:
        yield from walk(c, kind)


def lod_files(folder):
    folder = Path(folder)
    return sorted(folder.glob(folder.name+'_LOD*.cast'), key=lambda p: int(p.stem.rsplit('LOD', 1)[1]))


def levels(folder):
    return len(lod_files(folder))


def load(folder, lod=0, with_colors=True):
    files = lod_files(folder)
    if not files:
        raise FileNotFoundError('No Cast LODs in '+str(folder))
    roots = parse(files[min(lod, len(files)-1)])
    materials = {m['hash']: m['props'].get('n', 'material_%x' % m['hash']) for r in roots for m in walk(r, 'mtrl')}
    names, sections, slots = [], [], []
    for r in roots:
        for mesh in walk(r, 'mesh'):
            p = mesh['props']; pos = p['vp'].astype('f4'); n = len(pos)
            nrm = p['vn'].astype('f4') if 'vn' in p else np.zeros((n, 3), 'f4')
            uv = p['u0'].astype('f4') if 'u0' in p else np.zeros((n, 2), 'f4')
            if 'c0' in p or 'vc' in p:
                c = p.get('c0', p.get('vc'))
                col = (c.astype('f4')*255 if c.ndim == 2 else
                       np.stack([(c >> s) & 255 for s in (0, 8, 16, 24)], 1).astype('f4'))
            else:
                col = np.full((n, 4), 255, 'f4')
            faces = np.asarray(p['f'], 'u4').reshape(-1, 3)
            v = np.concatenate([pos, nrm, uv, col], 1)[faces.reshape(-1)]
            mat = materials.get(int(p['m'][0]) if 'm' in p else 0)
            if mat is None:
                # Without material nodes RSX names meshes body_<n>_LOD<k>_<model>_<material>.
                mat = re.sub(r'^body_\d+_LOD\d+_', '', p.get('n', ''))
                stem = Path(folder).name
                mat = mat[len(stem)+1:] if mat.startswith(stem+'_') else (mat or 'default_material')
            if mat not in names:
                names.append(mat)
            sections.append(v.reshape(-1).tolist()); slots.append(names.index(mat))
    return sections, slots, [names]
