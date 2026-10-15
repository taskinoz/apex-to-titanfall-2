"""Party Crasher 0.5.1: source world-projected UVs and corrected blend overlays.

Apex "wld" shaders project albedo from world position: uv = (x, -y) . c_uvN.
The converted meshes kept raw world coordinates as UVs, so these textures
repeated every unit and averaged to flat grey/olive sheets. This rewrites
their UVs from the source shader constants (see classify_world_uv.py).

The b2t ("blend to transparent") rubble/dirt overlays were drawn opaque and
coplanar with floors and grass, causing z-fighting and white sheets. Their
source opacity is
    (1 - saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)) * albedo.a * c_opacity
where vertexAlpha is byte 3 of the real vertex colour. bsp_tool labels that
32-bit field `negative_one`; its `colour` field is packed tangent data. The
coverage is baked per triangle into an atlas drawn with the native world alpha
shader, lifted 0.35 units. Overlay triangles whose baked coverage is zero
everywhere are invisible in the source as well and are retired from rendering.
Collision, entities, lights and lightmap charts are unchanged; nothing is added.
"""
import argparse
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import numpy as np
from new_arena_ports import CONFIG, ROOT, folder, source_bsp
from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact
from build_composite_map import DT
from apply_baked_lighting import tangents
from repair_camera_visibility import build_camera_visibility
from repair_native_render_partitions import reorder

OUT = folder('party-crasher')
PROJECT = OUT/'surface-repair'
BACKUP = OUT/'before-0.5.1'
MAP = OUT/'mp_party_crasher.bsp'
OVERLAYS = ('rubble_standard02_wld_b2t_wld_01', 'icelandic_dirt_01_wld_b2t')
LIFT = .35
TILE, ATLAS = 48, 2048
VISIBLE = 2/255


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')


def snapshot():
    if BACKUP.exists():
        raise ValueError('Rollback already exists')
    BACKUP.mkdir(parents=True)
    for name in ('mp_party_crasher.bsp', 'mp_party_crasher.stbsp', 'scene.json', 'scene.npz',
                 'source-build.json', 'physics.json', 'physics.npz'):
        shutil.copy2(OUT/name, BACKUP/name)
    shutil.copytree(OUT/'materials', BACKUP/'materials')
    live = OUT/'materials/build/party_crasher_world.rpak'
    temp = live.with_suffix('.detached.rpak'); shutil.copy2(live, temp); os.replace(temp, live)


def keys(t):
    return np.sort(np.asarray(t, '<f4'), axis=1).reshape(-1, 9).copy().view('V36').reshape(-1)


def project(info, positions):
    """Source shader UV: (x, -y) . RotScale + Translate (party-crasher has no recentring)."""
    xy = np.stack((positions[..., 0], -positions[..., 1]), -1)
    return np.stack((xy @ np.asarray(info['rot_x'])+info['translate'][0],
                     xy @ np.asarray(info['rot_y'])+info['translate'][1]), -1).astype('f4')


def classification():
    table = json.loads((OUT/'world-uv-materials.json').read_text())
    world = {n: v for n, v in table.items() if v['kind'] == 'world' and not v.get('scroll')}
    if not set(OVERLAYS) <= set(world):
        raise ValueError('Overlay materials must be classified as world projected')
    return world


def source_alpha(triangles, material):
    """Byte 3 of the real source vertex colour (bsp_tool's `negative_one`)."""
    sys.path.insert(0, str(ROOT/'tools/bsp_tool'))
    import bsp_tool
    from bsp_tool.branches.respawn.titanfall import MeshFlags
    from scipy.spatial import cKDTree
    geo = bsp_tool.load_bsp(str(source_bsp('party-crasher'))).external
    pos, val = [], []
    for mesh in geo.MESHES:
        sort = geo.MATERIAL_SORTS[mesh.material_sort]
        name = geo.texture_data_surface_name(sort.texture_data).replace('\\', '/').rsplit('/', 1)[-1]
        if name != material:
            continue
        records = getattr(geo, (mesh.flags & MeshFlags.MASK_VERTEX).name)
        for index in geo.MESH_INDICES[mesh.first_mesh_index:mesh.first_mesh_index+mesh.num_triangles*3]:
            v = records[index+sort.vertex_offset]
            pos.append(list(geo.VERTICES[v.position_index]))
            val.append(np.array([v.negative_one], '<i4').view('u1')[3])
    distance, nearest = cKDTree(np.asarray(pos)).query(triangles[:, :, :3].reshape(-1, 3).astype('f8'))
    if distance.max() > .01:
        raise ValueError('Overlay corner without matching source vertex: '+material)
    return np.asarray(val, 'f4')[nearest].reshape(-1, 3)/255


