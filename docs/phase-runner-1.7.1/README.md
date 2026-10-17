# Phase Runner 1.7.1

Fixes the flickering floor in both starting bases (opaque Apex decals drawn on the same plane as the floor; the stripes are now alpha-blended decals and a wrong stand-in sign texture is hidden), restores the metal frames around stacked containers that left visible gaps, and smooths the tunnel catwalks so they no longer dip and meet the floor at both arena ends. Minimaps are no longer washed out (shared ApexMaps.UI 0.1.1). Includes 1.7.0: Apex two-layer blending, Apex-scale ground tiling and collision matched to 210 cliffs and rocks.

## How

- `phase_runner_blend.py` traces each Apex blend material's pixel shader (layer UV source, ramp, vertex-alpha or z-up blend input). Vertex alpha comes from the source BSP vertex colours and prop VG colours matched by position, or from the z-up normal term; materials whose albedo is projected from world position get `uv = (x, -y) . RotScale + Translate` in source coordinates. The surfaces are rebound to native Coliseum wld bm materials in a new `phase_runner_blend.rpak`. Layer 2 is sampled at the mesh UV (Titanfall's shader has one UV): the tiling of world-projected snow/moss layers on rocks is approximate, not their colour.

- Kept single-layer: dam_concrete_02_stained_bm, metal_painted_yellow_02_dirty_bm, asphalt08_cracked_bm (unmatched source alpha or a regression in native captures).

- `phase_runner_collision.py` finds each rock's drawn LOD by vertex matching and replaces the source collider of 210 rocks over 15% mismatch with their drawn triangles. Owners with any disabled primitive (tunnel caps, catwalk clips) are not touched; spawns are not moved.

Invisible reachable collision: 18.2% before, 1.0% after (upper bound: reach ignores out-of-bounds volumes).

Validation: 112 binary checks (only vertex alpha/UV, texture-data strings and appended collision change; render budget unchanged); 84 spawns clear and supported; 40/40 drawn-rock contacts; both teams, postmatch lobby, stock and map reload.

Rollback: `legacy-work/phase-runner/before-1.7.0/` on the build drive.
