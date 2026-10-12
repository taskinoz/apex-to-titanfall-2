# Titanfall lightmaps, character probes and menu-stage isolation

Scope: project ray-baked sun/sky/local lighting, not a production GI or reflection
bake. PBR material recovery and baked illumination are separate tasks.

## Native lightmap and probe relationships

Observed SKY A uses RGBM in linear units:
`decoded_rgb = rgb * (alpha * 3.984375 + 0.015625)`.
SKY B direction decodes as `rgb * 2.007874 - 1`.
RTL A packs four six-bit local-light entries plus an eight-bit page; unused
entry is 63. RTL B carries visibility channels and a half-resolution plane.
The light-page table must match native hardware light indexing.

World-light records are 112 bytes in the tested lump version. Ambient entries
are filtered out of the hardware light table, so a WORLD_LIGHTS index is not a
hardware index. In the tested configuration, sun world slot 1 maps to hardware
slot 0. Character dynamic-light references also apply native reserved offsets.

Character probes are 48 bytes with fixed-point ambient coefficients (divide by
8192), visibility bytes and four light references. Rebuild their KD/access
structure and remap references against the filtered hardware table. Phase Runner
has 39,819 gameplay plus two menu probes, with 16,383 KD nodes. Drop-Off has
2,907 probes. These are map measurements, not format capacity limits.

## Physical multiplayer menu area

Titanfall multiplayer maps contain a physical pilot/Titan customization stage.
Mixing its environment/light slots with gameplay produced menu-character shadows
and a small rectangular lit region around the camera. Incorrect probe mapping
also left the player without expected native lighting.

Retain a separate menu environment and stage probes. Phase Runner isolates its
stage near `[-11776,11856,12736]`; this is a conversion choice. Drop-Off's 0.5.0
repair relocates all menu anchors and lighting together outside the photographic
sky sphere. Moving only the camera or one mesh is insufficient. Verify pause
menu transitions and views from the gameplay area.

Keep photographic sky geometry out of opaque caster/occlusion masks. The
converted skies are sphere-projection approximations, not exact source skyboxes.

## Triangle-shaped wall shadows

Drop-Off's wall marks disappeared with native fullbright, supporting a lighting
diagnosis rather than an albedo fault. Sparse 4x4 charts sampled tiny trim shadows
at triangle vertices and spread them over large white panels. Global nearest-
sample padding could also copy another chart's values into a gutter.

0.6.0 first confined every old chart's padding to its own six valid samples,
preserving those samples byte-for-byte. Padding repair alone did not remove the
wall marks. It then rebaked 1,302 large painted-wall triangles with 32x32 charts
(351 raster samples) and 948 smaller triangles with 16x16 (105 samples), using
slightly inset receivers and local gutters. Scope is the vertical painted-metal
panels near both control entrances, not the entire map.

New charts occupy spare space on atlas page 3, starting at rows 1248 and 1920.
No atlas page or texture-memory increase was needed. Reserve these rectangles
before subsequent appends and reject overlaps.

The native atlas page is bound by material sort per mesh. Updating vertex UVs
alone initially bound the wrong page. Split affected meshes by page, repartition
their indices with odd-triangle pair padding, and remap bounds/visibility. Tests
preserve old active faces and all non-lightmap vertex attributes. Reviewed native
captures greatly reduce the severe zigzags; this is not proof that every sparse
chart artifact elsewhere is fixed.

## Baker scope and verification

Phase Runner uses seven lightmap pages and thirty interior lights. Drop-Off uses
four 2048-pixel pages and sixty selected local lights; source spots are approximated
as point lights. Neither has bounced GI or freshly baked reflection cubemaps.

Verify charts, page bindings, RTL IDs and probe references structurally, then
inspect native horizontal/up/down, interior and player views. Preserve logs and
camera metadata; a successful bake calculation does not establish native output.

## Sources

`docs/conversion/character-lighting.json`, `interior-lights.json`,
`apply_baked_lighting.py`, retained C++ baker sources,
`docs/composite/screens-and-menu-2026-10-07.md`,
`docs/composite/local-repairs-2026-10-07.md`, `repair_composite_local.py`,
`test_composite_local.py`, and `docs/composite/validation.json`.