def overlay_tiles(name, triangles, alpha, values, base, slot):
    """Per-triangle 32x32 source colour and coverage tiles."""
    from restore_banner_display_textures import image_dds
    from bake_terrain_transitions import sample
    folder_ = OUT/'legion/exported_files/materials'/name
    albedo = np.asarray(image_dds(folder_/(name+'_albedoTexture.dds')).convert('RGBA'))/255
    mask = np.asarray(image_dds(folder_/(name+'_layerBlendTexture.dds')).convert('RGBA'))/255
    ramp = values['c_layerBlendRamp'][0]; opacity = values['c_opacity'][0]
    yy, xx = np.mgrid[:TILE, :TILE]; inner = TILE-5
    b = np.stack([1-(xx-2)/inner-(yy-2)/inner, (xx-2)/inner, (yy-2)/inner], -1).reshape(-1, 3)
    b = np.maximum(b, 0); b /= b.sum(1)[:, None]
    colours, covers = [], []
    for i, t in enumerate(triangles):
        world = b @ t[:, :3]
        c = sample(albedo, project(base, world)); m = sample(mask, project(slot, world))[:, 0]
        coverage = (1-np.clip(ramp*m-ramp+(ramp+1)*(b @ alpha[i]), 0, 1))*c[:, 3]*opacity
        colours.append(np.clip(c, 0, 1)); covers.append(coverage)
    return np.asarray(colours), np.asarray(covers)


def write_atlas(name, colours, covers):
    from PIL import Image
    from bake_terrain_transitions import save_mips
    per_row = ATLAS//TILE
    if len(colours) > per_row*per_row:
        raise ValueError('Overlay atlas capacity exceeded: '+name)
    colour = np.zeros((ATLAS, ATLAS, 4), 'u1'); cover = np.zeros_like(colour)
    uv = np.empty((len(colours), 3, 2), 'f4')
    for i, (c, a) in enumerate(zip(colours, covers)):
        x, y = i % per_row*TILE, i//per_row*TILE
        rgb = np.rint(c*255).astype('u1'); rgb[:, 3] = 255
        colour[y:y+TILE, x:x+TILE] = rgb.reshape(TILE, TILE, 4)
        o = np.full((TILE*TILE, 4), 255, 'u1'); o[:, :3] = np.rint(a*255).astype('u1')[:, None]
        cover[y:y+TILE, x:x+TILE] = o.reshape(TILE, TILE, 4)
        uv[i] = np.array([[x+2.5, y+2.5], [x+TILE-2.5, y+2.5], [x+2.5, y+TILE-2.5]])/ATLAS
    target = OUT/'materials/assets/texture/party_crasher'
    for suffix, image in (('overlay_atlas', colour), ('overlay_coverage', cover)):
        save_mips(Image.fromarray(image), (target/(name+'_'+suffix)).with_suffix('.dds'))
    return uv


