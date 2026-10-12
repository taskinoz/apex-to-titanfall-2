"""Check packaged v12 material headers and their external dependencies."""
import json
import struct
from pathlib import Path
from extract_native_material import NativePak

ROOT = Path(__file__).resolve().parent


def validate(folder=None):
    folder = Path(folder) if folder else ROOT/'output/phase-runner/world-materials'
    custom = NativePak(folder/'build/phase_runner_world.rpak')
    references = [NativePak(ROOT/'inputs/tf2-rpak-work'/name)
                  for name in ('common.raw.rpak','coliseum.raw.rpak')]
    known = {a['guid'] for p in [custom]+references for a in p.assets}
    missing = set()
    materials = 0
    for asset in custom.assets:
        if asset['type'] != 'matl':
            continue
        spec,uber = custom.material(asset)
        if len(uber) != 224 or asset['version'] != 12:
            raise ValueError('Incorrect TF2 material layout')
        for value in list(spec['$textures'].values()) + [spec[k] for k in
            ('$depthShadowMaterial','$depthPrepassMaterial','$depthVSMMaterial','$colpassMaterial','shaderSet')]:
            guid = int(value,16)
            if guid and guid not in known:
                missing.add(hex(guid))
        materials += 1
    result = dict(materials=materials,assets=len(custom.assets),
                  missing_external_guids=sorted(missing),
                  native_v12_verified=True,all_dependencies_present=not missing)
    (folder/'validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if missing:
        raise ValueError('Unresolved dependencies')


if __name__ == '__main__':
    validate()
