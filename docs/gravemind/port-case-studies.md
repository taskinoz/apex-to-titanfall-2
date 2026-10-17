---
id: gm_01m4nfwh6d8em5ts5pzrv4cbwb
title: "Titanfall map conversion case studies: Phase Runner, Drop-Off and Party Crasher"
description: Versioned current port budgets, recoverable props, remaining omissions and native evidence
tags:
  - titanfall-2
  - apex-legends
  - map-conversion
  - phase-runner
  - drop-off
  - composite
  - case-study
  - party-crasher
project: apex-to-titanfall-2
status: verified
created: 2026-10-11T12:44:29.261Z
updated: 2026-10-17T16:11:56.580Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 8
---
# Phase Runner and Drop-Off: verified conversion case studies

Reviewed 11 October 2026; latest tested project releases were built 6–7 October.
These are playable visual/collision adaptations, not full Apex gameplay ports.

| Map | Apex source | Titanfall command | Northstar package | Reviewed release |
| --- | --- | --- | --- | --- |
| Phase Runner | `mp_rr_arena_phase_runner` | `map mp_phase_runner` | `PhaseRunner` | 1.2.0 |
| Drop-Off | `mp_rr_arena_composite` | `map mp_arena_composite` | `ArenaComposite` | 0.6.0 |

Both tested source BSPs are version 47; targets are version 37. Drop-Off is the
displayed map name, while Composite remains the internal source/package name.
Map labels/loading art are adapted separately from physical map data.

## Phase Runner

Source coordinates are recentered by subtracting `[26000,19000,0]`. The release
uses conservative all-visible geometry, world-baked static props, source collision
plus targeted tunnel repairs, native character lighting, and interior illumination.
An authored catwalk/rail adaptation improves tunnel traversal.

Twenty firs are complete fixed LOD2 rather than player-sized brush impostors.
The grounding audit found one trunk about 47.6 units above rendered snow. Nearby
omitted props were small vegetation, not a structural support. Nine trunks were
lowered eight units below minimum sampled support; eleven embedded trunks stayed
unchanged. The correction propagates to visual, collision and lighting transforms.
Grounding is a deliberate local repair, not a rule to snap all source objects.

The static inventory is a 1.0.0 snapshot: 5,425 included of 16,376 placements
inside the arena, 10,951 omitted across 68 model types, and 486 outside the filter.
Foliage (9,537 omitted) dominates, followed by rocks (527) and industrial props
(339). Do not add the twenty firs again to these documented included counts;
later 1.1.0 gameplay and 1.2.0 safety changes do not represent new recovered props.
Compiled model availability and target inclusion remain separate properties.

The documented geometry baseline has 972,628 triangles, 2,924,184 padded indices,
4,982 meshes and 479 static batches. Seven lightmap pages, thirty local interior
lights and 39,821 character probes are recorded. AI navigation, full shader/FX
parity, dynamic source behavior and full spatial mip streaming remain incomplete.

## Drop-Off

0.6.0 accounts for all 8,356 source static placements:

| Disposition | Placements |
| --- | ---: |
| Included | 4,264 |
| Excluded by all-visible draw budget | 2,051 |
| Remote/menu/backdrop selection exclusion | 1,884 |
| Source asset not recovered | 147 |
| Removed detached wind shield | 1 |
| Removed orphan attached lamp | 1 |
| No rendered sections after atmosphere/glow filters | 8 |

The local-origin filter has 6,472 placements and is a project selection policy.
Budget exclusions can be recoverable assets, not missing files. Fourteen selected
solid placements have no decoded source collision (small cable stoppers, puddle
decals and bamboo). Neutral fallback source signage covers 564 rendered triangles;
`empty_model` covers one. Source layered shaders, animation, reflections, spot
light fidelity, doors, audio and particle behavior are incomplete.

0.6.0 restores source server supports 2914/2916 and stacked tank containers
5287/5288 at original transforms using complete LOD3, adding 910 triangles.
The containers' existing world collision is retained. Lamp 5093 belonged to the
previously removed wind shield 4924; its 24 draw/shadow faces are disabled.
No new guessed collider fills that gap.

