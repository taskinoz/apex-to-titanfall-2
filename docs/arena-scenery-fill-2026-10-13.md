# Scenery recovery at 97% of native world capacity

Phase Runner 1.6.0 restores 432 source placements; Drop-Off 0.10.0 restores
366. This pass implements the user's requested 97–98% **rendering capacity**
target. It does not recover 97% of all Apex objects.

| Measured native world budget | Phase Runner | Drop-Off |
| --- | ---: | ---: |
| Added source placements | 432 | 366 |
| Added render triangles | 42,737 | 74,003 |
| Padded world indices | 3,052,710 | 3,053,136 |
| Native world index capacity | 3,145,728 | 3,145,728 |
| Occupancy | 97.04% | 97.06% |
| Unused world indices | 93,018 | 92,592 |
| Static batch runs / native capacity | 490 / 2,048 | 379 / 2,048 |
| Added collision triangles | 4,710 | 42,468 |
| Added collision headers | 50 | 443 |
| Added lightmap pages, 1024 square | 1 | 1 |
| Added dynamic entities | 0 | 0 |
| Local source placements rendered | 5,857 / 16,376 | 4,630 / 6,472 |
| Local placements still omitted | 10,519 | 1,842 |

The ~2.95% world index reserve is separate from dynamic entity slots, native
model rendering, texture residency, AI navigation and CPU budgets. Existing
spawns, objectives, lights, character probes, minimaps, menu isolation and
collision exclusions remain unchanged. Game mode entities can still spawn;
AI navigation is not supplied by this pass. Full multiplayer and AI load
performance has not been established by the single-client harness checks.

The usual conservative project policy remains 95% for other conversions.
This is a scoped, explicitly requested exception, capped at 97.5% by the
builder. The 2,048 batch ceiling and 3,145,728 index ceiling are separate native
world submission limits. Dynamic light masks can split static batch runs.

## Restored content

Phase Runner adds ground plants, moss/grass and flowers across supported
terrain, eight small snow rock clusters, eight generators and eleven power
cells. It retains the earlier twenty trees. Plants retain the source XY,
rotation and scale; a vertical ray against retained geometry places their
roots into nearby ground for tall plants. Flat ground-cover uses authored LOD2
and places its lowest vertex half a unit above support, avoiding the buried
flat meshes found during close-up QA. Steep surface patches that require their
original wall/rock support are omitted. Plants needing more than 48 units of
vertical correction are skipped rather than left suspended. No hanging moss, ceiling vents,
unrecovered screens, test boxes or new trees are included.

Drop-Off adds utility conduits and clamps, tanks, crates, cargo, furniture,
planters, desk accessories, rack arms, panel corners and one roof section.
Selection is confined to the gameplay vicinity: |X| < 3700, -200 < Y < 7100,
and -256 < Z < 2200. This is a recovery policy, not a claim about native Apex
playable bounds. Under-map/background furniture is excluded. Both maps use
distributed spatial selection rather than spending the budget in one corner.

