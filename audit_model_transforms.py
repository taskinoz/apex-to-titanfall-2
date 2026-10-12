"""Report Apex inline model placement and source vertex bounds."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import bsp_tool


def audit():
    bsp = bsp_tool.load_bsp(str(ROOT/'inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp'))
    geo = bsp.external
    for suffix in ('env','fx','script','snd','spawn'):
        if hasattr(bsp,'ENTITIES_'+suffix):
            setattr(geo,'ENTITIES_'+suffix,getattr(bsp,'ENTITIES_'+suffix))
    models = []
    for index in range(len(geo.MODELS)):
        model = geo.model(index)
        vertices = [v.position for mesh in model.meshes for p in mesh.polygons for v in p.vertices]
        if not vertices:
            continue
        bounds = [[min(v[k] for v in vertices) for k in range(3)],
                  [max(v[k] for v in vertices) for k in range(3)]]
        models.append(dict(index=index,entity=model.entity,
                           origin=list(model.origin),angles=list(model.angles),raw_bounds=bounds,
                           polygons=sum(len(m.polygons) for m in model.meshes)))
    output = ROOT/'output/phase-runner/model-transforms.json'
    output.write_text(json.dumps(models,indent=2))
    print(json.dumps(models[:4],indent=2))


if __name__ == '__main__':
    audit()