The wall-lighting repair targets 2,250 painted-wall triangles with higher-resolution
charts and proper native page bindings. Final cost: 942,146 serialized slots,
942,014 active triangles, 2,830,530 padded indices, 3,024 meshes and 353 batches.
The 90% project policy is nearly reached; substantial new props require savings.

35 regressions passed. Native captures cover all four reported locations and
both control entrances. Three native contact rays hit retained colliders.
Postmatch returned to the lobby, then stock Coliseum and Drop-Off reloaded in
the same process without logged script errors. This does not identify the cause
of an earlier user crash or establish multiplayer stability/performance.

## Version provenance

Use current receipts rather than historical summaries. Drop-Off's initial guide
still contains its old name and an earlier 86% budget. The copied engine-limit
JSON's current-release measurements describe Phase Runner, not Drop-Off. The
0.3.0 source-layout record supersedes 0.2.0 guessed rope placements/removed clips.
0.6.0 validation and repair records are authoritative for its final native build.

## Sources

Current `northstar/*/mod.json`, `docs/conversion/MISSING_CONTENT.md`,
`docs/conversion/trees.json`, `docs/conversion/tree-grounding-before.json`,
`docs/composite/inventory-summary.json`, `docs/composite/MISSING_CONTENT.md`,
`docs/composite/validation.json`, and versioned repair documents.

## Party Crasher 0.4.0 boundary and rooftop recovery — 14 October 2026

A measured priority swap recovers 380 exact source static placements: 168 facade/window sections, all 42 large boundary-rock placements, 42 roof vents and all 128 source solar panels. The final scene contains 2,532 included source placements of 13,825; 11,285 local placements remain omitted and eight are outside the selected region. These counts describe retained geometry, not complete visual parity or a native entity limit. Roof vegetation and dense inset/window modules still remain omitted.

Final world submission: 1,022,586 triangles, 3,072,114 padded indices (97.66% of 3,145,728), 3,185 meshes and 358 static draw batches. The remaining 73,614 indices do not certify AI, multiplayer performance or an unlimited effect budget. No gameplay entities were added. Existing entities, 67 out-of-bounds and two hurt triggers, source collision exclusions, character probes, world lights and used lightmap charts were retained. Existing material bindings and uber buffers compare identically against the immutable baseline. Six new material definitions use recovered Apex textures and native PBR; layered source shading remains approximate.

Use a priority inventory rather than greedily adding small objects: a facade-first candidate added 270 placements in 73,910 triangles; the accepted boundary/roof candidate adds 380 in 72,590 triangles. Boundary rock type 01 uses authored LOD3, types 02/03 authored LOD4. Solar panels use the last available authored LOD2. Original source transforms and source PHY/BVH surfaces are preserved; no guessed patch planes or collision boxes were inserted.

The independent binary audit passed 2,930 checks. Native checks from the exact mounted payload verified 29 new collider contacts, clear supported starts for both teams, postmatch return, stock Coliseum load and Party Crasher reload. Eight native edge/roof views and six matched native/R5R references were saved. Remote camera views temporarily remove boundary/hurt trigger entities only in owned diagnostic runtimes; normal gameplay checks reload the map and verify all 69 safety entities. Never infer gameplay safety from these diagnostic pictures. The shared ApexMaps.UI companion remains unchanged and no new uimg atlas is added.

Failures are retained explicitly. One prolonged diagnostic session reported an unregistered goalState in earn-meter code, followed by a shutdown access violation. Cause and relation to earlier stress failures remain unisolated. Fresh short-session checks passed; they do not erase that failure or certify long sessions. One R5R launch had a server-connection overflow; retry captured the roof references. An all-five-map retry reported a texture-allocation failure; the final new native checks used Party Crasher, Drop-Off and shared UI with the engines running serially. Do not count historical all-five-map atlas validation as a new 0.4.0 stress certification.

