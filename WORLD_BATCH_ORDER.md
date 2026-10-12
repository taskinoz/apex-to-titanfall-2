# Phase Runner native world submission — 0.1.40

The user reports that catwalks, railings and crates collide but have no visuals
at any angle in 0.1.39. All their triangles, textures and references remain in
the BSP. Increasing camera guards did not restore these draws.

Read-only inspection of the installed engine identifies a second submission
limit: engine.dll+0xb7304 compares the material-batch count with 0x800 (2,048).
The equal branch exits to +0xb74c9 before copying the next mesh. The previously
checked index limit at +0xb72af is independent and is still 0x300000 indices.
The draw list walks visible mesh bits in increasing mesh-ID order. Its batch
key contains the vertex channel, material sort and runtime dynamic-light mask.

The complete 0.1.39 draw order has 3,777 material/channel runs for just 454
unique keys. An independent submission simulation with a uniform dynamic-light
mask reaches the native cutoff at mesh 2,343. All 117 new catwalk/rail meshes
(old IDs 4,469 through 4,585) lie beyond that cutoff. Exposing more world geometry
through enlarged visibility guards can trigger this limit sooner.

Version 0.1.40 stably groups the exact existing mesh records by vertex channel
and material sort, reducing the complete static draw to 454 batches. It retains
all 881,966 triangles and all 2,652,150 paired/padded indices. Mesh bounds move
with their original records, and every visibility mesh ID is remapped to the
same physical geometry. The world model and its render partitions remain intact.
The transform rejects unsupported multi-model layouts, multiple partitions,
mixed vertex flags, translucent geometry and populated CSM mesh references.

Only MESHES, MESH_BOUNDS and OBJ_REFERENCES change. Every other payload remains
exact, including collision, character lighting, all surface lighting, vertex
positions/normals/tangents/UVs, material sorts, shadows, camera guards, sky and
portal records. Loading artwork, translations, RPaks and STBSP stay unchanged.
The original tunnel paths and prior releases remain backed up.

Six regressions check the installed engine instructions, reproduce the old
cutoff, prove all new draws fit, check 64 randomized visible subsets, verify
mesh/bound/reference ownership and all unrelated bytes, and reject unsupported
layouts. Three existing native index-budget regressions also pass; native
Homestead and Colony have 108 and 296 material/channel runs respectively.
The dedicated-server checks pass for map loading, collision, catwalk floors,
railings and both directions along each route.

The native static cutoff is removed. Runtime dynamic lights can split batches,
and actual GPU appearance still needs a client check. The final report preserves
that limitation rather than treating dedicated-server loading as a visual test.
