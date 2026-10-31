# Thunderdome visibility cells — 30 October 2026

The conversions draw every world mesh and static prop from one all-visible camera cell. `build_visibility_cells.py`
replaces it with a kd split of the arena into cells whose access trees hold only what can be seen from them, plus
one all-visible cell. There are no portals; the single-cell builds already use that format.

## Method

- **Scene:** 3,175 world meshes and 6,757 static props, 6.14M triangles in total. Props use the first LOD with at most
  1,500 triangles. See-through surfaces never block a ray but are recorded as seen: overlays, cutouts, glass and
  foliage props.
- **Viewpoints:** a reachability flood from 626 spawn points over world and solid-prop floors, sampled every 128 units
  at +64/+250/+450. That gives 352,266 viewpoints; 96,582 of them are inside the play bounds.
- **Rays:** `visibility_rays.exe tiles` casts 6,000 rays per viewpoint, about 35 minutes. Results are recorded per
  512-unit column, and an unchanged scene reuses `seen.bin`.
- **Cell sets:** each cell draws:
  - everything seen from its tiles and the ring of tiles around them;
  - every object within 512 units;
  - transparent meshes.
- **Cameras that see everything:** anything outside the play bounds, and anything above a cell's highest viewpoint
  plus 512, falls in the all-visible cell. That covers the stadium ring, spectator and intro cameras.
- **Budget:** the greedy split goes as far as the uint16 reference index allows, ending at 64,748 references.

## Result

| | Objects drawn |
| --- | ---: |
| Before (any camera) | 9,932 |
| Arena cells (11) | 1,341 to 8,186, about 64% on average inside the bounds |
| All-visible cell | 9,932 |

The central cells are the largest, at 7,931 and 8,186. A finer split needs more references than the 16-bit index
space holds, unless cells share reference ranges, which retail maps never do and is untested.

## Verification

- 72 shots: two spawn positions per cell with a spawn point, four directions each. Baseline and cells builds give the
  same world; the largest difference is 0.9% of pixels, all of it the HUD ability meter.
  Route: `test-harness/routes/thunderdome-visibility-cells.json`.
- Same camera on both builds, hovering below cell 6's height limit at (−1500, 5600, 1340): the cells build omits
  structures no player position in that cell sees. So the engine does cull by cell, and the cell BSP orientation is
  as assumed (child 0 is the front side).
- The harness is frame-capped, so there is no fps measurement. Not checked: whether a dedicated server's entity
  networking depends on cell connectivity, since the harness has a single player.

## Follow-up: small-prop fades and the stadium screens

- **Fades (`fade_small_props.py`):** the placement field at offset 36 is a fade distance in units. Setting 600 on
  every prop hid everything beyond 600 in game. Non-foliage props with a radius of at most 80 now fade at
  100 × radius, with a 1,500 minimum: 1,748 props, median 4,451. In the reported view across the middle, the
  result differs from the cells build in 0.03% of pixels.
- **Stadium screens:** `td2_crowd_stadium_ad_screens_01`'s ring bands use `td2_rui_screen_bg_rgdc`. That is an RUI
  screen background: black albedo, an LED dot-grid illumination map and scanlines. Apex draws the picture at run
  time, and Titanfall 2 cannot.
  - The material was left neutral grey. Its GUID `0x034717147C928E10` has a leading zero, and `rsx_index` keyed
    GUIDs zero-padded to 16 digits, while the Cast name drops the zero. The keys are now unpadded.
  - The large screens between the stadium posts (`td2_apex_screen_rui`, about 10,000 × 5,000) are not in the BSP
    and appear to be placed by Apex script. No placement data was found locally, so they are not placed.