Evidence: recover_party_structure.py, verify_party_structure.py, capture_party_structure.py, verify_party_structure_runtime.py; docs/candidates/party-crasher/port-0.4.0/{inventory-summary.json,placement-inventory.csv,validation.json,FAILED_DIAGNOSTICS.md}; immutable site snapshot 2026-10-14-party-structure. The player ZIP and installed runtime are hash verified; old mod/preferences and the previous download remain backed up.

## Firing Range 0.4.0 surface repair — 15 October 2026

The 0.3.0 inventory's 976 "Invalid static triangle strips" omissions were stale. Those VG sections are direct triangle lists without a strip table, which the decoder now reads. 74 of them form the central VTOL landing pad near Titanfall `(1523, 2008, -700)`: deck, tarmac, three arm towers, pipes, supports, eight sewer staircases, air units and runway lights. All were restored. The remaining 900 grass cards and two dead trees are budget omissions, not decode failures.

Native vertical traces against the restored visuals showed that the deck, pipes and supports already had source world collision (within 0–5 units). **The staircases had none**: their IRPS collider exists only in the prop `.phy`. Appending that collider fixed it. Lesson: "world/source-owned" labels for omitted props are a default, not a verified fact. Trace the restored surfaces before claiming that collision exists.

The repair also baked transparent-sand coverage (`1 - saturate(5*mask - 5 + 6*vertexAlpha)`) into a 2048 atlas on the native world-alpha shader. Previously the overlay rendered opaque over the metal floors. The atlas gives about 0.7 texels/unit against about 4 in the source, so blending is soft. The bones and rock 1292 moved from LOD2/3 to authored LOD1. Four of twelve zipline arms fit. Final: 3,080,502 padded indices (97.93%), 894 binary checks, 20 native surface contacts, both teams, postmatch → lobby, Coliseum and reload, with no errors.

## Party Crasher 0.5.0 signage — 15 October 2026

0.4.0 placed all 33 flex-screen frames but none of the 4-triangle `survival_modular_flexscreens_04` panels. 0.5.0 adds the panels, 33 signs and 12 banners (78 placements, 3,426 triangles, 97.99%). Twelve Angel City banners and an alpha text-decal sign were skipped. Screen advertisement art is script-driven in Apex, so the panels show the static source material.

A duplicate-triangle survey found no meaningful budget. Of 11,093 same-material coincident pairs, 9,885 are intentional two-sided faces (opposite winding), about 517 are stacked `echo_big_screen_animation_01` frames, and only about 100 are true duplicates. At about 98%, further large recovery on either map needs the native static-prop path (models outside the world index budget), not more baked world geometry.

## Applying the Party Crasher / Firing Range fixes to Phase Runner and Drop-Off — 16 October 2026

Measured on Phase Runner 1.6.1 and Drop-Off 0.10.1 using `audit_legacy_collision.py` plus adapters for
`analyse_visibility.py` and `classify_world_uv.py`. Reach was flooded from the BSP spawns without
out-of-bounds volumes, so the invisible-collision fractions are upper bounds.

| Fix | Phase Runner | Drop-Off |
| --- | --- | --- |
| Grid rebuild re-enabling disabled colliders | Not affected (7,134/7,654 brushes, 25,916/25,998 headers active as intended) | Not affected (no grid-disabled primitives) |
| Prop normal axis order | Correct (median \|cos\| 1.0) | Correct |
| Two-layer bm blending | Missing on 187k triangles; snow/moss ground visibly wrong versus R5R | Missing on 52k triangles; minor next to the lighting gap |
| World-projected UV scale | Snow/moss ground tiles 3–8× too coarse (Apex 1/256 per unit) | Only a 6k-triangle grunge decal |
| Coarse drawn LOD vs full collider | 18.2% invisible; boundary cliffs `rock_sharp_lava_moss_desertlands_03/04` have only about 66% of their collider within 24 units of the drawn mesh | 4.5% invisible, mostly intentional clips and large landing structures |
| Omitted props with world-baked collision | Small share | 8 invisible `ship_console_control_med_v1` (about 50% of each surface on collision, about 12% drawn); server stand 8176 and parking post 4860 partially |
| Hidden-mesh culling | Has its own playable-visibility pass | 87 meshes / 27.6k triangles (about 83k indices) never seen; no menu-stage marker found, so check before culling |

