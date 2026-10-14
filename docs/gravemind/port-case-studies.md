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
updated: 2026-10-14T06:16:41.328Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 3
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
