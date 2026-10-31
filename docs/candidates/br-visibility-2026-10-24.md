# World's Edge visibility measurement (2026-10-24)

Question: could per-frame culling alone bring a whole battle royale map under Titanfall 2's world
submission cap of 3,145,728 indices per frame (`audit_world_draw_budget.py`)?

Tool: `measure_br_visibility.py`, with the `views` mode added to `visibility_rays.cpp`. Data:
[br-visibility-2026-10-24.json](br-visibility-2026-10-24.json).

## Scene

| | Count |
|---|---:|
| World meshes (tools materials excluded) | 57,659 |
| World triangles | 2,726,052 (8,191,926 padded indices, 260% of the cap) |
| Static prop placements | 451,863 (833 without an export: barrels, zipline arms) |
| Prop triangles at LOD0 | 405.5M |
| Prop triangles at each model's last non-empty LOD | 49.3M |

Props use their last non-empty LOD as visibility geometry, the most this machine can raycast. Their cost
is still counted from the full LOD tables.

## Method

There are 38 viewpoints. The 15 World's Edge locations in R5Reloaded's deathmatch script each get two:
eye height at the spawn centroid, and a nearby roof (the 97th percentile of up-facing surfaces within
1,200 units). Another 8 are the highest up-facing surfaces inside the locations' hull, below z 10,000 and
at least 3,000 units apart. Each viewpoint casts 6M first-hit rays over the sphere, about 0.08° apart.
Each viewpoint reports its worst frame out of 24: 12 yaws, each level and at −20° pitch, using
Titanfall's fov 90 at 16:9.

| Measure | Meaning |
|---|---|
| perfect | Every unit (world mesh or prop placement) with any visible triangle. This is a lower bound for culling at unit granularity: cells, portals and occlusion queries can't beat it. |
| frustum | Every unit in the frame, with no occlusion. |
| baked | Props at their cheapest LOD, merged into world geometry as this project does. |
| static-prop LOD | Props at the LOD their switch distance selects. VG distances are read as metres, which is an assumption. |

Rays miss sub-pixel geometry, so "perfect" is slightly low.

Viewpoints with fewer than 500 triangle hits have the eye inside geometry and are excluded: Space
Elevator ground, Refinery roof, Thermal Station roof, both Epicenter points and vantage (-3807, -7948).
Views with 1,000–8,000 hits are real interiors (TTV Building, Capitol City ground and others). They're
cheap but not worst cases.

## Results (share of the cap, worst frame)

| Viewpoint | World perfect | World frustum | World + props perfect, baked | Props, static-prop LOD | Foliage share |
|---|---:|---:|---:|---:|---:|
| Capitol City roof | 5.9% | 62% | 29% | 68% | 1% |
| Little Town ground | 2.6% | 12% | 35% | 107% | 31% |
| Little Town 2 roof | 3.4% | 232% | 26% | 59% | 8% |
| Factory ground | 5.2% | 28% | 25% | 90% | 7% |
| Train yard roof | 4.0% | 62% | 62% | 143% | 50% |
| Overlook ground | 2.2% | 68% | 28% | 73% | 17% |
| Vantage (-305, -13075) | 16.4% | 61% | 145% | 157% | 51% |
| Vantage (16873, -30584) | 18.9% | 219% | 144% | 142% | 52% |
| Vantage (-10776, -21341) | 17.4% | 147% | 116% | 131% | 37% |

All outdoor viewpoints are in the JSON.

## Findings

1. **World geometry fits with good culling.** With perfect occlusion, the worst world-only frame is 19%
   of the cap, from the highest vantage points, and ground and roof views stay under 6%. Frustum culling
   alone does not fit: it reaches 232%. Culling has to occlude, not just test the view frustum.
2. **Props are the blocker if they're baked.** From high ground, the props you can see exceed the cap
   even at their cheapest LOD and with perfect occlusion: 93–129% for props alone, 105–145% with world
   geometry. Foliage is roughly 40–70% of that.
3. **Whole maps can't use the baked-prop approach at all.** Merging 451,863 placements into world
   geometry stores 49M triangles even at their cheapest LODs, and 405M at LOD0. Natively instanced
   static props would store each model once: 1,576 models.
4. **A full port would therefore need three things:**
   - Apex props drawn through Titanfall's own static prop path. That path is separate from the
     world index cap and has real LOD switching, but converting Apex models to it is unsolved here.
   - Occlusion-quality visibility for world geometry.
   - Foliage thinning.

   Raising the engine cap alone would need roughly 1.5× for baked props from vantage points, but that
   would not fix storage (finding 3).
