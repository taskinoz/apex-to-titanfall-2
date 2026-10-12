"""Build a conservative camera-access-path diagnostic without changing draw bounds.

Titanfall's client PvsCullAccessPath clips CELL_AABB_NODES and OBJ_REF_BOUNDS
before emitting mesh references. Keep the real MESH_BOUNDS, indices, materials,
and collision intact; only visibility boxes contain the playable camera domain.
This deliberately trades PVS selectivity for a controlled client experiment.
"""
import json, math, shutil, struct
from pathlib import Path
from compact_preview_bsp import compact
from preview_visibility import validate_visibility
from repair_preview_index_padding import read_lumps

ROOT = Path(__file__).resolve().parent
CAMERA_MIN = (-16384.0, -16384.0, -8192.0)
CAMERA_MAX = (16384.0, 16384.0, 8192.0)


def build_camera_visibility(bounds, references, camera_min=CAMERA_MIN,
                            camera_max=CAMERA_MAX, leaf_size=255):
    meshes = list(struct.iter_unpack('<8f', bounds))
    refs = list(struct.iter_unpack('<H', references))
    if not meshes or len(meshes) > 65535 or sorted(r[0] for r in refs) != list(range(len(meshes))):
        raise ValueError('Visibility references must cover every mesh exactly once')
    if not 1 <= leaf_size <= 255 or math.ceil(len(meshes) / leaf_size) > 255:
        raise ValueError('Flat visibility tree exceeds native byte-sized counts')
    if not all(math.isfinite(v) for v in (*camera_min, *camera_max)) or any(
            camera_min[k] >= camera_max[k] for k in range(3)):
        raise ValueError('Invalid camera domain')
    boxes = []
    for (index,) in refs:
        m = meshes[index]
        if not all(math.isfinite(v) for v in m) or any(m[k+4] < 0 for k in range(3)):
            raise ValueError('Invalid mesh bounds')
        low = tuple(min(camera_min[k], m[k] - m[k+4] - 1) for k in range(3))
        high = tuple(max(camera_max[k], m[k] + m[k+4] + 1) for k in range(3))
        boxes.append((low, high))
    low = tuple(min(b[0][k] for b in boxes) for k in range(3))
    high = tuple(max(b[1][k] for b in boxes) for k in range(3))
    children = math.ceil(len(boxes) / leaf_size)
    nodes = [struct.pack('<3f2BH3f2H', *low, children, 0, len(boxes), *high, 1, 0)]
    for first in range(0, len(boxes), leaf_size):
        batch = boxes[first:first+leaf_size]
        blo = tuple(min(b[0][k] for b in batch) for k in range(3))
        bhi = tuple(max(b[1][k] for b in batch) for k in range(3))
        nodes.append(struct.pack('<3f2BH3f2H', *blo, 0, len(batch), len(batch), *bhi, 0, first))
    objects = b''.join(struct.pack('<3fI3fI', *lo, 0, *hi, 0) for lo, hi in boxes)
    result = (b''.join(nodes), references, objects)
    validate_visibility(*result, bounds)
    return result


def build():
    source = ROOT/'output/phase-runner/preview-full-collision/mp_phase_runner_preview.bsp'
    output = ROOT/'output/phase-runner/preview-camera-visibility/mp_phase_runner_preview.bsp'
    # 0.1.28 is withdrawn after the client hid the recovered objects. Native
    # world index submission has a separate capacity the box tests did not cover.
    from audit_world_draw_budget import enforce_camera_bypass_budget
    enforce_camera_bypass_budget(source)
    current = read_lumps(source, (0x51, 0x77, 0x78, 0x79))
    nodes, refs, objects = build_camera_visibility(current[0x51], current[0x78])
    assert refs == current[0x78]
    checks = validate_visibility(nodes, refs, objects, current[0x51])
    report = compact(source, output, {0x77: nodes, 0x79: objects})
    status = json.loads(source.with_name('source-build.json').read_text())
    status['camera_visibility_repair'] = dict(
        **checks, camera_domain_min=CAMERA_MIN, camera_domain_max=CAMERA_MAX,
        leaf_reference_limit=255, maximum_pending_nodes=len(nodes)//32-1,
        reference_order_preserved=True, geometric_mesh_bounds_preserved=True,
        collision_and_draw_buffers_byte_identical=True, compaction=report,
        native_reader='client.dll PvsCullAccessPath at RVA 0x2e8e80',
        camera_inside_object_boxes_bypasses_access_path_silhouette_clip=True,
        experimental=True, client_rendering_verified=False,
        limitation='Conservative PVS boxes reduce visibility selectivity and may lower frame rate. '
                   'Real mesh bounds remain geometric. Client testing must establish whether '
                   'this stage causes the angle-dependent disappearance; GPU correctness is not proven.')
    output.with_name('source-build.json').write_text(json.dumps(status, indent=2))
    shutil.copy2(source.with_suffix('.stbsp'), output.with_suffix('.stbsp'))
    print(json.dumps(status['camera_visibility_repair'], indent=2))


if __name__ == '__main__':
    build()
