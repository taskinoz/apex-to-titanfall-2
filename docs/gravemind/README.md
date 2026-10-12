# Titanfall 2 and Apex Legends maps: verified conversion knowledge

Recorded 11 October 2026 from the Apex-to-Titanfall conversion project. Latest
reviewed builds: Phase Runner 1.2.0 and Drop-Off 0.6.0, tested through Northstar.
This collection records observations from Apex rBSP 47 and Titanfall 2 rBSP 37.
It does not establish compatibility with every Apex season or engine build.

## Articles

- [BSP, model and serialized record layouts](binary-formats.md)
- [Collision decoding, ownership and traversable tunnels](collision.md)
- [Visibility, portals and measured engine limits](visibility-and-limits.md)
- [Materials, PBR, STBSP and texture residency](materials-and-streaming.md)
- [Lightmaps, character lighting and the multiplayer menu stage](lighting.md)
- [Entities, safety volumes, spawns and native game modes](entities-and-gameplay.md)
- [Phase Runner and Drop-Off conversion case studies](port-case-studies.md)
- [Native test harness and release validation](testing-and-packaging.md)
- [Design requirements for a future automatic converter](converter-design.md)

## Evidence policy

Measured binary capacities, serialized field ranges, project safety margins and
unverified ideas are different kinds of knowledge. Each article states its scope
and cites workspace-relative evidence paths. Those paths refer to the conversion
project; they are provenance references, not files hosted by Gravemind.

Structural validation is not proof of visual fidelity, successful loading is not
proof of collision, and a single-client run is not proof of multiplayer balance
or performance. Unknown formats and omitted objects must remain explicit.

The two ports bake selected static props into world meshes. Their world-index
budgets do not establish the limits of Titanfall's native model/entity renderer.
All-visible cells are a tested fallback, not a validated selective portal builder.

The articles contain technical findings and project-authored documentation.
Original game archives, extracted game assets and credentials are not included.

## Authoritative sources

`docs/conversion/APEX_TO_TITANFALL2.md`, the corresponding binary/layout/limit
ledgers, `docs/conversion/GAMEPLAY_MODES.md`, and the source scripts underpin
Phase Runner. Its static inventory retains explicitly versioned 1.0.0 provenance;
1.1.0 adds gameplay and 1.2.0 restores source safety areas.

For Drop-Off, prefer `docs/composite/validation.json`,
`docs/composite/local-repairs-2026-10-07.md`, and
`docs/composite/inventory-summary.json` for 0.6.0 measurements. Some introductory
paragraphs in `docs/composite/CONVERSION.md` retain older budgets, the old display
name and earlier feature descriptions. Its copied engine-limit ledger also has
a Phase Runner `current_release` section. Do not treat those as current Drop-Off
measurements. The current receipt resolves these discrepancies.

Future converter architecture in this collection is a proposal; it is not an
existing universal, one-command conversion tool.
