# Titanfall map visibility, portals and measured limits

Scope: world-baked render path in the tested installed Titanfall 2 engine.
These are not universal map dimensions or a native-model total-prop limit.

## Why converted objects disappeared

The project reproduced position- and angle-dependent disappearance of pipes,
stairs, rocks and props. Failures involved native index submission capacity,
material/opaque/alpha partitions, access-path bounds and camera-cell data.
Looking straight ahead versus up/down does not prove different XYZ axes or
an out-of-bounds gameplay rule. The tested sources use unchanged XYZ axes.

Conservative native all-visible cell/access-path structures removed these
failures. Keep actual mesh bounds geometric; widen camera access envelopes rather
than falsifying geometry bounds. Phase Runner's tested camera envelope spans
`[-16384,-16384,-8192]` to `[16384,16384,8192]`. This is a project visibility
envelope, not the maximum playable map dimensions.

Changing mesh order or partitions requires remapping all cell/object references,
including transparent meshes. Changing lightmap pages can split meshes and
therefore changes padding, draw keys and visibility references too.

Earlier selective portal graphs culled the sky and interiors, producing
hall-of-mirrors artifacts. A future selective implementation needs watertight
cells, oriented apertures, connected interior/exterior paths, sky propagation,
state-dependent doors, and camera sweeps inside and outside each passage.
It remains unvalidated; conservative visibility plus optimization is the tested
fallback, with a larger simultaneous render cost.

## Capacities versus policies

| Constraint | Value | Evidence class |
| --- | ---: | --- |
| Submitted world indices | 3,145,728 | Audited native capacity, engine RVA 0xB72AF |
| World draw batches | 2,048 | Audited native capacity, engine RVA 0xB7304 |
| Material sorts | 8,192 | Native loader bitset capacity |
| Mesh reference/local vertex/primitive index | 65,535 maximum index | uint16 serialized range |
| Brush cut/bevel and cell child/direct-reference count | 255 | uint8 serialized range |
| Packed center and extent | signed16, maximum 32,767 | Serialized range; check both independently |
| Phase Runner world index margin | ≤95% | Project safety policy |
| Drop-Off recovery margin | ≤90% | Project safety policy |
| Phase Runner static batches | <512 | Project safety policy; light masks can multiply batches |
| Local vertex ceiling / collision group size | 60,000 / 96 triangles | Conservative writer choices |

Native mesh index cost is `3 * (triangles + (triangles & 1))`: odd triangle
counts receive pair padding. Budget the padded sum per mesh, not three times
the scene's active triangles. Disabled degenerate slots still occupy submission
storage. Dynamic light masks can split the base static draw keys at runtime.

Observed engine SHA-256:
`58eb1a1b44b30275bdd21368de264d856bc310d37d93a0f76f111f0026913487`.
Observed client SHA-256:
`002b36487fec7c98882929fbccdb506d0146bbf3270cbb964a4d21c5edf7eebc`.
RVAs and capacities must be re-audited against changed binaries.

## Reviewed budgets

| Snapshot | World indices | Meshes | Static batches | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Phase Runner documented geometry baseline | 2,924,184 | 4,982 | 479 | 92.96% of observed capacity; later entity/safety repairs preserve geometry |
| Drop-Off 0.6.0 | 2,830,530 | 3,024 | 353 | 89.980%; about 200 more triangles under its 90% policy, depending on padding |

Drop-Off has 942,146 serialized triangle slots, of which 942,014 are active.
Its 132 disabled slots are 108 start covers and 24 orphan-lamp faces. Capacity
checks establish that the audited submission fits, not a stable frame rate or
unlimited dynamic effects. Further substantial recovery needs geometry savings
or a separately validated model/visibility backend.

No universal map-size limit, native entity/prop total, VRAM cap, selective portal
capacity or support for all Apex versions was established.

## Sources

`audit_world_draw_budget.py`, `guard_native_sort_capacity.py`,
`repair_camera_visibility.py`, `native_preview_cells.py`,
`docs/conversion/engine-limits.json`, and
`docs/composite/local-repairs-2026-10-07.md` / `validation.json`.
The copied Composite engine-limit ledger's `current_release` is Phase Runner;
use the 0.6.0 receipt for current Drop-Off usage.
