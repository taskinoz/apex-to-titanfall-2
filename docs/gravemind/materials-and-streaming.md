# Titanfall native materials, PBR and STBSP

Scope: the project's native world-material adaptation. The tested target uses
RPak version 7 and `matl` version 12. Apex shaders are not directly transplantable.

## Materials and correct texture assignment

Read RMDL skin and submesh material slots and keep original albedo UVs. Losing
the submesh mapping made control-room consoles display unrelated atlas fragments.
Do not guess transparency from a material slot number: painted Hammond cargo
containers must remain opaque; actual opacity/decal masks select alpha passes.

The native adaptation recovers albedo, normal, gloss and specular channels.
Metalness/roughness needs an intentional BRDF conversion; renaming source channels
does not reproduce source shading. Source vertex colors, layered blends, wind,
animated screens and full reflection behavior remain incomplete.

Native world materials require compatible shader dependencies, uberbuffer,
glue, rasterizer, depth and blend states, and matching depth passes. Lowering
texture alpha on an opaque material does not make correct transparent glass.
Dedicated compatible alpha/transparent passes and TEXDATA flags must agree.

## Dependency closure and loading failures

Check every texture, shader and pass dependency against the package and required
native common/Coliseum packs. One decal shader referenced an unmounted Glitch
asset and stalled loading. The fixed conversion embeds compatible dependencies
with distinct GUIDs. Validate a cold launch and stock-map reload; having visited
a dependency map earlier must not be required.

GUID existence checks alone are insufficient. In Drop-Off, inheriting a glass
template's unrelated texture table stalled startup despite available GUIDs.
Alpha materials must bind only their intended recovered channels. Broad map-regex
pak loading and raw dependency preloading also caused lifecycle/hang failures
in earlier experiments; retain the actually tested pack order and reload tests.

Use neutral fallback materials for missing assets rather than an unrelated atlas.
Report source aliases, rendered face counts, shader provenance and unresolved
dependencies separately. `_wldc` aliases and derived layer alpha are important
for the recovered ground/dirt overlays.

## STBSP versus STARPak

Titanfall requires a matching STBSP material catalogue alongside these BSPs.
The tested STBSP version is 8.0, header 392 bytes, magic `0xCB00CBB5`. Six uint64
offset/count descriptors begin at byte 168. Material-info and spatial-column
counts are record counts with 24-byte strides; other blocks use byte counts.
Observed physical block order is `[1,2,3,0,4,5]`, with absolute file offsets.

Material records link string names to 64-bit asset GUIDs. Columns carry
payload-relative offset, size, coverage and packed XY bounds. The ports use
resident textures and empty coverage columns. This fulfils the tested catalogue
requirements; it does not implement full spatial mip streaming. STBSP and texture
STARPak have distinct roles and must not be conflated.

Drop-Off 0.6.0 has 231 native catalogue materials and resident textures capped at
1024 pixels. That cap is a project quality/residency choice, not a native engine
limit. A future streaming backend needs verified coverage/residency semantics,
preserved referenced STARPak offsets, and movement tests under actual VRAM pressure.
Stage referenced stream extents into owned sparse copies; never truncate inputs.

## Foliage and depth separation

Phase Runner's twenty firs use fixed author LOD2: 62 bark plus 952 foliage
triangles per tree. Leaf alpha combines albedo alpha and opacity with coverage-
preserving mip generation. Compatible two-sided foliage is retained. Leaf cards
are excluded from static casting to avoid rectangular shadows; trunks cast.
No wind animation or dynamic LOD is recovered by world baking.

Z-fighting fixes separate only render layers and preserve collision bytes.
Phase Runner used 0.08-unit layer offsets (0.16 for stripes); Drop-Off's selected
ground overlay used 0.24. These are measured local repairs, not universal texture
offsets. Record applied edits and hashes so rebuilding cannot apply them twice.

## Sources

`prepare_composite_materials.py`, `build_preview_stbsp.py`,
`stage_rpak_streams.py`, `docs/conversion/loading-repair.json`,
`docs/arena-repairs-2026-10-06.md`, `docs/composite/missing-materials.json`,
and both conversion guides. See [lighting](lighting.md) for shading diagnosis.
