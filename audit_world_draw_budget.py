"""Audit native index-copy and static draw-batch limits without binary changes.

engine.dll+0xb72af compares the next index total with 0x300000 and branches
to the submission epilogue at +0xb74b1 when it would exceed that capacity.
This is separate from static model rendering and from PVS box acceptance.
engine.dll+0xb7304 also stops submission at 0x800 material batches. Runtime
dynamic-light masks can split otherwise compatible material/channel batches.
"""
import json,struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WORLD_INDEX_CAPACITY=0x300000
WORLD_BATCH_CAPACITY=0x800


def static_draw_key(record):
    # Runtime key at b72ba..b72e4 = vertex channel, material sort, dynamic
    # light mask. Luxel metadata/styles do not split this submission path.
    r=struct.unpack('<I3H6b2h2BHI',record)
    return (r[4],r[-2])


def batch_audit(meshes):
    keys=[static_draw_key(meshes[i:i+28]) for i in range(0,len(meshes),28)]
    starts=[i for i,k in enumerate(keys) if i==0 or k!=keys[i-1]]
    return dict(static_batch_runs=len(starts),unique_static_draw_keys=len(set(keys)),
        world_batch_capacity=WORLD_BATCH_CAPACITY,
        static_batches_fit_simultaneously=len(starts)<=WORLD_BATCH_CAPACITY,
        first_mesh_excluded_by_static_batch_limit=starts[WORLD_BATCH_CAPACITY] if len(starts)>WORLD_BATCH_CAPACITY else None,
        dynamic_light_masks_can_split_static_batches=True,
        native_batch_limit_instruction='engine.dll+0xb7304',
        native_batch_limit_exit='engine.dll+0xb74c9')


def audit(path):
    from repair_preview_index_padding import read_lumps
    lumps=read_lumps(path,(0x50,0x7b))
    counts=[struct.unpack_from('<H',lumps[0x50],i+4)[0] for i in range(0,len(lumps[0x50]),28)]
    total=3*sum(c+(c&1) for c in counts)
    used=0;prefix=0
    for count in counts:
        indices=3*(count+(count&1))
        if used+indices>WORLD_INDEX_CAPACITY:break
        used+=indices;prefix+=1
    return dict(path=str(path),meshes=len(counts),real_triangles=sum(counts),
        native_padded_indices=total,world_index_capacity=WORLD_INDEX_CAPACITY,
        all_meshes_fit_simultaneously=total<=WORLD_INDEX_CAPACITY,
        maximum_all_visible_mesh_prefix=prefix,prefix_indices=used,
        first_mesh_excluded_when_all_visible=prefix if prefix<len(counts) else None,
        mesh_partitions=list(struct.unpack_from('<3I',lumps[0x7b])),
        **batch_audit(lumps[0x50]),
        limitation='This audits a native world-rendering capacity. It does not prove which '
                   'meshes the running client marks visible or account for earlier index-buffer '
                   'use in the frame. Static models use a different rendering path.')


def enforce_camera_bypass_budget(path):
    proof=audit(path)
    if not proof['all_meshes_fit_simultaneously']:
        raise ValueError('Withdrawn camera-bypass experiment: all-visible world geometry '
                         f"needs {proof['native_padded_indices']:,} indices but the native "
                         f"world index budget is {WORLD_INDEX_CAPACITY:,}. Preserve spatial "
                         'visibility or move recovered props to native model rendering.')
    if not proof['static_batches_fit_simultaneously']:
        raise ValueError('Withdrawn camera-bypass experiment: all-visible world geometry '
                         f"needs {proof['static_batch_runs']:,} material-batch runs but the native "
                         f"draw list holds {WORLD_BATCH_CAPACITY:,}. Group compatible meshes first.")
    return proof


def main():
    paths={'preview':'output/phase-runner/preview-full-collision/mp_phase_runner_preview.bsp',
           'homestead':'inputs/titanfall2-homestead/maps/mp_homestead.bsp',
           'colony':'inputs/titanfall2-colony/maps/mp_colony02.bsp'}
    report=dict(native_instruction_rva='engine.dll+0xb72af',
        native_overflow_exit_rva='engine.dll+0xb74b1',
        native_instruction_source='logs/native-reader-engine-0x7cb410.txt',
        builds={name:audit(ROOT/path) for name,path in paths.items()},
        user_report_0_1_28='No rocks or objects visible',
        index_budget_is_confirmed=True,client_failure_cause_confirmed=False,
        recommended_direction='Retain spatial bounds; investigate native prop rendering '
                              'or verified lower-detail draw meshes instead of exposing all '
                              'seven million baked world triangles at once.')
    (ROOT/'logs/world-draw-budget-audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
