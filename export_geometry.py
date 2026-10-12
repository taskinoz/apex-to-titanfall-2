"""Recover Apex brush geometry for inspection; this does not create a TF2 map."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
import bsp_tool
from bsp_tool.scene import Obj


def export(path, output):
    bsp = bsp_tool.load_bsp(str(path.resolve()))
    geo = bsp.external
    if geo.loading_errors:
        raise ValueError(f'External BSP parsing errors: {geo.loading_errors}')
    for suffix in ('env', 'fx', 'script', 'snd', 'spawn'):
        name = 'ENTITIES_' + suffix
        if hasattr(bsp, name):
            setattr(geo, name, getattr(bsp, name))
    models = {f'brush_{i:03d}': geo.model(i) for i in range(len(geo.MODELS))}
    output.mkdir(parents=True, exist_ok=True)
    Obj.from_models(models).save_as(str(output / (path.stem + '.obj')))
    summary = dict(source=str(path.resolve()), version=bsp.version,
                   brush_models=len(models), meshes=len(geo.MESHES),
                   triangles=sum(m.num_triangles for m in geo.MESHES),
                   materials=list(geo.SURFACE_NAMES),
                   static_prop_models=list(geo.GAME_LUMP.sprp.model_names),
                   static_props=len(geo.GAME_LUMP.sprp.props),
                   note='Brush geometry only. No prop meshes, textures, TF2 collision, or playable BSP.')
    (output / 'geometry-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('materials', 'static_prop_models')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bsp', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export(args.bsp, args.output)