def patch():
    if (PROJECT/'surface-result.json').exists():
        raise ValueError('Already patched; restore before-0.5.1 to rebuild')
    if not BACKUP.exists():
        snapshot()
    PROJECT.mkdir(exist_ok=True)
    from apex_material_constants import ApexMaterials
    from classify_world_uv import albedo_source
    source = ApexMaterials(OUT/'paks'/(CONFIG['party-crasher']['source']+'.rpak'))
    world = classification()
    original = np.load(BACKUP/'scene.npz'); tri = original['triangles'].copy(); mi = original['material']
    names = [str(n) for n in original['names']]; original.close()
    orig_points = tri[:, :, :3].copy()
    retired = np.zeros(len(tri), bool); overlay_ids = {}; tile_uv = {}; report = {}
    for name in OVERLAYS:
        ids = np.flatnonzero(mi == names.index(name))
        values, _ = source.constants(name)
        ps = (OUT/'shader-inspection'/(name+'-ps.txt')).read_text(errors='replace')
        mask_slot = albedo_source(ps, 5)['slot']
        slot = dict(rot_x=values[f'c_uv{mask_slot}RotScaleX'], rot_y=values[f'c_uv{mask_slot}RotScaleY'],
                    translate=values[f'c_uv{mask_slot}Translate'])
        colours, covers = overlay_tiles(name, tri[ids], source_alpha(tri[ids], name), values, world[name], slot)
        visible = covers.max(1) >= VISIBLE
        retired[ids[~visible]] = True
        overlay_ids[name] = ids
        uv = write_atlas(name, colours[visible], covers[visible])
        tile_uv[name] = dict(zip(ids[visible].tolist(), uv))
        report[name] = dict(triangles=len(ids), visible=int(visible.sum()), retired=int((~visible).sum()),
                            ramp=values['c_layerBlendRamp'][0], mask_slot=mask_slot, albedo_slot=world[name]['slot'])
    for name, info in world.items():
        if name not in names:
            continue
        ids = np.flatnonzero(mi == names.index(name))
        if name in OVERLAYS:
            for tid, uv in tile_uv[name].items():
                n = tri[tid, :, 3:6]; n = n/np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
                tri[tid, :, 6:8] = uv; tri[tid, :, :3] += n*LIFT
        else:
            tri[ids, :, 6:8] = project(info, tri[ids, :, :3])
    lookup = {}
    for name, ids in overlay_ids.items():
        for j, k in zip(ids, keys(orig_points[ids])):
            lookup[k.tobytes()] = int(j)
    l = read_lumps(MAP, range(128)); buf = {k: bytearray(v) for k, v in l.items()}
    native = []
    for at in range(0, len(l[2]), 36):
        st = struct.unpack_from('<I', l[2], at+12)[0]; off = struct.unpack_from('<I', l[0x2c], st*4)[0]
        native.append(l[0x2b][off:l[0x2b].index(0, off)].decode().replace('\\', '/').rsplit('/', 1)[-1])
    sorts = list(struct.iter_unpack('<3hHI', l[0x52]))
    records = np.frombuffer(buf[0x49], DT).copy()
    positions = np.frombuffer(l[3], '<f4').reshape(-1, 3)
    normals = np.frombuffer(bytes(buf[0x1e]), '<f4').reshape(-1, 3)
    new_positions = []; keep = []; newindices = bytearray(); bounds = bytearray()
    rewritten = drawn = removed = 0
    for i, mesh in enumerate(struct.iter_unpack('<I3H6b2h2BHI', l[0x50])):
        sort = sorts[mesh[-2]]; name = native[sort[0]]
        local = np.frombuffer(l[0x4f], '<u2', mesh[1]*3, mesh[0]*2).reshape(-1, 3)
        record = list(mesh); box = l[0x51][i*32:i*32+32]
        if name in OVERLAYS:
            ix = local.astype('u4')+sort[-1]
            if len(np.unique(ix)) != ix.size:
                raise ValueError('Overlay mesh shares vertices between triangles: '+name)
            kept = []
            for face_local, face in zip(local, ix):
                pts = positions[records['pi'][face]]
                tid = lookup.get(keys(pts[None])[0].tobytes())
                if tid is None:
                    raise ValueError('Overlay face without scene source')
                if retired[tid]:
                    removed += 1; continue
                src = orig_points[tid]
                for vi, p in zip(face, pts):
                    corner = int(np.argmin(np.linalg.norm(src-p, axis=1)))
                    if np.linalg.norm(src[corner]-p) > .002:
                        raise ValueError('Overlay corner mismatch')
                    records['uv'][vi] = tile_uv[name][tid][corner]
                    n = normals[records['ni'][vi]]; n = n/max(np.linalg.norm(n), 1e-12)
                    # Lifted copies: never move a position shared with the floor.
                    records['pi'][vi] = len(positions)+len(new_positions); new_positions.append(p+n*LIFT)
                kept.append(face_local)
            if not kept:
                continue
            local = np.asarray(kept, '<u2'); record[1] = len(local); record[-1] |= 0x10
            struct.pack_into('<I', buf[2], sort[0]*36+32, struct.unpack_from('<I', buf[2], sort[0]*36+32)[0] | 0x10)
            drawn += len(local)
        elif name in world:
            for vi in np.unique(local.astype('u4')+sort[-1]):
                records['uv'][vi] = project(world[name], positions[records['pi'][vi]][None])[0]
            rewritten += len(local)
        if name in world:
            ix = local.reshape(-1).astype('u4')+sort[-1]
            allpos = np.concatenate((positions, np.asarray(new_positions, 'f4').reshape(-1, 3)))
            pts = allpos[records['pi'][ix]]
            tan, mir = tangents(pts.reshape(-1, 3, 3), normals[records['ni'][ix]].reshape(-1, 3, 3),
                                records['uv'][ix].reshape(-1, 3, 2))
            start = len(buf[0x1e])//12; buf[0x1e].extend(tan.astype('<f4').tobytes())
            records['tangent'][ix] = np.arange(start, start+len(ix), dtype='u4') | (mir.reshape(-1).astype('u4') << 31)
            if name in OVERLAYS:
                lo = pts.min(0)-.02; hi = pts.max(0)+.02; c = (lo+hi)/2; e = (hi-lo)/2
                box = struct.pack('<8f', *c, float(np.linalg.norm(e))+.02, *e, 0)
        record[0] = len(newindices)//2
        newindices.extend(local.tobytes())
        if record[1] & 1:
            newindices.extend(struct.pack('<3H', *[int(local[-1, -1])]*3))
        keep.append(struct.pack('<I3H6b2h2BHI', *record)); bounds.extend(box)
    positions = np.concatenate((positions, np.asarray(new_positions, 'f4').reshape(-1, 3)))
    buf[3] = bytearray(positions.astype('<f4').tobytes())
    buf[0x49] = bytearray(records.tobytes()); buf[0x4f] = newindices
    buf[0x50] = bytearray(b''.join(keep)); buf[0x51] = bounds
    count = len(keep); struct.pack_into('<2I', buf[0xe], 24, 0, count)
    # Overlays are translucent or retired: none casts an opaque static shadow.
    excluded = keys(orig_points[np.concatenate(list(overlay_ids.values()))])
    shv = np.frombuffer(l[0x7c], '<f4').reshape(-1, 3); newv = bytearray(); newix = bytearray(); newrec = bytearray()
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
    temp = MAP.with_suffix('.surfaces.bsp'); compact(MAP, temp, buf); os.replace(temp, MAP)
    np.savez(OUT/'scene.npz', triangles=tri, material=mi, names=names)
    np.savez(PROJECT/'retired.npz', mask=retired)
    scene = json.loads((OUT/'scene.json').read_text())
    scene['retired_triangle_ledger'] = np.flatnonzero(retired).tolist()
    scene['active_render_triangles'] = scene['triangles']-int(retired.sum())
    write(OUT/'scene.json', scene)
    write(PROJECT/'surface-result.json', dict(
        world_projected_materials={n: dict(slot=v['slot'], rot_x=v['rot_x'], rot_y=v['rot_y'], translate=v['translate'],
                                           triangles=v['triangles']) for n, v in world.items() if n not in OVERLAYS},
        rewritten_native_triangles=rewritten, overlays=report, overlay_triangles_drawn=drawn,
        retired_overlay_triangles=removed, lift=LIFT, visible_threshold=VISIBLE,
        coverage_equation='(1 - saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)) * albedo.a * c_opacity',
        vertex_alpha='byte 3 of the source vertex colour (bsp_tool field negative_one)',
        atlas=dict(size=ATLAS, tile=TILE), collision_unchanged=True, triangles_added=0))
    print('Rewrote', rewritten, 'triangles; overlays drawn', drawn, 'retired', removed, flush=True)


