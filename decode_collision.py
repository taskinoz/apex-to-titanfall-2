"""Recover regular world BVH polygons for inspection, not a playable TF2 map.

Leaf layouts follow r-ex/rsx's published bvh decoder. Map nodes use the
grouped-axis layout verified by audit_compatibility.py. Packed geometry and
prop leaves are explicitly reported rather than guessed.
"""
import argparse
import collections
import json
import struct
from pathlib import Path


def decode(path, output, vertex_offset=None,label_surfaces=False):
    def lump(index):
        return path.with_name(f'{path.name}.{index:04x}.bsp_lump').read_bytes()
    nodes = list(struct.iter_unpack('<24h4I', lump(18)))
    leafs = lump(19)
    vertices = list(struct.iter_unpack('<3f', lump(3)))
    masks = [v[0] for v in struct.iter_unpack('<I', lump(16))]
    properties=list(struct.iter_unpack('<h2bI',lump(17))) if label_surfaces else []
    names=lump(15) if label_surfaces else b''
    world = struct.unpack_from('<6f2I4i4f', lump(14))
    if vertex_offset is None:
        vertex_offset = world[10]
    root, leaf_base = world[8:10]
    origin, scale = world[12:15], world[15] * 65535
    if leaf_base != 0:
        raise ValueError('Only the world root with a zero leaf base is supported')
    pending = [(0, root, 0, None)]
    visited = set()
    compound_seen = set()
    shared_nodes = 0
    counts, skipped = collections.Counter(), collections.Counter()
    faces = bounds_checked = bounds_mismatches = 0
    errors = []
    def word(index):
        if not 0 <= index < len(leafs)//4:
            raise ValueError(f'Leaf word {index} outside data')
        return struct.unpack_from('<I', leafs, index*4)[0]
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'world-collision-regular.obj'
    with target.open('w', encoding='utf-8') as stream:
        stream.write('# Experimental regular BVH polygons; packed and static prop leaves excluded.\n')
        while pending:
            kind, index, contents, bounds = pending.pop()
            counts[str(kind)] += 1
            try:
                if kind == 1:
                    continue
                if kind == 0:
                    if index in visited:
                        shared_nodes += 1
                        continue
                    visited.add(index)
                    n = nodes[index]
                    mask = masks[n[24] & 255]
                    types = (n[26]&15, n[26]>>4&15, n[27]&15, n[27]>>4&15)
                    for child in range(3,-1,-1):
                        box = tuple((n[axis*8+child]*scale+origin[axis],
                                     n[axis*8+4+child]*scale+origin[axis]) for axis in range(3))
                        pending.append((types[child],n[24+child]>>8,mask,box))
                elif kind == 3:
                    if index in compound_seen:
                        continue
                    compound_seen.add(index)
                    count = word(index)
                    if not 0 < count <= 256:
                        raise ValueError(f'Invalid compound leaf count {count} at {index}')
                    cursor = index + 1 + count
                    for j in range(count):
                        desc = word(index+1+j)
                        mask_index, primitive, length = desc&255, desc>>8&255, desc>>16
                        if not length or cursor + length > len(leafs)//4:
                            raise ValueError('Compound leaf extends outside data')
                        if primitive in (0,1,2) or primitive > 9:
                            raise ValueError(f'Unexpected compound primitive type {primitive}')
                        pending.append((primitive,cursor,masks[mask_index],bounds))
                        cursor += length
                elif kind in (4,6):
                    header = word(index)
                    count, base = (header>>12&15)+1, (header>>16)<<10
                    for j in range(count):
                        encoded = word(index+1+j)
                        bits = 11 if kind == 4 else 10
                        base += encoded & ((1<<bits)-1)
                        b = base+1+(encoded>>bits&511)
                        c = base+1+(encoded>>(bits+9)&511)
                        points = [vertices[k+vertex_offset] for k in (base,b,c)]
                        if kind == 6:
                            points.insert(2,tuple(points[1][a]+points[2][a]-points[0][a] for a in range(3)))
                        if bounds is not None:
                            bounds_checked += 1
                            if any(v[a] < bounds[a][0]-4 or v[a] > bounds[a][1]+4 for v in points for a in range(3)):
                                bounds_mismatches += 1
                        label=''
                        if label_surfaces:
                            prop_index=header&4095
                            if prop_index>=len(properties):raise ValueError('Surface property index outside table')
                            name_at=properties[prop_index][3]
                            name=names[name_at:names.index(0,name_at)].decode()
                            label=f' surface_{prop_index} material_{name}'
                        stream.write(f'g contents_{contents:08x}{label}\n')
                        for point in points:
                            stream.write('v ' + ' '.join(str(x) for x in point) + '\n')
                        stream.write('f ' + ' '.join(str(i) for i in range(-len(points),0)) + '\n')
                        faces += 1
                else:
                    skipped[str(kind)] += 1
            except (ValueError, IndexError, struct.error) as exc:
                errors.append(dict(type=kind,index=index,error=str(exc)))
                if len(errors) > 100:
                    raise ValueError('Too many invalid records; decoder stopped') from exc
    report = dict(source=str(path.resolve()), world_root=root, world_model_first_vertex=world[10],
                  selected_vertex_offset=vertex_offset, regular_polygons=faces,
                  world_nodes_visited=len(visited), encountered_types=dict(counts),
                  repeated_node_references=shared_nodes,
                  skipped_leaf_types=dict(skipped), errors=errors,
                  bounds_checked=bounds_checked, polygons_outside_parent_bounds=bounds_mismatches,
                  complete=False, playable=False,
                  note='Regular world polygons only. Packed, type-8 and static prop leaves require further work.')
    (output/'collision-recovery.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bsp', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--vertex-offset',type=int,help='Diagnostic override; defaults to world model first_vertex')
    args = parser.parse_args()
    decode(args.bsp,args.output,args.vertex_offset)