Drop-Off's largest visual gap against R5R is overall lighting (much darker and bluer), not blending.

### Outcome — 16 October 2026

**Phase Runner 1.7.0**
- **Blending (`phase_runner_blend.py`).** 26 materials were rebound to native Coliseum wld bm in a new
  `phase_runner_blend.rpak` (Postload attached to `mp_coliseum.rpak`). `build_preview_stbsp.build(...,
  extra_paks=...)` lists materials across all nine packs. Source vertex alpha matched 100% for 27 of 29
  materials. Prop SMDs were rebuilt from QC, so position matching uses 0.5 units.
- **World UVs.** Rewritten in the source frame (port + 26000/19000).
- **Kept single-layer.** `asphalt08_cracked_bm` produced white specks in native captures, and two
  materials had unmatched source alpha.
- **Collision (`phase_runner_collision.py`).** Uses `collision-ownership.json` (explicit
  first_brush/first_header ranges per placement) and finds each rock's drawn LOD by vertex matching.
  210 rocks were replaced. Owners with any disabled primitive were skipped, so tunnel and catwalk
  exclusions are preserved.
- **Spawn snapping must stay off on Phase Runner.** The arena floor covers buried cliff rock, so the
  Firing Range rule pulled floor spawns up to 200 units underground. All 84 spawns pass natively without
  it.
- **Results.** Invisible reachable collision went from 18.2% to 1.0%.
- **Still wrong.** The light-grey `terrain_transition_preview` atlas (an earlier Codex bake) still
  differs from Apex's dark asphalt and patchy snow ground.

**Drop-Off**
- The 8 invisible ship consoles are in Apex's sealed side control rooms, which the port intentionally
  keeps closed. Harness cameras die there in both games, so there is no gameplay impact.
- Nothing from the Party Crasher toolset has a meaningful payoff on Drop-Off; its overall lighting is the gap.

**Overflow 0.4.0**
- **Blending.** `apply_layer_blends.py` covered 18 materials (it now gives neutral fallbacks for missing
  layer-1 PBR maps).
- **Collision and invisible objects.** `match_collision_to_render.py` replaced 51 placements.
  `recover_invisible_props.py` (generic for new_arena_ports maps) drew 53 omitted props whose surfaces
  lay on undrawn world collision. Invisible collision went from 3.7% to 2.8%.
- **Tooling fixes.** One Overflow trigger uses an unsupported collision descriptor; `analyse_visibility`
  now skips it (reach only grows). The route runner needs an explicit respawn on Overflow (`capture_route.py`).
- **Contact check.** Traces over the yellow pipes stop on a pre-existing clip at z 1244.
  `verify_collision_match` now excludes contacts that stop on collision active both before and after.
- **Crash.** Overflow crashes Northstar at spawn in about 1 of 5 fresh sessions, in 0.3.1 and 0.4.0
  alike: null-pointer reads in `server.dll` / `engine.dll` at varying addresses. The cause is not
  identified.
- **R5Reloaded.** It currently fails to load `mp_rr_aqueduct` ("Connection to server overflowed"), so
  Overflow 0.4.0 was compared only against 0.3.1 and archived R5R views.

### Phase Runner 1.7.1 and shared UI 0.1.1 — 17 October 2026

