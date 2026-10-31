"""Run the native-prop conversion stages for a port, in order, and record how long each took.

From a package with the world rebuilt (Thunderdome: the UV-rescaled 0.2.0, `ArenaThunderdome-uv`):

  1. props          build_native_props.py: compiled props, the props RPak and placements -> <source>-props
  2. rebake         rebake_native_prop_shadows.py: lightmap tiles and probes with the props as casters
  3. collision      add_native_prop_collision.py: solid props as world triangle collision
  4. overlays       separate_world_overlays.py: world overlay layers lifted off their surfaces
  5. world-materials patch_world_materials.py: fallback-textured overlays and alpha decals in the world RPak
  6. cells          build_visibility_cells.py: per-cell visible sets
  7. fades          fade_small_props.py: fade distances for small non-foliage props

Each stage refuses a package it has already processed, so a failed run is restarted from the source. Stage
output goes to <output>/pipeline.log and the timings to <output>/pipeline.json. 30 October 2026, Thunderdome:
props 7 min, rebake 11 min, world materials 2 min, cells 3 min with cached rays (35 min tracing the stadium ring
too, about 10 within the play bounds), everything else under a minute.

  python run_prop_pipeline.py thunderdome <source package> [--foliage]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def stages(ident, source, output, foliage):
    o = str(output)
    return [('props', ['build_native_props.py', ident, str(source)]+(['--foliage'] if foliage else [])),
            ('rebake', ['rebake_native_prop_shadows.py', ident, o]),
            ('collision', ['add_native_prop_collision.py', ident, o]),
            ('overlays', ['separate_world_overlays.py', o]),
            ('world-materials', ['patch_world_materials.py', ident, o]),
            ('cells', ['build_visibility_cells.py', ident, o]),
            ('fades', ['fade_small_props.py', ident, o])]


def run(ident, source, foliage):
    source = Path(source); output = source.parent/(source.name+'-props')  # build_native_props.py's destination
    timings = {}; log_path = output.parent/(output.name+'-pipeline.log')
    with log_path.open('w') as log:
        for name, args in stages(ident, source, output, foliage):
            start = time.time(); log.write(f'== {name}\n'); log.flush()
            print(f'{name} ...', flush=True)
            run = subprocess.run([sys.executable, '-u', str(ROOT/args[0]), *args[1:]], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            timings[name] = round(time.time()-start, 1); print(f'{name} {timings[name]} s', flush=True)
            if run.returncode:
                raise SystemExit(f'{name} failed ({run.returncode}); see {log_path}')
    log_path.replace(output/'pipeline.log')
    (output/'pipeline.json').write_text(json.dumps(dict(source=str(source), foliage=foliage, seconds=timings,
                                                        total=round(sum(timings.values()), 1)), indent=2))
    print(json.dumps(timings))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('ident'); p.add_argument('source')
    p.add_argument('--foliage', action='store_true'); a = p.parse_args()
    run(a.ident, a.source, a.foliage)
