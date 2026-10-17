# Phase Runner 1.7.0

Restores Apex two-layer blending with Titanfall's native blend shader: snow caps and moss on rocks, moss lines on the structures and moss/dirt ground now blend as in Apex. Snow and moss ground tile at the Apex scale instead of 3-8x too coarse. 210 boundary cliffs and rocks drawn at coarse detail now collide with the shape you see instead of invisible full-detail rock. Minimap, gameplay, tunnel and catwalk collision exclusions, lighting and scenery are unchanged. AI navigation remains incomplete.

## How

- `phase_runner_blend.py` traces each Apex blend material's pixel shader (layer UV source, ramp, vertex-alpha or z-up blend input). Vertex alpha comes from the source BSP vertex colours and prop VG colours matched by position, or from the z-up normal term; materials whose albedo is projected from world position get `uv = (x, -y) . RotScale + Translate` in source coordinates. The surfaces are rebound to native Coliseum wld bm materials in a new `phase_runner_blend.rpak`. Layer 2 is sampled at the mesh UV (Titanfall's shader has one UV): the tiling of world-projected snow/moss layers on rocks is approximate, not their colour.

- Kept single-layer: dam_concrete_02_stained_bm, metal_painted_yellow_02_dirty_bm, asphalt08_cracked_bm (unmatched source alpha or a regression in native captures).

- `phase_runner_collision.py` finds each rock's drawn LOD by vertex matching and replaces the source collider of 210 rocks over 15% mismatch with their drawn triangles. Owners with any disabled primitive (tunnel caps, catwalk clips) are not touched; spawns are not moved.

Invisible reachable collision: 18.2% before, 1.0% after (upper bound: reach ignores out-of-bounds volumes).

Validation: 126 binary checks (only vertex alpha/UV, texture-data strings and appended collision change; render budget unchanged); 84 spawns clear and supported; 40/40 drawn-rock contacts; both teams, postmatch lobby, stock and map reload.

Rollback: `legacy-work/phase-runner/before-1.7.0/` on the build drive.