- **Base floor flicker.** Apex decals (`cement_stripes_decals_vert`, `s2s_*` bolt decals) were drawn
  opaque and coplanar with `s2s_wall_trim_01_vc`. They are now alpha-blended decals (Homestead base
  material 0x92b5ba61a3bf2e7a with decal depth bias `rasterizerFlags 0x16` and an opacity map in slot
  13).
  - The shader set must be the art-supports pack's `0xC0F822522D0CBA1E`.
  - The glass-console pack's `0x5BBBF75FE4EADB81` is a glass shader, and referencing it from these
    materials stopped the map from ever loading (the game stayed at the menu with no log error).
- **Stand-in lettering.** The Apex "CAUTION LOADING AREA" lettering is `signage_building_02`.
  `repair_dev_materials.py` had substituted `sign_warning_yellow` (a CCTV sign texture) for it, so that
  material is now drawn fully transparent.
- **Stripe colour.** The stripe's yellow is source vertex colour (213, 190, 74); it is baked into the albedo.
- **Container gaps.** `industrial_cargo_container_320_01` LOD3 keeps only the box (z 8–136); the frame
  (z 0–144) exists only at LOD ≤ 2. `phase_runner_details.py` appends the missing frame sections for
  17 drawn containers.
  - Their lightmap UV and page are copied from the nearest drawn vertex of the same container, so no
    bake is needed.
  - Frame triangles are grouped by (material, page), because Phase Runner is at 490 of 512 static
    batches.
- **Catwalks.** The 0.1.37 catwalks followed the raw Apex path z, which jumps ±14 units every few points.
  Every catwalk vertex (render, shadow, collision) now moves by `gaussian(z) − z` along the route, and
  the arena ends ramp onto the floor (−758 / −762). Collision is rebuilt from the moved triangles.
- **Minimaps.** Minimaps looked washed out on all five maps. `texconv -f BC7_UNORM_SRGB` without `-srgb`
  treats PNG input as linear and re-encodes it, lifting the dark Apex overview art from a mean of 42 to
  110. The fix is to add `-srgb`. Other builders using the same call (banners, display faces,
  presentation art) are probably affected too.
- **RSX patch packs.** A local RSX 2.3.0 build (`legacy-work/rsx-build`, VS 2022, vcpkg curl/opus, built
  from a path without spaces) loads R5R's `common(01)`/`(02)` chain once the ZSTD base is decompressed
  with `decompress_rpak.py`. RSX itself cannot read ZSTD.
  - Page patching then fails: 50,807 pointer headers point outside their pages.
  - Likely cause: the patches were made against a different base than R5R's rebuilt `common.rpak`.
  - `signage_building_02` therefore remains unrecovered.

## Party Crasher 0.6.4 Northstar screen artwork — 18 October 2026

The existing star placeholder in `oasis_signs_ad_atlas_01` is replaced with a new landscape Northstar image matching the Drop-Off banner family: white Titan emblem, NORTHSTAR lettering, navy/purple panels and cyan accents. Original artwork and the complete built-in imagegen prompt are retained in `art/northstar/party-crasher-northstar-screen-v1.png` and `party-crasher-screen-v1.md`.

`party_crasher_northstar_screen.py` changes only the existing atlas panel. The source panel rectangle (1266,749)–(2047,1180) maps to native pixels [633,374,1024,591) in the existing 1024-square BC3 sRGB atlas. Its 11 mip levels and header remain unchanged; 80,111 compressed blocks outside the affected panel are byte identical. Preserve existing sRGB bytes rather than applying another gamma conversion. All 599 material definitions/bindings and the pack's 1,888-asset inventory compare identically. No BSP, STBSP, geometry, collision, lights, scripts, UVs or UI atlases change.

The exact mounted candidate was captured from the previous q40 screen camera and a backed-off full-screen view. Artwork is upright and neighboring Oasis signs remain intact. Stock Coliseum and Party Crasher then reloaded with no logged script errors or native crashes. These are single-client visual/reload checks, not new multiplayer or performance certification. Evidence: `docs/candidates/party-crasher/port-0.6.4/validation.json` and `screen-in-game.png`. Previous material pack, original atlas and metadata remain in the isolated build folder `party-crasher/northstar-screen-v1/` for rollback.
