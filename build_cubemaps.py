"""Give a port reflection cubemaps, captured in game.

No port has any (lumps 0x28 PAKFILE and 0x2A CUBEMAPS are empty, and every mesh's cubemap byte is -1), where
Homestead has 4 and Colony 7. The layout follows MRVN-Radiant's titanfall2_cubemaps.cpp and
docs/respawn/RESPAWN_TF2_LUMPS.md, read from six retail maps:
* CUBEMAPS: per cubemap `<3iI`, its integer origin and a zero;
* meshes (0x50): byte 11 is the mesh's cubemap; lit meshes take the nearest one, unlit meshes -1; material sorts
  (0x52) store cubemap 0, as every Homestead sort does;
* PAKFILE: a stored ZIP with the comment `XZP1 0` padded to 32 bytes, holding
  materials/maps/<map>/cubemaps.hdr.vtf: VTF 7.5, 256x256 faces, flags 0x420C, format 66 (BC6H unsigned), 9 mips,
  one frame per cubemap; data is mips smallest first, then frames, then the six faces in D3D order (+X, -X, +Y, -Y,
  +Z, -Z) sampled with Source world vectors. Resources `0` (image offset), `CMA` (one float per cubemap, meaning
  unresolved: MRVN writes 1.0 for gameplay cubemaps) and `CRC` (0).

MRVN renders faces from its bake; here each cubemap is six in-game screenshots from its origin (camera fov 106.26,
which is 90 degrees vertically at 16:9: Titanfall's fov is the 4:3 horizontal angle), resampled per face texel
from the view facing it most directly, linearised from sRGB and compressed to BC6H with texconv.

  python build_cubemaps.py plan <package> [between]    cubemap origins: the two team bases and points between them
  python build_cubemaps.py capture <package>           harness session must be running on that package
  python build_cubemaps.py write <package>
"""
import io
import json
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from repair_environment_lighting import entities

ROOT = Path(__file__).resolve().parent
FACE = 256
MIPS = 9
FOV = 106.26           # 4:3 horizontal fov whose vertical angle at 16:9 is 90 degrees
EYE = 72.
VIEWS = {'px': (0, 0), 'py': (0, 90), 'nx': (0, 180), 'ny': (0, 270), 'pz': (-90, 0), 'nz': (90, 0)}  # pitch, yaw


def face_direction(face, u, v):
    """MRVN FaceDirection: D3D cube faces with Source world vectors (u, v in [-1, 1], v down)."""
    one = np.ones_like(u)
    d = [np.stack((one, -v, -u)), np.stack((-one, -v, u)), np.stack((u, one, v)),
         np.stack((u, -one, -v)), np.stack((u, -v, one)), np.stack((-u, -v, -one))][face]
    return d/np.linalg.norm(d, axis=0)


def basis(pitch, yaw):
    p, y = np.radians(pitch), np.radians(yaw)
    forward = np.array([np.cos(p)*np.cos(y), np.cos(p)*np.sin(y), -np.sin(p)])
    right = np.array([np.sin(y), -np.cos(y), 0.]); return forward, right, np.cross(right, forward)


def plan(package, between=3):
    """One cubemap at each team base (the two spawn clusters) and `between` along the line joining them, the bases at
    their spawns' height, the others over the highest floor within 512 units above it."""
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    spawns = np.array([[float(v) for v in e['origin'].split()] for e in entities(bsp)
                       if e.get('classname', '').startswith('info_spawnpoint_human')])
    a, b = spawns[np.linalg.norm(spawns-spawns.mean(0), axis=1).argmax()], None
    b = spawns[np.linalg.norm(spawns-a, axis=1).argmax()]
    for _ in range(20):  # two-means: the bases
        near_a = np.linalg.norm(spawns-a, axis=1) <= np.linalg.norm(spawns-b, axis=1)
        a, b = spawns[near_a].mean(0), spawns[~near_a].mean(0)
    from analyse_visibility import render_triangles
    tris = render_triangles(bsp)[0].astype('f8'); p0, p1, p2 = tris[:, 0], tris[:, 1], tris[:, 2]
    d = (p1[:, 1]-p2[:, 1])*(p0[:, 0]-p2[:, 0])+(p2[:, 0]-p1[:, 0])*(p0[:, 1]-p2[:, 1])

    def floor(x, y, z):
        with np.errstate(divide='ignore', invalid='ignore'):
            u = ((p1[:, 1]-p2[:, 1])*(x-p2[:, 0])+(p2[:, 0]-p1[:, 0])*(y-p2[:, 1]))/d
            v = ((p2[:, 1]-p0[:, 1])*(x-p2[:, 0])+(p0[:, 0]-p2[:, 0])*(y-p2[:, 1]))/d
        h = u*p0[:, 2]+v*p1[:, 2]+(1-u-v)*p2[:, 2]
        hit = (np.abs(d) > 1e-6) & (u >= 0) & (v >= 0) & (u+v <= 1) & (h <= z+512)
        return h[hit].max() if hit.any() else None
    origins = []
    for t in np.linspace(0, 1, between+2):
        x, y, z = a+(b-a)*t; f = z if t in (0, 1) else floor(x, y, z)  # spawn rooms are roofed: bases at spawn height
        if f is not None:
            origins.append([x, y, f+EYE])
    origins = np.round(origins).tolist()
    (package/'cubemaps.json').write_text(json.dumps(dict(origins=origins, fov=FOV), indent=2)+'\n'); print(origins)