def materials():
    from bake_terrain_transitions import save_mips
    from PIL import Image
    mats = OUT/'materials'
    mapping = json.loads((mats/'mapping.json').read_text()); manifest = json.loads((mats/'build.json').read_text())
    files = {f['_path']: f for f in manifest['files']}
    template = mats/'assets/material/world/party_crasher/slum_grime_decal_01_bt_wld'
    spec0 = json.loads(template.with_suffix('.json').read_text()); uber = template.with_suffix('.uber').read_bytes()
    neutral = {}
    # Atlas UVs drive every channel; tiled normal/gloss maps would stretch.
    for slot, semantic, colour in (('1', 'normal', (128, 128, 255, 255)), ('2', 'gloss', (30, 30, 30, 255)),
                                   ('3', 'spec', (8, 8, 8, 255))):
        path = f'texture/party_crasher/overlay_neutral_{semantic}.rpak'
        save_mips(Image.new('RGBA', (4, 4), colour), (mats/'assets'/path).with_suffix('.dds')); neutral[slot] = path
    for name in OVERLAYS:
        r = mapping['materials'][name]
        textures = {'0': f'texture/party_crasher/{name}_overlay_atlas.rpak',
                    '13': f'texture/party_crasher/{name}_overlay_coverage.rpak', **neutral}
        for path in textures.values():
            files[path] = dict(_type='txtr', _path=path, **{'$disableStreaming': True})
        spec = dict(spec0, name=r['name'], width=ATLAS, height=ATLAS, surfaceProp='gravel')
        spec['$textures'] = textures; spec['$colpassMaterial'] = '0x0'
        path = 'material/'+r['name']+'_wld.rpak'
        (mats/'assets'/path).with_suffix('.json').write_text(json.dumps(spec, indent=2))
        (mats/'assets'/path).with_suffix('.uber').write_bytes(uber)
        files[path] = dict(_type='matl', _path=path)
        r.update(textures=textures, transparent=True,
                 native_source_channels='Source b2t colour and coverage baked per triangle; world alpha shader')
    manifest['files'] = sorted(files.values(), key=lambda f: f['_type'] != 'txtr')
    write(mats/'build.json', manifest); write(mats/'mapping.json', mapping)
    import subprocess
    run = subprocess.run([str(ROOT/'tools/repak/RePak.exe'), str(mats/'build.json')], capture_output=True, text=True)
    (PROJECT/'material-build.log').write_text(run.stdout+run.stderr); run.check_returncode()
    if 'ERROR' in run.stdout+run.stderr:
        raise ValueError('RePak reported an error')
    from build_preview_stbsp import build
    build(OUT, mats, 'mp_party_crasher', 'party_crasher_world')
    write(PROJECT/'material-result.json', dict(overlays=list(OVERLAYS), all_other_materials_retained=True))


