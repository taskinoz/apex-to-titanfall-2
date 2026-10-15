"""Append source props into lightmap tiles released by retired meshes.

recover_composite_details.append gives each new triangle the next 4x4 tile
after the scene ledger, so it stops when the fourth lightmap page is full.
Every native triangle owns exactly one 4x4 tile (verified: unique ordinals
page*262144 + row*512 + column), so tiles of triangles that are no longer
drawn (retired overlays, hidden meshes) are free. This variant allocates new
triangles to any unused tile on any page, splits material-sort chunks per page,
and bakes each page's new charts separately against the full caster ledger.
Everything else follows the original append.
"""
import json
import os
import struct
import subprocess
from pathlib import Path

import numpy as np
import recover_composite_details as recovery
from recover_composite_details import JOB, ROOT
from repair_preview_index_padding import read_lumps, validate_index_padding
from compact_preview_bsp import compact
from build_composite_map import DT
from apply_baked_lighting import tangents, encode_rgbm
from spatial_preview_meshes import partition
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder
from audit_world_draw_budget import enforce_camera_bypass_budget

PAGES, PER_PAGE = 4, 512*512


def used_tiles(bsp, max_vertex=None):
    """Tile ordinals of drawn triangles; optionally only vertex records below max_vertex."""
    l = read_lumps(bsp, (0x49, 0x4f, 0x50, 0x52)); rec = np.frombuffer(l[0x49], DT)
    sorts = list(struct.iter_unpack('<3hHI', l[0x52])); used = []
    for mesh in struct.iter_unpack('<I3H6b2h2BHI', l[0x50]):
        sort = sorts[mesh[-2]]
        if max_vertex is not None and sort[-1] >= max_vertex:
            continue
        ix = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).astype('u4')+sort[-1]
        uv = rec['light'][ix][:, :2].reshape(-1, 3, 2)*2048; t = np.floor(uv.min(1)/4).astype(np.int64)
        used.append(sort[1]*PER_PAGE+t[:, 1]*512+t[:, 0])
    used = np.concatenate(used)
    if len(np.unique(used)) != len(used):
        raise ValueError('Lightmap tiles are shared; the one-tile-per-triangle layout does not hold')
    return used


def free_tiles(bsp):
    return np.setdiff1d(np.arange(PAGES*PER_PAGE, dtype=np.int64), used_tiles(bsp))