def capture(package):
    sys.path.insert(0, str(ROOT/'test-harness'))
    from harness import Controller
    package = Path(package); cfg = json.loads((package/'cubemaps.json').read_text()); c = Controller(); shots = {}
    c.command('ui', 'console', command='rui_drawEnable 0')  # the HUD is RUI; camera mode only hides the weapon
    try:
        for i, origin in enumerate(cfg['origins']):
            for name, angles in VIEWS.items():
                c.camera(origin, [angles[0], angles[1], 0], FOV, 3 if name == 'px' else 1.5)
                shots[f'{i}-{name}'] = c.capture(f'cubemap{i}-{name}')['path']
    finally:
        c.command('ui', 'console', command='rui_drawEnable 1')
    cfg['shots'] = shots; (package/'cubemaps.json').write_text(json.dumps(cfg, indent=2)+'\n')


def faces(shots, i):
    """Six linear-light FACE x FACE faces for cubemap i from its screenshots."""
    sys.path.insert(0, str(ROOT/'tools/lighting-python'))
    from PIL import Image
    images = {n: (np.asarray(Image.open(shots[f'{i}-{n}']).convert('RGB'), 'f4')/255)**2.2 for n in VIEWS}
    h, w = next(iter(images.values())).shape[:2]; focal = (h/2)/np.tan(np.radians(45))
    t = (np.arange(FACE)+.5)/FACE*2-1; u, v = np.meshgrid(t, t); out = []
    for face in range(6):
        d = face_direction(face, u, v).reshape(3, -1); best = np.full(d.shape[1], -2.); colour = np.zeros((d.shape[1], 3), 'f4')
        for name, (pitch, yaw) in VIEWS.items():
            f, r, up = basis(pitch, yaw); facing = f @ d; use = facing > best
            x = w/2+focal*(r @ d)/np.maximum(facing, 1e-6); y = h/2-focal*(up @ d)/np.maximum(facing, 1e-6)
            ok = use & (facing > 0) & (x >= 0) & (x < w) & (y >= 0) & (y < h)
            colour[ok] = images[name][y[ok].astype(int), x[ok].astype(int)]; best[ok] = facing[ok]
        out.append(colour.reshape(FACE, FACE, 3))
    return out


def dds_cube(face_list, path):
    """An R16G16B16A16_FLOAT cubemap DDS (DX10 header) of one mip, for texconv."""
    header = struct.pack('<4s7I44x2I4s5I', b'DDS ', 124, 0x1007, FACE, FACE, FACE*8, 0, 1, 32, 4, b'DX10', 0, 0, 0, 0, 0)
    header += struct.pack('<5I', 0x1000, 0x200 | 0xFC00, 0, 0, 0)  # caps: texture | cubemap (all faces)
    dx10 = struct.pack('<5I', 10, 3, 0x4, 1, 0)  # R16G16B16A16_FLOAT, 2D, TEXTURECUBE, one cube
    data = b''.join(np.concatenate((f, np.ones(f.shape[:2]+(1,), 'f4')), 2).astype('<f2').tobytes() for f in face_list)
    Path(path).write_bytes(header+dx10+data)