The exact added source indices, models, transforms, skins, authored LODs,
ground adjustments and collision methods are in
[Phase Runner's recovery ledger](scenery-fill/phase-runner-recovered-placements.json)
and [Drop-Off's recovery ledger](scenery-fill/drop-off-recovered-placements.json).
Older full source inventories remain baseline records. Merge these recovery
indices into them when calculating current omissions; do not treat a historical
CSV omission as a newly missing object.

The current complete remaining placement lists are
[Phase Runner](scenery-fill/phase-runner-remaining-placements.csv) and
[Drop-Off](scenery-fill/drop-off-remaining-placements.csv), including the
separately identified remote/menu/backdrop exclusions. Dynamic behaviour and
unrecovered shader limitations remain in the historical conversion reports.

## Geometry, materials and collision

Read original RMDL/VG sections with their vertex RGB, skin and UVs. Select
authored LOD up to LOD2 for foliage and LOD3 for other additions; do not simplify by discarding arbitrary triangles.
Bake transforms into the existing world path. Split spatial mesh groups and
material sort batches to preserve uint16 local indices, with a 60,000 local
vertex policy. Preserve the existing attribute, collision and lightmap buffer
prefixes. Reorder the complete mesh table into native opaque/transparent
partitions and remap references. Keep the working conservative camera domain
and all-visible tree. No render portals are introduced.

Opaque surfaces reuse native PBR materials where possible. New material packs
include source albedo and available normal, gloss and specular channels;
missing channels have explicit neutral values. Source foliage opacity is
folded into albedo alpha. Native cutout depth, prepass, colour and shadow shader
dependencies use unique identifiers, two-sided rasterization and alpha-coverage
mips. BC3 albedo is tagged sRGB, preserving the compressed blocks. Vertex RGB
is retained; source vertex alpha is not used as the native transparency mask.
New textures are resident in `phase_runner_fill.rpak` / `drop_off_fill.rpak`.
New planter glass uses an opaque native PBR approximation. Its source alpha
remains in the texture, but the full Apex glass shader is not reproduced;
the earlier truck-glass repair is preserved independently.

Source nonsolid plants remain nonsolid. Solid additions use decoded source
IRPS/embedded BVH shapes, or full source LOD0 surfaces when no exported shape
exists. Do not make blocking boxes for foliage or use the coarse render LOD as
collision. Already owned colliders are excluded. Rebuild spatial collision
references from the existing **active** primitive set plus additions; preserve
disabled tunnel barriers and intentional room closures. Independent collider
AABB checks cover pilot, Titan and objective clearances before launch.

Only new geometry gets new baked pages, using the established sun/sky and
30 Phase Runner / 60 Drop-Off interior fixtures. Existing lightmaps and probe
data remain byte-identical. New pages match each map's existing ambient policy:
RGB (0.025, 0.027, 0.032) with sky factor 0.4 + 0.6 visibility for Phase Runner;
RGB (0.09, 0.10, 0.12) with sky factor 0.65 + 0.35 visibility for Drop-Off.
Native cutout foliage is a static approximation; Apex wind and foliage-specific
shading are not reproduced. The native material catalogue gains the new names
while retaining the previous streaming payload. Compacting the BSP relocates
absolute GameLump pointers; normalized payloads remain identical.

## Verification and reproduction

The candidates passed 289 offline checks. Native checks cover 23 camera-matched
Apex/port views, sixteen fixed-position angle sweeps, 36 contacts against newly
added colliders and both teams' starts on both maps. Saved Apex images are
hash-verified source captures, not new R5R runs. Pilot and Titan spawn hulls
are checked during mode initialization. Drop-Off checks Pilots vs Pilots and
FFA in addition to its captured Skirmish session; Phase Runner checks Skirmish,
Pilots vs Pilots, CTF, Hardpoint, Fastball and Attrition initialization.
This does not validate an AI wave, objective completion or a full match.
Postmatch returns to the lobby, followed by stock Coliseum and both candidate
maps reloading in the same process with clean script logs.

The withdrawn 1,802-placement candidate had a CTF switch crash in a long-lived test process after an EA
disconnect/reconnection. A fresh candidate session loaded CTF successfully.
The legacy `PhaseRunnerModes_Check()` debug command then produced a Squirrel
type error in a separate test; the baseline control did not reproduce it.
The independent harness checks validate live spawn entities and objectives
without relying on that command. Close-up QA also found buried flat foliage;
the final 432-placement candidate uses a more detailed LOD, correct support
height and excludes steep surface patches lacking their original support.
The withdrawn candidate is not packaged or installed. Final native checks
use the corrected BSP hash. The earlier failure's cause is unconfirmed;
these later passes do not establish long-session stability.

Run `plan_arena_fill.py`, then `build_arena_fill.py prepare <map>` and
`build_arena_fill.py build <map>` against the recorded 1.5.0 / 0.9.0 baselines.
Run `verify_arena_fill.py`; stage both candidate packages in the isolated
Northstar profile. Use `verify_arena_fill_runtime.py capture <map>`, `modes`
and `reload`. Inspect native screenshots before promotion.
`finalize_arena_fill.py` requires those receipts and matching hashes, then
copies verified runtime files into the working packages. Release packaging
and installation retain previous versions for rollback.

Candidates, private native logs, source exports and binary snapshots are under
ignored `output/arena-fill/`. Public validation summaries and recovery deltas
are in `docs/scenery-fill/`. Player ZIPs contain only runtime files, installation
instructions and an actual in-game screenshot. Historical 1.5.0 / 0.9.0 ZIPs
and the complete baseline runtime snapshots remain available.
