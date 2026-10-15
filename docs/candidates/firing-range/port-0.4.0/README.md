# Firing Range 0.4.0

Restores the hidden central VTOL landing pad: 74 source pieces including the deck, tarmac, arm towers, pipes, supports, air units, runway lights and stairs, which now have their source collision. The transparent sand overlay no longer covers the metal floors, the giant bones and a reported large rock use smoother authored LOD1, and four zipline arms are restored. Uses 97.93% of native world index capacity with no added gameplay entities. Sand blending is a lower-resolution static approximation; eight further zipline arms, foliage, weapon stations, targets, animated advertisements and AI navigation remain absent. Restart between previews.

## What changed

- **Landing pad.** 74 source placements around (1523, 2008, -700) were omitted in 0.3.0 as "invalid static triangle strips". They use direct triangle lists without a strip table, which the decoder now reads. Their deck, tarmac, pipes and supports already had source world collision. Native traces showed the eight sewer staircases had none, so their source IRPS colliders are appended.
- **Sand overlay.** `sand_desert_02_bm_transparent` rendered as an opaque sheet over metal floors. It now uses the native world-alpha shader with coverage baked from the source shader equation `1 - saturate(5*mask - 5 + 6*vertexAlpha)` into a 2048 atlas. The atlas gives about 0.7 texels per unit, so blending is softer than the source.
- **Bones and rock 1292.** Authored LOD1 replaces LOD2/LOD3. A proposed 8x base-UV scale for `rib_giant_*` was rejected: the source pixel shader applies `c_uv1RotScale` only to the detail normal, and the albedo is an unwrapped atlas.
- **Zipline arms.** Four of twelve source arms fit under the 98% index ceiling; the rest are listed in `inventory-summary.json`.

The independent audit passed 894 checks. Native tests verified 20 landing-pad surface contacts against the visible geometry, clear supported team spawns, unchanged safety triggers and ropes, postmatch return, stock Coliseum loading and Firing Range reloading. Seven matched R5R/Northstar views were captured from the exact mounted payload. Pilots vs Pilots was exercised; FFA registration and entities are unchanged from 0.3.1. No multiplayer FPS, AI or all-five-map stress certification is implied.

Baseline rollback is retained on the build drive under `firing-range/before-0.4.0/`.

Reproduce with `repair_firing_range_surfaces.py plan`, `patch`, `materials`, `append`, then `verify_firing_surfaces.py`, `stage_firing_surfaces.py`, the `firing-range-surface-repair` routes and `verify_firing_surfaces_runtime.py`. Set APEX_PORT_WORK to the owned build workspace.

## Rejected 0.4.1 sand candidate (15 October 2026)

Party Crasher 0.5.1 showed that the real Apex vertex colour is the record field bsp_tool names
`negative_one`; 0.4.0's sand coverage reads the `colour` field, which holds packed tangent data.
A 0.4.1 rebuild using the correct field (and multiplying albedo alpha) passed the binary audit (894
checks) and all native gates, and the tunnel edges matched R5R. On the reported metal-floor view,
however, it covered most of the grates with opaque sand, while R5R shows grates across two-thirds of
the floor. The source overlay sits 0.65 units above the grates, so depth does not hide it: the mask
or another coverage input is still not reproduced. 0.4.0 stays published; the 0.4.1 candidate is
staged under `surface-candidates/ApexFiringRange` on the build drive for further work.
