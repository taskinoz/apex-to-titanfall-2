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
updated: 2026-10-28T09:13:17.390Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 9
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

## Which texture a `c_uvN` transform applies to — 15 October 2026

A material's `c_uv1RotScaleX/Y` and `c_uv1Translate` constants do not necessarily scale the base UVs. In the `rib_giant_large_01` source shaders, the VS passes UVs through unchanged (`mov o0.xy, v2.xy`). The PS samples albedo (t0), normal (t1) and gloss (t2) at the raw UV and applies the ×8 `c_uv1` transform only to the **detail normal** (t3). The rib albedo is an unwrapped island atlas, so scaling base UVs by 8 tiled the atlas gaps and produced dark streaks. That proposal was rejected in Firing Range 0.4.0. Before applying a UV constant, trace which `sample` instruction consumes the transformed coordinate (in the `inspect_apex_shader.py` disassembly).

Transparent-overlay world layers (for example `sand_desert_02_bm_transparent`) must not ship as opaque. Firing Range 0.4.0 bakes the source coverage equation into a per-triangle atlas on the native world-alpha shader (homestead `0x92b5ba61a3bf2e7a`) with neutral PBR. One UV set drives every channel, so the albedo is atlas-resampled as well. At 2048² over about 2.34M sq units, sharpness is about 0.7 texels/unit against about 4 in the source. Area-weighted packing would give only about 1.4×. A sharper result needs a shader with separate coverage UVs.

## World-projected UVs and the real vertex colour — 15 October 2026

**World-projected albedo.** Many Apex `wld` pixel shaders rebuild the world position (`add rN.xyz, vK.xyz, cb2[0]`) and compute texture coordinates as `(x, -y) . c_uvNRotScale + c_uvNTranslate`. The mesh "UV" for such a material is only the raw world coordinate. Ports that sample those UVs directly repeat the texture once per unit, which averages to a flat colour: the user-reported grey rubble, olive moss and grey snow. Phase Runner's 0.1.9 moss fix was a hand-made instance of this. `classify_world_uv.py` traces, for every material's PS, the `dp2` coefficient row (which `c_uvN`) and source operand (world position vs mesh `v0`) feeding a texture sample. Validation: it independently derives `sand_desert_02_wld` → (x, -y)/256, the hand fix that was verified in game. Party Crasher had 13 such materials (8,879 triangles), Overflow 2 and Firing Range 4. Note that mesh-UV materials can also carry non-identity transforms (e.g. `glass_window_bulletproof01` ×2, scrolling water).

**Real vertex colour.** For the Apex v47 `VERTEX_LIT_BUMP` records read here, bsp_tool's field names are misleading. The 32-bit field it calls `negative_one` is the real RGBA vertex colour: plain floors are 0xFFFFFFFF, concrete is R=G=B≈242, and b2t overlays carry a smoothly varying alpha. The field it calls `colour` is packed tangent-like data: byte 2 is about 1 and byte 3 is 0 or 128. Reading `colour` as RGB is what produced the "red terrain / green structures" that led to disabling vertex colour. Blend-overlay coverage computed from the wrong field covered whole courtyards. With `negative_one` byte 3 it reproduced R5R's edge-only snow (checked with a top-down coverage map against matched captures). Vertex-colour RGB tint (e.g. `concrete_polished_ground_clean_seamless_01_pattern` multiplies albedo by `v1.xyz`) can now be revisited per material using the correct field.

**b2t overlays.** Source opacity is `(1 - saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)) * albedo.a * c_opacity`, with the mask slot traced separately (t5 or t6). Party Crasher 0.5.1 bakes it per triangle (48 px tiles, 2048 atlas) on the native world-alpha shader and retires triangles whose coverage is zero everywhere: 615 of 2,161, freeing world-index budget.

## Native two-layer blending for Apex "bm" materials — 15 October 2026

The previews bound only layer 1 of Apex two-layer (`_bm`) materials. That covered 222k triangles on Firing Range, 68k on Party Crasher and 91k on Overflow, so rock tops lost their sand, moss and snow, and blended ground showed one texture.

**Titanfall 2 ships a native blend shader with the same equation.** Coliseum's `world/concrete/concrete_plates_plain_wet_bm` (material `0x3C9AF4B3C2D1E723`, colour pass `0x4DD5D05777540133`, shaderset `0x1C26FE9E094361FE`) evaluates, by DXBC:

`w = saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha)`, then `albedo = lerp(albedo1, albedo2, w) * c_albedoTint`

