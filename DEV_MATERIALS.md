# Phase Runner material repair 0.1.32

The pass replaces 6,961 rendered triangles that used the native developer-grid
fallback. The source face assignments are recovered from the original compiler
buffer and independently checked OBJ order. Barrel faces are restricted to the
two proven source placements, 11900 and 11903.

| Original material | Replacement | Triangles |
| --- | --- | ---: |
| white_floor_tile_mendoko | Original Apex floor albedo/normal/gloss/specular | 761 |
| s2s_roof_panel_01_vc | Matching Titanfall source roof, with original vertex colors | 960 |
| barrel_latch_blue | Original Apex barrel albedo/normal/gloss/specular | 4,344 |
| dam_concrete_02_gray | Recovered stained-concrete variant | 62 |
| metal_painted_white_01 | Recovered white painted-metal variant | 34 |
| signage_building_02 | Recovered yellow warning-sign substitute | 564 |
| authored dev_gray_512 | White floor-tile cladding | 236 |

The last four assignments are themed substitutions, not exact original artwork.
The three recovered materials use all four native PBR shader channels. DDS files
retain their compressed source format and packed normal channels. Legion export
uses `--nmlrecalc none`; no unit-vector normal reconstruction is applied.

The original texture project remains in `output/phase-runner/world-materials`.
The separate candidate is `output/phase-runner/dev-materials`. Its existing
native materials are verified identical by material fields and uber-buffer data.
All 380 materials resolve their texture, shader and depth-pass dependencies.
The resident-texture STBSP catalog is regenerated and round-trip checked.

Every triangle's complete vertex records and lightmap page are checked against
0.1.31. Vertex, normal, lightmap, world-light and collision lumps remain byte
identical. Only developer-fallback bindings change. Native index padding and
the protected draw budget remain valid. Both tunnel walkways are unchanged.

Four preservation tests and 927 fresh native server collision checks pass.
Client rendering and lighting appearance still need inspection. The first bake
retains the limitations described in LIGHTING.md, including no indirect bounce
or custom reflection probes. ART_TODO.md records the future Nessie and walkway
ideas. Both 0.1.30 and 0.1.31 archives are retained.

Rebuild with `prepare_dev_materials.py`, RePak using its generated build.json,
`validate_world_materials.validate(project)`, `repair_dev_materials.py`, then
`build_preview_stbsp.build(folder, project)`. Run
`python -m unittest test_dev_materials` using the bundled Python. Package into a
separate directory and run the isolated native validation before finalizing.

Source tooling: [RSX](https://github.com/r-ex/rsx),
[Legion+](https://github.com/r-ex/LegionPlus), and
[RePak](https://github.com/r-ex/RePak). Local source texture identifiers and
paths are recorded in `recovered-materials.json` in the packaged mod.
