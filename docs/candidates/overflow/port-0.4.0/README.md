# Overflow 0.4.0

Restores Apex two-layer blending with Titanfall's native blend shader: stains, dirt and wear on concrete, painted metal and rock now blend as in Apex instead of showing one layer. 51 pipes, rocks and wall plates drawn at coarse detail now collide with the shape you see, and 53 props whose Apex collision was still in the map (tech panels, server racks, ceiling servers, warning lights, vents) are drawn instead of being invisible objects. Known issue (also in 0.3.1): about one load in five can crash Northstar at spawn; restart and load again. Animated advertisements, AI navigation and Titan modes remain absent.

## How

- `apply_layer_blends.py`: 18 Apex bm materials rebound to Titanfall's native wld bm shader with source vertex alpha / z-up blend input (all 18 matched their source alpha).

- `match_collision_to_render.py`: 51 coarse-LOD placements over 15% collision/render mismatch collide with their drawn triangles; no spawn moved.

- `recover_invisible_props.py`: 53 omitted props near reachable ground whose own surface lay on undrawn world collision are drawn from their source VG; no collision added.

Invisible reachable collision: 3.7% before, 2.8% after.

Validation: 1,544 binary checks; collision grid = 0.3.1 active set minus replaced colliders plus new headers; 31/31 drawn-surface contacts (9 samples stopped on an unrelated pre-existing clip above the pipes); spawns, both teams, postmatch lobby, stock and map reload. Two of many harness sessions crashed on a second map load at spawn; repeated fresh-session and reload tests of this build and of 0.3.1 show the same intermittent Northstar instability, not a new fault.

Rollback: `overflow/before-layer-blend/`, `before-collision-match/`, `before-invisible-props/` on the build drive.
