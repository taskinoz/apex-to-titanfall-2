# Portal-free visibility and render optimization — 0.1.36

The 0.1.35 portal experiment is withdrawn. Although it passed CPU validation
and dedicated-server loading, the user's client culled the sky and produced
hall of mirrors. Those checks did not exercise the client renderer.

Version 0.1.36 restores the exact cell, portal and occlusion records from the
user-confirmed 0.1.34 lighting release. There are no new connected portals.
All 4,561 meshes remain referenced once in a 255-node spatial visibility tree.
The decorative sky's visibility bounds contain the complete supported camera
domain: ±12,288 units horizontally and ±4,096 vertically. Real mesh bounds are
unchanged. Ordinary visibility objects receive 384 units of local padding;
meshes intersecting either tunnel route additionally contain that route's
conservative envelope. This protects nearby geometry while keeping distant
objects spatially bounded. It is not spatial asset streaming.

Compatible native material-sort records share vertex-buffer batches: 4,561
records become 337, preserving the exact material/lightmap/cubemap binding.
Duplicate vertices are welded within each mesh, with bit-identical position,
normal, tangent, UV, color and lighting values. Each mesh retains a contiguous
vertex block, so its native CPU clipping span never increases. No triangle,
surface or detail is removed. Vertex data drops from 115,238,376 to 106,530,512
bytes, saving 8,707,864 bytes. This is a measured data reduction, not a measured
frame-rate improvement or an assertion of 337 GPU draw calls.

All 873,018 rendered triangles retain their original corner attributes and
winding. Native paired-index padding remains valid: 2,625,306 padded indices
use 83.46% of the fixed world index budget. Positions, normals, real mesh
bounds, all collision, shadow geometry, baked lightmaps, interior lights,
PBR textures and both tunnel walkways retain the 0.1.34 data.

Seven regressions check every rendered corner and binding, native ranges and
padding, restored portal records, sky camera angles, both tunnel routes,
local distant bounds and every untouched BSP lump. Fresh native collision
results are recorded separately in runtime-validation.json. Client sky,
tunnel rendering, outdoor popping and performance still require an in-game
check. Full texture mips remain resident; STBSP is unchanged.
