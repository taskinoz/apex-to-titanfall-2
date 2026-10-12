"""Read-only remaining-placement/compiled-LOD audit for the installed 0.1.44 map."""
import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/lighting-python'))
from read_vg_static import compiled_materials

PROPOSED_LODS = {
    'sign_caution_chemical': 0, 'sign_caution_pump_warning': 0,
    'sign_plate_c': 0, 'sign_service_shaft_01': 0,
    'sign_service_shaft_02': 0, 'street_sign_arrow': 0,
    'ceiling_vent_metal': 0, 'imc_antenna_01': 0, 'imc_antenna_02': 0,
    'light_wall_IMC_01_on': 1, 'wire_ceiling_mounts_straight': 1,
    'wire_ground_coils_02': 1, 'survival_modular_flexscreens_04': 0,
    'survival_modular_flexscreens_frame_01': 1,
    'thunderdome_screen_tower_arm_01': 1,
    'veh_land_msc_forklift_imc_v2_static': 2,
}


def main():
    inventory = json.loads((ROOT / 'logs/art-supports-remaining-objects.json').read_text())
    validation = json.loads((ROOT / 'northstar/PhaseRunner.Preview/runtime-validation.json').read_text())
    availability = {r['model']: r for r in json.loads((ROOT / 'logs/remaining-source-model-availability.json').read_text())}
    placements = inventory['remaining_placements']
    counts = Counter(p['model'] for p in placements)
    assert sum(counts.values()) == validation['remaining_objects']['unrendered_arena_placements']
    models = []
    for model, count in counts.items():
        name = Path(model).stem
        folder = ROOT / 'tools/legion/exported_files/models' / name
        row = dict(model=model, name=name, placements=count,
                   category=model.split('/')[1], lods=[], materials=[])
        source = availability.get(model, {})
        row['source_qc_exists'] = source.get('source_qc_exists', False)
        rmdl, vg = folder / (name + '.rmdl'), folder / (name + '.vg')
        row['compiled_available'] = rmdl.exists() and vg.exists()
        if row['compiled_available']:
            try:
                slots, skins = compiled_materials(rmdl.read_bytes())
                selected_skins = sorted(set(p['skin'] for p in placements if p['model'] == model))
                row['skins'] = selected_skins
                row['materials'] = sorted({mat for skin in selected_skins for mat in skins[skin]})
                with vg.open('rb') as handle:
                    header = handle.read(160)
                    assert struct.unpack_from('<2I', header) == (0x47567430, 1)
                    h = struct.unpack_from('<18Q', header, 16)
                    handle.seek(h[2])
                    meshes = [struct.unpack('<18I', handle.read(72)) for _ in range(h[3])]
                    handle.seek(h[12])
                    lods = [struct.unpack('<2hf', handle.read(8)) for _ in range(h[13])]
                row['static_decodable'] = True
                for lod, (first, size, distance) in enumerate(lods):
                    assert size == len(slots) and first >= 0 and first + size <= len(meshes)
                    selected = meshes[first:first + size]
                    assert all(m[9] % 3 == 0 for m in selected)
                    triangles = sum(m[9] // 3 for m in selected)
                    static = all(m[9] == 0 or m[0] & 0x5000 != 0x5000 for m in selected)
                    row['static_decodable'] &= static
                    row['lods'].append(dict(lod=lod, triangles=triangles,
                        total_triangles=triangles * count, sections=size,
                        static_decodable=static, source_distance=distance))
            except Exception as exc:
                row['error'] = str(exc)
        models.append(row)
    budget = validation['draw_budget']
    from audit_world_draw_budget import audit
    current = audit(ROOT / 'northstar/PhaseRunner.Preview/mod/maps/mp_phase_runner.bsp')
    installed = audit(Path('D:/Games/Titanfall2/R2Northstar/mods/PhaseRunner.Preview/mod/maps/mp_phase_runner.bsp'))
    for field in ('real_triangles', 'native_padded_indices', 'static_batch_runs'):
        assert current[field] == installed[field] == budget[field], field
    indices = budget['native_padded_indices']
    capacity = budget['world_index_capacity']
    proposal = []
    for model in models:
        if model['name'] not in PROPOSED_LODS:
            continue
        lod = model['lods'][PROPOSED_LODS[model['name']]]
        assert lod['static_decodable']
        proposal.append(dict(model=model['model'], placements=model['placements'],
                             source_lod=lod['lod'], triangles=lod['total_triangles'],
                             materials=model['materials']))
    triangles = sum(p['triangles'] for p in proposal)
    proposal_materials = sorted({m for p in proposal for m in p['materials']})
    assert triangles * 3 < int(capacity * .95) - indices
    result = dict(version=validation['version'], rendered=validation['remaining_objects']['rendered_in_arena'],
                  omitted=len(placements), model_types=len(models),
                  compiled_model_types=sum(m['compiled_available'] for m in models),
                  compiled_placements=sum(m['placements'] for m in models if m['compiled_available']),
                  current_indices=indices, capacity=capacity,
                  raw_free_indices=capacity - indices,
                  extra_indices_under_95_percent=int(capacity * .95) - indices,
                  static_batch_runs=budget['static_batch_runs'], models=models,
                  installed_and_workspace_draw_budgets_match=True,
                  proposal=dict(placements=sum(p['placements'] for p in proposal),
                      triangles=triangles, source_material_names=len(proposal_materials),
                      index_utilization_before_new_mesh_padding=(indices + triangles * 3) / capacity,
                      selected_models=proposal,
                      status='Read-only candidate; no geometry or game files changed. Final padded indices, material/lightmap batches, dependencies, collision and loading require validation after staging.'))
    out = ROOT / 'logs/recoverable-prop-budget-0.1.44.json'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('models', 'proposal')}, indent=2))
    print('Proposed placements:', result['proposal']['placements'], 'triangles:', triangles,
          'source material names:', len(proposal_materials))
    for row in sorted(models, key=lambda r: (r['category'], r['name'])):
        costs = ','.join(f"L{x['lod']}:{x['triangles']}/{x['total_triangles']}" for x in row['lods'])
        print(f"{row['category']:15} {row['placements']:5} {row['name']:55} {costs or 'NO VG'} "
              f"materials={len(row['materials'])} static={row.get('static_decodable')} error={row.get('error','')}")


if __name__ == '__main__':
    main()