The Apex `bm` shaders use exactly this. Native slots: t0–t3 layer 1, t15 detail normal, t22 layerBlend mask, t23–t26 albedo2/normal2/gloss2/spec2. `c_layerBlendRamp` is at uber offset 92 and `c_albedoTint` at 96. Every layer samples the mesh UV (v0). Vertex alpha arrives through the record colour (`o1.w = v2.w`); the native PS does not use vertex RGB.

**Blend inputs differ per Apex material** (traced by `layer_blend_survey.py`):
- Vertex alpha: take it from the source vertex colour (bsp_tool `negative_one` byte 3 for world geometry, VG colour alpha for props).
- Z-up materials (rock/moss/snow, rock/sand): there is no vertex alpha. The input is `saturate((n.z - c_zUpBlendingMaxAngleCos) / (c_zUpBlendingMinAngleCos - c_zUpBlendingMaxAngleCos)) * c_zUpBlendingVertexAlpha.x`. Those constants are cb0[21].w, cb0[21].z and cb0[22].x, and flat upward faces get layer 2. Bake it per vertex from the normal.

Apex sometimes projects layer 2 in world space. The native shader samples it at the mesh UV, which changes tiling but not colour. `apply_layer_blends.py` writes the alpha into the BSP vertex records (every corner has its own record, so this is safe) and rebinds materials to an embedded copy of the native shaderset. Note that Firing Range's source BSP stores surface names in upper case. In game, Firing Range's sand floors and slopes match matched R5R views closely, and Party Crasher's rubble/dirt and moss blends appear. Loads were clean with no script errors.

## Overflow lava emission regression — 28 October 2026

Matched saved R5R/Northstar lava-channel captures confirm that the port is substantially duller than Apex. Native ray checks identify the large channel as lava_river_aqueduct_01_bm (6,832 drawn triangles). Its 0.4.1 native Coliseum blend material has no emission bindings and zero emissive tint, while the reflected Apex constants specify RGB 10 for both layers and ramp 20. Source vertex alpha varies widely, so a uniformly bright replacement would lose authored masking. The separate flow surface (831 triangles) already retains source HDR tint 8.5; adjusting it alone misses the main channel. The retired coincident lava_river_v3_bm remains retired.

The accepted Overflow 0.4.2 build extends native production blend shader variants 0/1/8/9 with seven executable instructions to capture the original blend weight and add two-layer emission after diffuse compression and before existing fog. It preserves native executable lighting/fog/motion instructions, vertex bytecode, input flags and the byte-identical diagnostic variants 4/5/12/13. SHEX declarations, RDEF bindings, shader-set texture count and DXBC checksums are updated; all eight nonempty variants are accepted by a D3D11 WARP device. Five regression tests pass. Unique material/shader names and GUIDs avoid overriding the existing shared shader. Source emission/multiply textures are combined in linear space, stored as sRGB with mips, and use the source multiplier 10. Original diffuse is restored instead of the older tone-mapped glow baked into albedo.

Binary comparison permits only BSP material-string tables and absolute game-lump relocation; geometry, visibility, collision, vertex alpha, lightmaps and safety data remain unchanged. Native matched lava-channel, north-platform and overview screenshots confirm bright yellow-orange glow closer to Apex without a global exposure change. Northstar 1.31.14 single-client PS/FFA checks passed: 24 clear/supported spawns per mode, both PS team starts, weapon fire, postmatch lobby, stock Coliseum and converted-map reload, safety entities and no script/native error entries. All 354 original materials and 829 original resident textures are unchanged; eight assets are added. An initial separate emission-pack candidate stalled in an RPak loader wait while the baseline loaded; consolidation into the existing world pack then loaded and passed lifecycle checks. A cross-pack dependency/order issue is consistent with this result, but the exact wait and the earlier EA attribution were not established. Working and installed Overflow are now 0.4.2, packaged separately from immutable RC1/0.4.1. Source scrolling/distortion is not recovered, and multiply detail is frozen into the source emission maps. Dedicated servers, multiplayer load and AI remain unverified.

Local evidence: native_lava_emission.py, fix_overflow_lava_emission.py, test_native_lava_emission.py, docs/candidates/overflow-lava-2026-10-28.md and ignored output/overflow-lava-2026/. Thunderdome's current mapping has no named lava surface; Thermal Station's masked lava treatment is documented separately. Overflow's own source shader/constants are the brightness reference, not an arbitrary saturation or global exposure adjustment.