def patch_page(buf, jobs, work, page):
    from light_composite import LOCAL
    from scipy.ndimage import distance_transform_edt
    values = np.fromfile(work/f'sun{page}.bin', '<f4').reshape(2048, 2048, 5)
    local = np.fromfile(work/f'local{page}.bin', LOCAL).reshape(2048, 2048)
    mask = np.fromfile(work/f'sun{page}.bin.mask', 'u1').reshape(2048, 2048)
    sky = np.frombuffer(buf[0x62], 'u1').reshape(PAGES, 2, 2048, 2048, 4)
    offset = page*(2048*2048*8+1024*1024*4)
    ids = np.ndarray((2048, 2048), '<u4', buffer=buf[0x69], offset=offset)
    vis = np.ndarray((2048, 2048, 4), 'u1', buffer=buf[0x69], offset=offset+2048*2048*4)
    for job in jobs:
        x = int(job['uv'][0, 0]//4)*4; y = int(job['uv'][0, 1]//4)*4
        valid = mask[y:y+4, x:x+4].astype(bool)
        if not valid.any():
            raise ValueError('New chart has no baked receiver pixels')
        nearest = distance_transform_edt(~valid, return_distances=False, return_indices=True)
        v = values[y:y+4, x:x+4][tuple(nearest)]; loc = local[y:y+4, x:x+4][tuple(nearest)]
        ambient = np.array([.09, .10, .12])*(.65+.35*np.maximum(v[..., 1, None], 0))+loc['fill']
        sky[page, 0, y:y+4, x:x+4] = encode_rgbm(ambient)
        bent = np.empty((4, 4, 4), 'u1'); bent[..., :3] = np.rint(np.clip((v[..., 2:5]+1)/2.007874, 0, 1)*255).astype('u1'); bent[..., 3] = 255
        sky[page, 1, y:y+4, x:x+4] = bent
        ids[y:y+4, x:x+4] = loc['ids']; vis[y:y+4, x:x+4] = loc['vis']; vis[y:y+4, x:x+4, 0] = np.rint(v[..., 0]*255).astype('u1')


def append(bake_base, index_fraction, sun_executable, sun_direction):
    """recovery.OUT/WORK/MAP/BACKUP must be configured as for recovery.append."""
    OUT, WORK, MAP, BACKUP = recovery.OUT, recovery.WORK, recovery.MAP, recovery.BACKUP
    if (WORK/'result.json').exists():
        raise ValueError('Details already applied; restore the snapshot and clear the receipt before reapplying')
    a = np.load(WORK/'addition.npz'); data = a['triangles']; mi = a['material']; names = list(a['names']); col = a['collision']; a.close()
    plan = json.loads((WORK/'plan.json').read_text()); oldscene = json.loads((BACKUP/'scene.json').read_text())
    free = free_tiles(MAP)
    if len(free) < len(data):
        raise ValueError(f'Only {len(free)} free lightmap tiles for {len(data)} triangles')
    lids = (0, 1, 2, 3, 0xe, 0x18, 0x1e, 0x2b, 0x2c, 0x36, 0x42, 0x44, 0x45, 0x49, 0x4f, 0x50, 0x51, 0x52, 0x53, 0x5c, 0x60, 0x61, 0x62,
            0x64, 0x69, 0x77, 0x78, 0x79, 0x7b, 0x7c, 0x7e, 0x7f, 5)
    l = read_lumps(MAP, lids); buf = {k: bytearray(v) for k, v in l.items()}
    mapping = json.loads((OUT/'materials/mapping.json').read_text())['materials']
    native_names = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        native_names.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/'))
    cursor = 0; jobs = {p: [] for p in range(PAGES)}; ordered = []; casters = []
    for ti, name in enumerate(names):
        rec = mapping[name]; native = rec['name']; alpha = rec['transparent']
        if native in native_names:
            material = native_names.index(native)
        else:
            material = len(native_names); native_names.append(native); st = len(buf[0x2c])//4
            buf[0x2c].extend(struct.pack('<I', len(buf[0x2b]))); buf[0x2b].extend(native.replace('/', '\\').encode()+b'\0')
            buf[2].extend(struct.pack('<3f6I', 0, 0, 0, st, 1024, 1024, 0, 0, 0xa00 | (0x10 if alpha else 0)))
        selected = data[mi == ti]; at = 0
        while at < len(selected):
            # One material sort per page: take the run of free tiles on one page.
            page = int(free[cursor]//PER_PAGE); n = min(10000, len(selected)-at)
            run = free[cursor:cursor+n]; n = int(np.sum(run//PER_PAGE == page)); run = run[:n]
            src = selected[at:at+n]; at += n; cursor += n
            p = src[:, :, :3]; normal = src[:, :, 3:6]; uv = src[:, :, 6:8]; tan, mirror = tangents(p, normal, uv)
            normal = normal/np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-12)
            pi = len(buf[3])//12; ni = len(buf[0x1e])//12; base = len(buf[0x49])//44
            buf[3].extend(p.astype('<f4').tobytes()); nb = np.empty((n*6, 3), '<f4'); nb[::2] = normal.reshape(-1, 3); nb[1::2] = tan.reshape(-1, 3)
            buf[0x1e].extend(nb.tobytes())
            records = np.zeros(n*3, DT); records['pi'] = np.arange(pi, pi+n*3); records['ni'] = np.arange(ni, ni+n*6, 2)
            records['uv'] = uv.reshape(-1, 2); records['color'] = 255
            records['tangent'] = np.arange(ni+1, ni+n*6, 2, dtype=np.uint32) | (mirror.reshape(-1).astype('u4') << 31)
            if src.shape[2] >= 12:
                records['color'] = np.rint(np.clip(src[:, :, 8:12], 0, 255)).astype('u1').reshape(-1, 4)
            tile = run % PER_PAGE
            cuv = np.stack((tile % 512, tile//512), 1)[:, None, :]*4+np.array([[.5, .5], [3.2, .5], [.5, 3.2]])
            records['light'][:, :2] = (cuv/2048).reshape(-1, 2); buf[0x49].extend(records.tobytes())
            job = np.zeros(n, JOB); job['p'] = p; job['n'] = normal; job['uv'] = cuv; job['page'] = 0
            jobs[page].append(job); ordered.append(src); casters.append(np.full(n, not alpha, 'u1'))
            local = np.arange(n*3, dtype='<u2').reshape(-1, 3)
            front = np.sum(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0])*normal.sum(1), axis=1) > 0; local[front] = local[front][:, [0, 2, 1]]
            si = len(buf[0x52])//12; buf[0x52].extend(struct.pack('<3hHI', material, page, -1, n*3-1, base))
            for ixids in partition(p.mean(1), np.arange(n), limit=512):
                ix = local[ixids]; pts = p[ixids].reshape(-1, 3); lo = pts.min(0)-.02; hi = pts.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
                buf[0x50].extend(struct.pack('<I3H6b2h2BHI', len(buf[0x4f])//2, len(ix), int(ix.min()), int(ix.max()-ix.min()), 2, -1, -1, -1, -1, -1, -1, -1,
                                             255, 255, si, 0x100a00 | (0x10 if alpha else 0)))
                buf[0x4f].extend(ix.tobytes())
                if len(ix) & 1:
                    buf[0x4f].extend(struct.pack('<3H', *[int(ix[-1, -1])]*3))
                buf[0x51].extend(struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0))
            if not alpha:
                buf[0x7f].extend(struct.pack('<2I2h', len(buf[0x7c])//12, n, 1, -1)); buf[0x7c].extend(p.astype('<f4').tobytes())
                buf[0x7e].extend(local.tobytes())
    ordered = np.concatenate(ordered); casts = np.concatenate(casters)
    bake_base = Path(bake_base)
    oldtri = np.fromfile(bake_base/'bake-triangles.bin', '<f4').reshape(-1, 3, 3); oldcast = np.fromfile(bake_base/'bake-casters.bin', 'u1')
    if len(oldtri) != oldscene['triangles']:
        raise ValueError('Bake caster snapshot does not cover the current scene')
    np.concatenate((oldtri, ordered[:, :, :3])).astype('<f4').tofile(WORK/'bake-triangles.bin')
    np.concatenate((oldcast, casts)).tofile(WORK/'bake-casters.bin')
    env = dict(os.environ); mingw = Path('C:/ProgramData/mingw64/mingw64/bin')
    if mingw.is_dir():
        env['PATH'] = str(mingw)+os.pathsep+env.get('PATH', '')
    for page in range(PAGES):
        if not jobs[page]:
            continue
        pj = np.concatenate(jobs[page])
        # Only this page's new charts receive texels; every other triangle occludes.
        alljobs = np.zeros(len(oldtri)+len(ordered), JOB); alljobs['uv'] = -10
        offsets = np.cumsum([0]+[len(j) for p2 in range(PAGES) for j in jobs[p2]])
        k = 0
        for p2 in range(PAGES):
            for j in jobs[p2]:
                if p2 == page:
                    alljobs[len(oldtri)+offsets[k]:len(oldtri)+offsets[k]+len(j)] = j
                k += 1
        alljobs.tofile(WORK/f'bake-jobs{page}.bin')
        for exe, args in [(sun_executable, [WORK/'bake-triangles.bin', WORK/f'bake-jobs{page}.bin', WORK/f'sun{page}.bin', 2048, 2048, 1,
                                            WORK/'bake-casters.bin', *sun_direction]),
                          ('bake_interior_lighting.exe', [WORK/'bake-triangles.bin', WORK/f'bake-jobs{page}.bin', OUT/'fixtures.bin',
                                                          WORK/f'local{page}.bin', 2048, 2048, 1, WORK/'bake-casters.bin'])]:
            subprocess.run([str(ROOT/'tools'/exe) if not Path(exe).is_absolute() else exe, *map(str, args)], check=True, env=env)
        patch_page(buf, pj, WORK, page)
    recovery.append_collision(buf, col)
    count = len(buf[0x50])//28; struct.pack_into('<2I', buf[0xe], 24, 0, count)
    buf[0x77], buf[0x78], buf[0x79] = map(bytearray, build_camera_visibility(buf[0x51], np.arange(count, dtype='<u2').tobytes()))
    struct.pack_into('<3I', buf[0x7b], 0, count, count, count)
    shadow_count = len(buf[0x7f])//12
    for at in (0, 36):
        struct.pack_into('<i', buf[5], at+20, shadow_count)
    struct.pack_into('<i', buf[5], 36+8, shadow_count)
    buf.update(reorder(buf)[0]); validate_index_padding(buf[0x50], buf[0x4f], buf[0x52])
    temp = MAP.with_suffix('.details.bsp'); compact(MAP, temp, buf); proof = enforce_camera_bypass_budget(temp)
    if proof['native_padded_indices'] >= 3145728*index_fraction or proof['static_batch_runs'] >= 512:
        raise ValueError('Conservative budget exceeded')
    os.replace(temp, MAP)
    recovery.persist_scene(data, mi, names, plan)
    previous = json.loads((BACKUP/'source-build.json').read_text())['version']
    plan.update(draw_budget=proof, previous_version=previous,
                lighting='New 4x4 charts in released tiles, ray-baked per page against the full caster ledger',
                pages_used={p: int(sum(len(j) for j in jobs[p])) for p in range(PAGES) if jobs[p]})
    (WORK/'result.json').write_text(json.dumps(plan, indent=2))
    print(json.dumps(dict(added_props=plan['added_props'], added_triangles=plan['added_triangles'], pages=plan['pages_used'],
                          occupancy=round(proof['native_padded_indices']/3145728*100, 3)), indent=2), flush=True)