def stage():
    """Copy the accepted 0.5.0 mod and swap only the rebuilt map/STBSP/world pack."""
    from map_pack_lifetime import audit as pack_audit
    from new_arena_ports import WORK
    from package_player_mods import digest
    accepted = ROOT/'northstar/ArenaPartyCrasher'
    if json.loads((accepted/'mod.json').read_text())['Version'] != '0.5.0':
        raise ValueError('Unexpected accepted baseline version')
    if digest(BACKUP/'mp_party_crasher.bsp') != digest(accepted/'mod/maps/mp_party_crasher.bsp'):
        raise ValueError('Snapshot is not the accepted 0.5.0 payload')
    if not (PROJECT/'binary-validation.json').exists():
        raise ValueError('Run verify_party_surfaces.py first')
    candidate = WORK/'surface-candidates'/'ArenaPartyCrasher'
    if candidate.exists():
        shutil.rmtree(candidate)
    shutil.copytree(accepted, candidate)
    for relative, src in (('mod/maps/mp_party_crasher.bsp', MAP),
                          ('mod/maps/mp_party_crasher.stbsp', OUT/'mp_party_crasher.stbsp'),
                          ('paks/party_crasher_world.rpak', OUT/'materials/build/party_crasher_world.rpak')):
        shutil.copy2(src, candidate/relative)
        if digest(src) != digest(candidate/relative):
            raise ValueError('Staged payload differs: '+relative)
    mod = json.loads((candidate/'mod.json').read_text()); mod['Version'] = '0.5.1'
    (candidate/'mod.json').write_text(json.dumps(mod, indent=2))
    pack_audit(candidate/'paks', 'mp_party_crasher')
    print('Staged', candidate, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['patch', 'materials', 'stage'])
    dict(patch=patch, materials=materials, stage=stage)[p.parse_args().action]()