def bc6h_mips(face_list, work, i):
    """[face][mip] BC6H block bytes, mips largest first, from texconv."""
    src = work/f'cube{i}.dds'; dds_cube(face_list, src); (work/'bc6h').mkdir(exist_ok=True)
    subprocess.run([str(ROOT/'tools/directxtex/texconv.exe'), '-nologo', '-y', '-m', str(MIPS), '-f', 'BC6H_UF16', '-o', str(work/'bc6h'),
                    str(src)], check=True, capture_output=True)
    data = (work/'bc6h'/src.name).read_bytes(); at = 148; out = []
    for _ in range(6):
        mips = []
        for m in range(MIPS):
            n = max(1, (FACE >> m)//4)**2*16; mips.append(data[at:at+n]); at += n
        out.append(mips)
    if at != len(data):
        raise ValueError('Unexpected BC6H cubemap size')
    return out


def vtf(cubes, cma):
    frames = len(cubes); v = bytearray(b'VTF\0')
    v += struct.pack('<3I2HI2HI3fIfiBiBBH', 7, 5, 104, FACE, FACE, 0x420C, frames, 0, 0, .2, .2, .2, 0, 1., 66, MIPS, -1, 0, 0, 1)
    v += bytes(3)+struct.pack('<I', 3)+bytes(8)
    image = 104+(4+4*frames if frames > 1 else 0)
    v += b'0\0\0\0'+struct.pack('<I', image)
    v += (b'CMA\0'+struct.pack('<I', 104)) if frames > 1 else (b'CMA\x02'+struct.pack('<f', cma[0]))
    v += b'CRC\x02'+struct.pack('<I', 0)
    assert len(v) == 104
    if frames > 1:
        v += struct.pack(f'<I{frames}f', 4*frames, *cma)
    for mip in reversed(range(MIPS)):
        for cube in cubes:
            for face in range(6):
                v += cube[face][mip]
    return bytes(v)


def stored_zip(name, data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as z:
        z.comment = b'XZP1 0'.ljust(32, b'\0'); z.writestr(zipfile.ZipInfo(name), data)
    return buf.getvalue()


def write(package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp')); cfg = json.loads((package/'cubemaps.json').read_text())
    if 'written' in cfg:
        raise ValueError('Cubemaps already written')
    work = Path(os.environ.get('CUBEMAP_WORK', package))/'cubemap-work'; work.mkdir(parents=True, exist_ok=True)
    origins = np.asarray(cfg['origins']); cubes = [bc6h_mips(faces(cfg['shots'], i), work, i) for i in range(len(origins))]
    l = read_lumps(bsp, (0x28, 0x2A, 0x50, 0x51, 0x52))
    if l[0x28] or l[0x2A]:
        raise ValueError('The map already has cubemaps')
    meshes = bytearray(l[0x50]); centres = np.array([struct.unpack_from('<3f', l[0x51], i) for i in range(0, len(l[0x51]), 32)])
    assigned = 0
    for m, c in enumerate(centres):
        flags = struct.unpack_from('<I', meshes, m*28+24)[0]
        if flags & 0x600 == 0x400:  # unlit meshes reflect nothing
            continue
        struct.pack_into('<b', meshes, m*28+11, int(np.linalg.norm(origins-c, axis=1).argmin())); assigned += 1
    sorts = bytearray(l[0x52])
    for at in range(0, len(sorts), 12):  # retail material sorts all store cubemap 0
        struct.pack_into('<h', sorts, at+4, 0)
    name = f'materials/maps/{bsp.stem}/cubemaps.hdr.vtf'
    changes = {0x28: stored_zip(name, vtf(cubes, [1.]*len(origins))), 0x50: bytes(meshes), 0x52: bytes(sorts),
               0x2A: b''.join(struct.pack('<3iI', *np.rint(o).astype(int), 0) for o in origins)}
    temp = bsp.with_suffix('.cubemaps.bsp'); compact(bsp, temp, changes); os.replace(temp, bsp)
    cfg['written'] = dict(cubemaps=len(origins), meshes_assigned=assigned, pakfile_bytes=len(changes[0x28]))
    (package/'cubemaps.json').write_text(json.dumps(cfg, indent=2)+'\n'); print(json.dumps(cfg['written']))


if __name__ == '__main__':
    a = sys.argv[1:]
    {'plan': lambda: plan(a[1], *(int(x) for x in a[2:3])), 'capture': lambda: capture(a[1]), 'write': lambda: write(a[1])}[a[0]]()
