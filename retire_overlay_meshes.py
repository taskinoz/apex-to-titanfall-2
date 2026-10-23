"""Retire coplanar Apex overlay materials that Titanfall draws opaque (z-fighting), by whole mesh.

Vertex-alpha "b2t" overlays (icelandic_dirt_01_wld_b2t over asphalt) fade by
vertex alpha in Apex, which the native world shader cannot read; drawn opaque
they z-fight with the surface below. CONFIG[ident]['retire_overlays'] lists
them; the underlying surface stays. Same mesh-level retire as
fix_overflow_overlays.py (positions can coincide with the base layer).

  python retire_overlay_meshes.py thermal-station
"""
import json
import sys

import fix_overflow_overlays as overlays
from new_arena_ports import CONFIG, folder


def retire(ident):
    names = tuple(CONFIG[ident].get('retire_overlays', ()))
    if not names:
        return
    out = folder(ident); overlays.RETIRE = names
    counts = overlays.retire_meshes(out/(CONFIG[ident]['target']+'.bsp'))
    (out/'retired-overlays.json').write_text(json.dumps(counts, indent=2))
    print(ident, 'retired overlay triangles', counts, flush=True)


if __name__ == '__main__':
    retire(sys.argv[1])
