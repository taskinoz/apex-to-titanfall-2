---
id: gm_01m4nfvnsprv0ymngbh25c2hz2
title: Titanfall native materials, PBR and STBSP
description: Shader dependencies, material slots, alpha, resident catalogue and incomplete spatial streaming
tags:
  - titanfall-2
  - apex-legends
  - map-conversion
  - materials
  - pbr
  - stbsp
  - rpak
  - streaming
project: apex-to-titanfall-2
status: verified
created: 2026-10-11T12:44:01.206Z
updated: 2026-10-14T02:32:24.082Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 4
---
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

The same header layout also appears on PS4. Checked files: retail
`r2/maps/mp_lobby.stbsp` and `mp_eden.stbsp` from CUSA04013 1.00, and
`mp_lobby.stbsp` from the July 2016 PS4 Tech Test. All have magic `0xCB00CBB5`,
version 8.0, descriptor block 1 at byte 392, six uint64 descriptors at byte 168,
and physical order `[1,2,3,0,4,5]`. Only the headers were checked, so this does
not establish payload compatibility. See [PS4 dumps](../ps4/index.md).

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

## Source-derived texture policy and 0.3.0 findings (14 October 2026)

The requested fidelity policy is to derive native textures from original Apex channels, atlases, masks and reflected shader constants wherever supported. Keep source provenance and compare matched native R5R/Northstar camera views before release. Arbitrary saturation changes and generic interpretation of COLOR as RGB are not source reconstruction.

In the three 0.3.0 previews, the unpatched v8/v15 source pixel-shader DXBC reflection places the four-float albedo group at 352 (RGB at 356) and emissive group at 368 (RGB at 372). The first float in each group is an unrelated blend parameter. Guessed vector offsets produced incorrect colours and were rejected. Native HDR world materials retain source emission masks/tints, compatible complete PBR bindings, sRGB colour/emission and linear normal/data channels. Missing required maps use explicitly neutral channels rather than unrelated artwork. Resident textures have full mips and a 1024-pixel project cap.

Final adapted material counts are Firing Range 74 (5 HDR), Party Crasher 229 (15 HDR), and Overflow 143 (12 HDR). Generic vertex RGB/palette conversion is disabled: terrain COLOR encodes blend weights and some _vc materials also use palette data. Red terrain and green structures were observed in rejected native candidates. Preserve original bytes and require a reviewed per-material shader/palette mapping. One unavailable Overflow shader dependency retains its tested baseline; alpha emission and animated advertisements remain approximations.

Firing Range water uses unchanged native Gauntlet water_wild_02 bytecode with world lightmaps, adapted opaque state and BT-7274 water_wild_01_opaque normal/distortion/gloss/spec channels, while retaining the Apex backdrop albedo. BC5 normal/distortion stays BC5_UNORM through mip generation; decoding to ordinary RGBA does not preserve its encoding. Timed fixed-camera captures verified moving surface detail. Exact Apex refraction, reflections, waves, underwater behavior and volumetric fog remain incomplete.

Evidence: repository docs/candidates/native-water-fog-materials-2026-10-14.md, apex_material_constants.py, recover_arena_atmosphere.py, verify_arena_atmosphere.py, test_arena_atmosphere.py and the per-map port-0.3.0 receipts. The first material candidate crashed at materialsystem_dx11.dll+0x507fb; complete PBR bindings and explicit formats were corrected together, so the individual cause was not isolated.

## Shared UI texture packing and retained shader order — 14 October 2026

ApexMaps.UI 0.1.0 packs the five original 2560×1440 loading images and five existing 1024×1024 minimaps into one 8192×4608 atlas. Art is not resized. Three loading aliases per map plus one overview per map retain their original lookup names. UI artwork is decoded from its source DDS and recompressed as resident single-mip BC7_UNORM_SRGB; this is not lossless DDS block copying. The compiled pack contains one txtr and one uimg v10, with twenty image lookups. Native loading material GUIDs, states, bindings and uberbuffers are compared against retained original packs.

Do not move world materials before their mp_coliseum base shader dependencies simply to reduce residency: a native candidate loaded but showed pink fallback materials. The accepted fix retains world/incremental Postload ordering, separates the shared UI atlas, and supplies atlas-free presentation packs. World residency across installed conversions remains shared; this is not a streaming optimization. A future native/model or streaming backend needs a separately validated dependency order and residency policy.

Original source-derived world channels and prior source-reflection contracts remain unchanged by the 0.3.1 UI fix. Expanded matched views record missing large Party Crasher advertisements, differing holograms, source grading/volumetric haze and incomplete water/lava animation/reflection behavior as future fidelity work. Preserve source pixels, masks, constants and provenance when recovering them; avoid generic vertex RGB or arbitrary saturation changes.

Evidence: build_shared_map_ui.py, docs/conversion/shared-map-ui.json, docs/conversion/ui-atlas-lifetime-validation.json and site/ui-atlas-survey-findings.json.
