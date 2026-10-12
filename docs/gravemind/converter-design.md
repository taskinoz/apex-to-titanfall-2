# Requirements for a future Apex-to-Titanfall map converter

Status: proposed architecture informed by tested ports. The current implementation
is a set of project scripts with retained intermediate/template dependencies,
not an arbitrary-map, clean one-command converter. Supported evidence is limited
to the tested source BSP 47 and target BSP 37 combinations.

## Stages

1. Inspect immutable hashed BSP/VPK/RPak/STARPak/PHY inputs, versions, external
   lumps, entities, static placements and dependencies.
2. Extract only referenced assets into owned caches, preserving stream offsets
   and source hashes; leave original archives read-only.
3. Normalize geometry, transforms, material slots, collision and ownership into
   a typed intermediate representation; version-dispatch unknown layouts.
4. Plan selection by native padded index and draw-key cost, collision support,
   material residency and explicit gameplay behavior requirements.
5. Compile native draw/cell/collision structures, dependency-closed materials,
   catalogue and authored/adapted entities with checked ranges and relocations.
6. Bake surface lighting and native character probes with distinct menu/gameplay
   environments; reserve all chart allocations and use hardware light remaps.
7. Validate structure and native behavior, retain screenshots/logs/trace evidence,
   then package and hash a clean Northstar release with rollback.

Suggested commands `inspect`, `extract`, `plan`, `compile`, `bake`, `validate`
and `package` are proposed interfaces, not existing unified CLI functionality.

## Intermediate representation

Retain every original entity key/value pair and placement ID. Record source and
target origin/angles/scale/skin, selected author LOD, material assignments,
geometry hashes, backend and disposition. Intentional grounding or replacement
deltas need explicit reason and before/after data; never overwrite original origin.

Collision records need owner, source kind (world BVH, inline STAR, IRPS,
embedded BVH, visual fallback or adaptation), target representation, active flag,
contents, geometry hash and disabled reason. Produce one final active ownership
ledger rather than forcing readers to merge historical repair overlays.

Materials need source alias, target GUID, shader provenance, channel mappings,
alpha mode, dependency closure and fidelity adaptations. Visibility needs actual
geometry bounds, camera envelope and mode (`conservative` or validated portals).
Lighting needs caster/receiver masks, native light mapping, atlas reservations,
probes and isolated menu environment. Distinguish capacity limits, field ranges
and project margins in the same budget report.

Stages need implementation hash, input/output hashes, status, diagnostics and
reproducible parameters. Omissions need a source ID, reason and recovery
requirements. Reasons include budget, missing source, unsupported layout,
unsupported behavior, outside selection, deliberate adaptation and unverified.

The existing design contract is
`docs/conversion/conversion-project.schema.json`; historical scripts do not all
serialize that schema yet. Layout headers, 128-slot ledgers and versioned source
manifests provide a starting implementation reference.

## Separate backends and future work

World baking is tested and simplifies static recovery, but consumes world
submission capacity and discards dynamic LOD, animation and instancing. Dense
foliage and repeated props motivate a native-model backend; it needs independent
format, loading, collision and native-render capacity validation. It cannot inherit
the world-path limits or be called complete because one mesh export succeeded.

A true spatial streaming backend needs native coverage/residency semantics and
VRAM-pressure tests. A selective portal backend needs sky-preserving interior
connectivity and camera sweeps. Gameplay adaptation needs objectives, navigation,
conditional entity states and lifecycle validation separately from geometry.
Source identity matches do not certify behavior equivalence.

MRVN-Radiant was evaluated as a development/compiler starting point, not a complete
editor or universal Apex import pipeline. The project pins commit
`8022aefcf9506786fe9edf138dbf48cde0fa82f6` and retains a compiler patch. That is
historical provenance, not a claim about the current state of any upstream fork.

## Sources

`docs/conversion/APEX_TO_TITANFALL2.md`, `conversion-project.schema.json`,
`TOOLCHAIN.md`, `toolchain-versions.json`, `SOURCE_INDEX.md`,
`respawn_conversion_layouts.h`, `docs/composite/CONVERSION.md`, and the latest
map validation receipts. See [case studies](port-case-studies.md) for concrete
scope and remaining omissions.
