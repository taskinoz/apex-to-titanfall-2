Historical 0.2.0 record. Drop-Off source-layout corrections are documented in
[the 0.3.0 record](dropoff-source-layout-2026-10-07.md).

# Phase Runner 1.2.0 and Drop-Off 0.2.0 repair record

Internal map commands remain `mp_phase_runner` and `mp_arena_composite`.
Composite's displayed name is now **Drop-Off** in all 13 localization files.
The previous clean 1.1.0 and 0.1.0 ZIPs are retained for rollback.

## Phase Runner

Converted 82 source out-of-bounds entities and one source fall hurt volume to
native Titanfall convex trigger planes. One wholly remote source boundary has
no intersection with the target world domain and is omitted. Applied the same
(26000,19000,0) translation as the existing geometry conversion. Existing team
starts and CTF, Hardpoint and Fastball setup remain intact.

The isolated native client displays the countdown inside a source convex piece;
returning to the arena resets it. Evidence: `output/phase-runner/safety-runtime-test.json`
and `test-harness/output/20261006-221541/screenshots/phase-oob-final-7e352212.png`.

Decal separation offsets six material layers (8,740 render vertices) by 0.08
units, or 0.16 for stripes. Only render position records are appended; original
collision position indices and collision buffers are byte-preserved. Lightmap
coordinates are unchanged. The receipt now hashes render lumps separately, so
an entity-only update cannot accidentally apply the offset again.

## Drop-Off reported locations

| Report / position | Result |
| --- | --- |
| Door covered by development texture | Removed 12 placeholder triangles. Openings remain passable; Apex's eight scripted doors are not implemented. |
| Floating geometry 67.83,2236.06,17.91 | Removed detached wind shield placement 4924 and its collider. |
| Invisible north barrier 11.63,5624.97,16.03 | Removed the source-only exclusion slab; native crossing trace is clear. |
| No kill barrier below map | Restored five source hurt volumes, including the fall volume with top near Z=-657.05. Native falling player died in the test. |
| Upper platform exclusion barriers | Removed selected source-only clips, retained actual platform geometry and rail collision, and added two native access ropes. |
| Missing props -1456.67,196.37,192.03 | Reprioritized ground coils, landing mat and two cargo placements within the existing draw budget. |
| Invisible diagonal wall 1614.18,2690.04,-145.86 | Removed the identified Apex-only forcefield triangles and their mirrored counterpart; native trace is clear. |
| Missing stairs 881.54,2884.91,131.90 and -850.84,2899.38,117.28 | Restored source stair selection; all 124 source stair placements are now included. Both reported views show stairs. |
| Invisible stairs -1264.16,4943.96,11.55 | Included by the same stair recovery. |
| Transparent objects -2624.85,3336.14,287.03 and -1564.61,3731.89,286.03 | Painted Hammond cargo containers use opaque native materials rather than a slot-number-based transparency assumption. |
| Floor fighting at spawn and 3613.08,2529.54,129.18 | Separated decals and recovered the source `_wldc` dirt overlay. Derived its layer alpha and separated it 0.24 units from asphalt. Native close-up is clean. |
| Missing window 65.51,3634.83,416.75 | Still unresolved: nearby frames found, but the reported opening needs viewing direction to distinguish wall and roof glazing. No speculative blocking pane added. |
| Crash after match end | Original logs contain native access violations without a useful call stack. Not reproduced in isolated native match-end checks; the underlying cause is not established. |

Drop-Off includes 21 source out-of-bounds volumes and four native zipline routes:
two recovered source pairs, plus east and west upper-platform access routes.
Final authored access endpoints are east (2300,5400,-190) to (2320,5900,1450),
west (-2440,5450,60) to (-2600,5800,1450). Native brush traces along both routes
are clear, and pilot hull probes find supported lower attachment positions.
The source arena exclusions cover these otherwise accessible platforms. Their
convex pieces are split to subtract only two authored access boxes: east
(2000,5100,-250) to (2850,7100,1900), west (-3000,5100,-250) to
(-1750,7100,1900). All other portions of these boundaries remain active.
These checks do not replace multiplayer traversal and combat testing.
Native use input successfully attached the player to the east rope from beside
its middle: `ZIP_MIDDLE true`, followed by upward movement along the route.
Lower anchors now extend below their supporting surfaces. Walking towards the
west rope and pressing use successfully attaches (`APPROACH_ZIP_WEST true`).
Grabbing the east rope from the lower deck remains unreliable in the harness;
complete end-to-end rides on every route remain unverified.

## Conversion details and limits

`decode_source_trigger_volumes.py` decodes entity `*coll0`, `*coll1`, ... in
numeric order. The descriptor is 56 bytes; leaf start is at descriptor offset
28. A leaf header is `<4B4f>`: vertex/face/triangle/quad counts and frame XYZ plus
scale. Positions are **signed int16**, scaled by 65535 times the leaf scale,
then translated by the leaf frame origin. Treating them as unsigned displaces
the lower half of fall volumes and can put the kill plane above the map.
This differs from the existing world-collision leaf decoder; do not merge their
coordinate rules without checking each format.

Each convex piece is intersected with the target +/-16,000 coordinate domain.
Native triggers retain their source class, damage and boundary settings, with
`*trigger_brush_B_plane_P` and local `*trigger_bounds_mins/maxs`. Source collision
blobs and source model references are removed from these native trigger entities.
All target entities live in the main lump, with an empty external partition tag.

Physics retains recovered world BVH and prop IRPS/BVH shapes. Seventy identified
source-only exclusion triangles are removed; actual visible geometry still
collides. No broad guessed bounds replace the map's collision.

Final Drop-Off render budget is 899,988 triangles and 4,123 static placements.
Stair and reported prop recovery exchanges some lesser furnishings rather than
raising the all-visible budget. Lighting is rebuilt after geometry edits.
See `composite/MISSING_CONTENT.md` and its regenerated complete placement CSV
for all exclusions; the conversion is still a preview.

Material lookup supports exported `_wldc` aliases. Actual alpha masks select
native alpha shaders and consistent TEXDATA flags; painted cargo is explicitly
opaque. Native Coliseum material dependencies remain alive through map setup.
Rejected map-regex pack loading invalidated cached materials on repeated map
setup; preloading a raw Coliseum dependency stalled startup. Neither experiment
is included in these releases.

## Test harness and evidence

The dedicated R2MapHarness profile stages both maps without changing unrelated
normal-profile mods. Its three owned package directories are replaced before
launch; previously merged staging left an old Phase Runner BSP ahead of the
current package and caused a misleading failed boundary test. A regression test
now covers switching packages with stale map files.

Automated conversion/boundary checks and harness checks are recorded in
`logs/arena-repair-tests.log` and `logs/arena-harness-tests.log`. Native screenshots,
traces and runtime counts are recorded in `output/composite/final-native-repairs.json`,
with final route and match-end evidence added separately. Isolated single-player
tests do not establish multiplayer performance, all game modes or the cause of
the user's original native crash. Intro/evac remain disabled for Drop-Off.

Player ZIPs contain only the mod runtime, a short README and an in-game capture.
Each compressed runtime member is checked against its source SHA-256. Full
development ledgers and test tooling remain in the workspace.
