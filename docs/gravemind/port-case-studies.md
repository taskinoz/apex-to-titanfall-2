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
