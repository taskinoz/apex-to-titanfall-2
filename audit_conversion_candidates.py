"""Read-only source-map feasibility audit; does not build or install a port."""
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
import bsp_tool
from extract_map import RespawnVpk, extract
from plan_arena_fill import model_index

GAME = Path('D:/Games/R5Reloaded/R5R Library/LIVE')
MAPS = {
    'party-crasher': ('Party Crasher', 'mp_rr_party_crasher'),
    'overflow': ('Overflow', 'mp_rr_aqueduct'),
    'arena-empty': ('Arena Empty (SDK environment)', 'mp_rr_arena_empty'),
    'firing-range': ('Firing Range', 'mp_rr_canyonlands_staging'),
}


def audit_large_maps():
    """Read only the BSP header and world-mesh records, not BR prop assets."""
    rows = []
    dest = ROOT / 'inputs/candidates/large-map-meshes'
    for name in ('mp_rr_canyonlands_mu2', 'mp_rr_desertlands_mu2', 'mp_rr_olympus'):
        index = GAME / 'vpk' / ('englishclient_' + name + '.bsp.pak000_dir.vpk')
        extract(index, dest, 'maps/' + name + '.bsp')
        extract(index, dest, 'maps/' + name + '.bsp.0050.bsp_lump')
        header = (dest / 'maps' / (name + '.bsp')).read_bytes()
        if header[:4] != b'rBSP' or struct.unpack_from('<I', header, 4)[0] != 47:
            raise ValueError('Large-map mesh schema needs explicit version support')
        data = (dest / 'maps' / (name + '.bsp.0050.bsp_lump')).read_bytes()
        records = list(struct.iter_unpack('<IH8hHI', data))
        triangles = sum(m[1] for m in records)
        padded = sum(m[1] * 3 + (m[1] % 2) * 3 for m in records)
        rows.append(dict(map=name, bsp_version=47, meshes=len(records), triangles=triangles,
            padded_indices=padded, fraction_native_world_capacity=padded / 3145728,
            scope='All source world mesh records only; props excluded',
            crc_verified=True, mesh_sha256=hashlib.sha256(data).hexdigest()))
    out = ROOT / 'docs/candidates'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'large-map-brush-audit.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    return rows


def lod_counts(folder):
    data = (folder / (folder.name + '.vg')).read_bytes()
    if struct.unpack_from('<2I', data) != (0x47567430, 1):
        raise ValueError('Unsupported VG format')
    h = struct.unpack_from('<18Q', data, 16)
    result = []
    for i in range(h[13]):
        first, count, distance = struct.unpack_from('<2hf', data, h[12] + i * 8)
        if first < 0 or count < 0 or first + count > h[3]:
            raise ValueError('Invalid VG mesh range')
        triangles = sum(struct.unpack_from('<I', data, h[2] + j * 72 + 36)[0] // 3
                        for j in range(first, first + count))
        result.append(triangles)
    return result


