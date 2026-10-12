"""Compare actual source/target map records without writing a converted BSP."""
import argparse
import collections
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
import bsp_tool
from bsp_tool.branches.respawn import titanfall2


def raw_lump(bsp, name):
    h = bsp.headers[name]
    index = bsp.branch.LUMP[name].value
    sidecar = Path(bsp.folder) / f'{bsp.filename}.{index:04x}.bsp_lump'
    if sidecar.is_file():
        return sidecar.read_bytes()
    if not h.length:
        return b''
    bsp.file.seek(h.offset)
    data = bsp.file.read(h.length)
    if len(data) != h.length:
        raise ValueError(f'Truncated {name}')
    return data


def schema(branch, name, version):
    for kind in ('LUMP_CLASSES', 'BASIC_LUMP_CLASSES', 'SPECIAL_LUMP_CLASSES'):
        cls = getattr(branch, kind, {}).get(name, {}).get(version)
        if cls is not None:
            fmt = getattr(cls, '_format', None)
            return dict(kind=kind, type=cls.__name__, format=fmt,
                        record_bytes=struct.calcsize('<' + fmt) if fmt else None,
                        fields=list(getattr(cls, '__slots__', [])))
    return dict(kind='raw/unsupported', type=None, format=None, record_bytes=None, fields=[])


def audit(source, reference):
    src, ref = [bsp_tool.load_bsp(str(p.resolve())) for p in (source, reference)]
    if ref.version != 37:
        raise ValueError('Reference must be a Titanfall 2 v37 BSP')
    rows = []
    for lump in src.branch.LUMP:
        data = raw_lump(src, lump.name)
        if not data:
            continue
        source_schema = schema(src.branch, lump.name, src.headers[lump.name].version)
        target_enum = titanfall2.LUMP(lump.value)
        target_name = target_enum.name
        target_schema = schema(titanfall2, target_name, ref.headers[target_name].version)
        same_name = target_name == lump.name
        same_layout = same_name and source_schema['format'] is not None and all(
            source_schema[k] == target_schema[k] for k in ('format', 'fields'))
        rows.append(dict(index=lump.value, source=lump.name, target_slot=target_name,
                         bytes=len(data), source_version=src.headers[lump.name].version,
                         reference_version=ref.headers[target_name].version,
                         source_schema=source_schema, target_schema=target_schema,
                         classification=('matching_record_layout_needs_semantic_checks' if same_layout
                                         else 'different_record_layout' if same_name else 'repurposed_slot')))
    types = {0:'BVH_NODE',1:'NO_CHILD',2:'UNUSED_2',3:'UNKNOWN_3',4:'TRI_REGULAR',
             5:'TRI_PACKED',6:'QUAD_REGULAR',7:'QUAD_PACKED',8:'STAR_COLL',9:'STATIC_PROP'}
    counts = collections.Counter()
    node_data = raw_lump(src, 'BVH_NODES')
    invalid_active_bounds = 0
    invalid_references = []
    leaf_words = len(raw_lump(src, 'BVH_LEAF_DATA')) // 4
    masks = len(raw_lump(src, 'CONTENTS_MASKS')) // 4
    node_count = len(node_data) // 64
    for node_index, node in enumerate(struct.iter_unpack('<24h4I', node_data)):
        if node[24] & 255 >= masks:
            invalid_references.append(dict(node=node_index, error='contents mask index out of range'))
        # Map BVHs store four minima followed by four maxima per axis.
        # Child types occupy the low byte; child 0 and 2 use its low nibble.
        for child, (shift, word) in enumerate(((0,node[26]),(4,node[26]),(0,node[27]),(4,node[27]))):
            value = (word >> shift) & 15
            counts[types.get(value, f'UNKNOWN_{value}')] += 1
            index = node[24 + child] >> 8
            if value != 1:
                invalid_active_bounds += sum(node[axis*8+child] > node[axis*8+4+child] for axis in range(3))
            if value == 0 and index >= node_count or 3 <= value <= 8 and index >= leaf_words:
                invalid_references.append(dict(node=node_index, child=child, type=value, index=index))
    required = [l.name for l in titanfall2.LUMP if l.name.startswith(('CM_', 'TRICOLL_'))]
    return dict(source=str(source.resolve()), reference=str(reference.resolve()),
                source_version=src.version, target_version=ref.version, lump_comparison=rows,
                collision_child_types=dict(counts), target_collision_lumps_to_build=required,
                collision_structure_validation=dict(nodes=node_count, invalid_active_axis_bounds=invalid_active_bounds,
                                                    invalid_references=invalid_references),
                warnings=['Equal record layouts do not establish cross-engine compatibility.',
                          'BVH types are interpreted using bsp_tool, not validated engine trace results.',
                          'No converted or playable map is produced.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/compatibility.json'))
    args = parser.parse_args()
    result = audit(args.source, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Lump layouts:',dict(collections.Counter(r['classification'] for r in result['lump_comparison'])))
    print('Collision types:',result['collision_child_types'])
    print('Saved',args.output.resolve())