def main():
    available = model_index()
    archive_rows = []
    for path in sorted((GAME / 'vpk').glob('englishclient_mp_rr_*_dir.vpk')):
        archive = RespawnVpk.from_file(str(path))
        name = path.name.removeprefix('englishclient_').split('.bsp')[0]
        archive_rows.append(dict(map=name, client_vpk=True,
            server_vpk=path.with_name(path.name.replace('englishclient_', 'englishserver_')).exists(),
            map_rpak=(GAME / 'paks/Win64' / (name + '.rpak')).exists(),
            bsp=any(p == 'maps/' + name + '.bsp' for p in archive.namelist()),
            archive_files=len(archive.namelist())))
    reports = []
    for ident, (label, name) in MAPS.items():
        source = ROOT / 'inputs/candidates' / ident / 'maps' / (name + '.bsp')
        bsp = bsp_tool.load_bsp(str(source))
        geo = bsp.external
        if geo.loading_errors:
            raise ValueError(str(geo.loading_errors))
        sprp_override = False
        if not hasattr(geo.GAME_LUMP.sprp, 'props') and geo.GAME_LUMP.headers['sprp'].version == 51:
            # The pinned branch registers this exact parser for sprp 51 in
            # apex_legends51.py. This SDK BSP has a v47 outer header instead.
            from bsp_tool.branches.respawn.apex_legends import GameLump_SPRP
            geo.GAME_LUMP.sprp = GameLump_SPRP.from_bytes(bytes(geo.GAME_LUMP.sprp))
            sprp_override = True
        sprp_supported = hasattr(geo.GAME_LUMP.sprp, 'props')
        props = geo.GAME_LUMP.sprp.props if sprp_supported else []
        names = geo.GAME_LUMP.sprp.model_names if sprp_supported else []
        counts = collections.Counter(names[p.model_name] for p in props)
        reuse = []
        for model, count in counts.most_common():
            folder = available.get(Path(model).stem.lower())
            row = dict(model=model, placements=count, already_exported=folder is not None)
            if folder:
                try:
                    lods = lod_counts(folder)
                    row.update(lod_triangles=lods, proposed_lod=min(3, len(lods) - 1),
                               estimated_triangles=count * lods[min(3, len(lods) - 1)])
                except (OSError, ValueError, struct.error) as error:
                    row['error'] = str(error)
            reuse.append(row)
        brush = sum(m.num_triangles for m in geo.MESHES)
        mins = [min(p.origin[i] for p in props) for i in range(3)] if props else None
        maxs = [max(p.origin[i] for p in props) for i in range(3)] if props else None
        main = geo.MODELS[0]
        entity_counts = {}
        for path in sorted(source.parent.glob(name + '*')):
            if path.suffix == '.ent' or path.name.endswith('.0000.bsp_lump'):
                import re
                text = path.read_bytes().decode('utf-8', 'replace')
                entity_counts[path.name] = dict(collections.Counter(re.findall(r'"classname"\s*"([^"\n]*)"', text)))
        index_floor = sum(m.num_triangles * 3 + (m.num_triangles % 2) * 3 for m in geo.MESHES)
        reports.append(dict(id=ident, name=label, source_map=name, bsp_version=bsp.version,
            bsp_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            extraction='CRC-verified client VPK maps/*; original game unchanged',
            parsing_errors=[], brush_models=len(geo.MODELS), brush_meshes=len(geo.MESHES),
            brush_triangles=brush, padded_brush_indices=index_floor,
            brush_fraction_native_world_capacity=index_floor / 3145728,
            native_capacity=3145728, conservative_target_fraction=.95,
            conservative_indices_remaining_before_props=int(3145728 * .95) - index_floor,
            world_bounds=dict(min=list(main.mins), max=list(main.maxs)),
            placement_origin_bounds=dict(min=mins, max=maxs),
            static_prop_schema_supported=sprp_supported,
            static_prop_parser_override=sprp_override,
            sprp_version=geo.GAME_LUMP.headers['sprp'].version,
            static_placements=len(props) if sprp_supported else None,
            unique_static_models=len(counts) if sprp_supported else None,
            solid_modes=dict(collections.Counter(p.solid_mode.value for p in props)),
            raw_static_flags=dict(collections.Counter(int(p.flags) for p in props)),
            already_exported_models=sum(r['already_exported'] for r in reuse),
            already_exported_placements=sum(r['placements'] for r in reuse if r['already_exported']),
            known_lod3_or_last_prop_triangles=sum(r.get('estimated_triangles', 0) for r in reuse),
            bvh_nodes=len(geo.BVH_NODES), bvh_leaf_words=len(geo.BVH_LEAF_DATA),
            materials=len(geo.SURFACE_NAMES), entity_class_counts=entity_counts, models=reuse))
        print(label, json.dumps({k: reports[-1][k] for k in
            ('bsp_version', 'brush_triangles', 'static_placements', 'unique_static_models',
             'already_exported_models', 'already_exported_placements',
             'brush_fraction_native_world_capacity', 'known_lod3_or_last_prop_triangles')}))
        bsp.file.close()
    result = dict(date='2026-10-13', available_maps=archive_rows, candidates=reports,
        limitations=[
            'Source brush geometry only is compared with the measured TF2 all-visible native world index capacity.',
            'World bounds include sky and remote areas; they are not the playable arena footprint.',
            'All source placements include remote/background and potentially collision proxies; source flags need engine-specific interpretation.',
            'Existing exports are a reuse opportunity, not proof that complete source assets or physics are recovered.',
            'Known prop cost excludes unexported models, collision, materials, lighting and menu stage.',
            'A 95 percent target is a conservative project policy; entity/AI/navigation budgets are separate.',
            'No port, native collision guarantee, performance guarantee or Titan clearance test is produced.'])
    out = ROOT / 'docs/candidates'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'source-audit-2026-10-13.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    audit_large_maps()


if __name__ == '__main__':
    main()
