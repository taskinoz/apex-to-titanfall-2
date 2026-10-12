# Drop-Off 0.6.0 — source attachments and wall lighting

## Reported locations

| Report | Source diagnosis | Repair |
| --- | --- | --- |
| Lamp (-8,2273,66) | Placement 5093 was attached to shield 4924, removed in 0.2.0. Its bounds were contained in the shield assembly; no wall exists at this height. | Disable exactly 24 lamp draw and shadow triangles. It was non-solid. |
| Floating boxes (-438,132,130) | Air units, tall panels and generator sit above the omitted mounted server unit 2914. | Restore the complete source server body at its original transform, plus mirrored support 2916. |
| Invisible object (-19,1962,-59) | Source world collision outlines stacked containers 5287 and 5288, but neither visual was included. | Restore both container visuals at their original transforms; retain their existing collider. |
| Jagged wall shadows (-1917,631,192) | Native fullbright removes the marks. Sparse four-texel charts sample trim shadows at triangle vertices and spread them across large panels. | Rebake 1,302 large painted-wall triangles with 32x32 charts and 948 smaller triangles with 16x16 charts at both control entrances. |

All four recovered objects use complete source LOD3, adding 910 triangles. No
new duplicate collider is added. Every collision stream, grid, entity, world
light and character probe is byte-identical to 0.5.0. Original geometry,
albedo UVs, normals and tangent frames survive; only scoped wall lightmap UVs
and the 24 orphan lamp indices change. Room closures and source ziplines remain.

## Lightmap correction

Baseline padding used a global nearest-sample expansion, allowing adjacent
triangle charts to supply gutter samples. Correct all allocated 4x4 chart
gutters from the six valid samples inside that same chart. Original valid
samples remain byte-identical. This alone did not remove the wall artifacts.

For vertical research-station painted-metal panels within 1,200 units of
(-1917,631,600) or (1917,631,600), large triangles of area greater than 1,000
get 32x32 charts (351 raster samples each). Triangles of area 100..1,000 get
16x16 charts (105 samples each). Other materials and smaller triangles retain
their existing chart resolution. Sun, sky and local-light receivers are baked
against the complete current opaque scene. Receiver pixels lie slightly inside
the triangle rather than exactly at a shared vertex. Gutters stay within each
new chart. Existing lights, probes and other chart interiors are retained.

The new charts occupy spare space on atlas page three: large charts begin at
pixel row 1248; small charts begin at row 1920. No existing allocation overlaps
them. Native material sorts store the lightmap page per mesh, so affected
meshes are split by page and the original triangle indices are repartitioned
with native pair padding. Vertex UV changes alone are insufficient and were
rejected by the in-game verification. Reserved chart rectangles are recorded
in `output/composite/local-repair/wall-scope.npz`; future append operations
reject overlapping allocations. Total page count and texture memory stay fixed.

## Capacity and verification

4,264 source placements; 942,146 serialized triangle slots;
942,014 active triangles. The 132 disabled slots comprise 108
temporary spawn covers and 24 orphan lamp triangles. Native padded index use is
2,830,530 / 3,145,728
(89.980%).
The project 90% policy leaves about 200 triangles, depending on mesh padding.
There are 3,024 meshes and 353 static batch runs.
Further substantial recovery requires geometry savings. The STBSP catalogue
covers 231 native materials; resident texture cap stays at 1024 pixels.

35 regression tests passed. Tests protect the complete old active triangle set,
exact orphan selection, source transforms, every collision stream, lights,
probes, valid old lighting samples, isolated gutters, atlas allocation,
correct native page bindings, material dependencies and submission budgets.
Native screenshots inspect all reported locations and both control entrances.
Three collision rays contact the preserved source colliders. Postmatch returns
to the lobby; stock Coliseum and Drop-Off reload in the same game process with
no script errors. These are single-client checks, not multiplayer performance
measurements. Coarse lighting, source shader approximations and missing assets
elsewhere remain documented in the inventory.

## Reproduction and rollback

Run `repair_composite_local.py` with `plan`, `materials`, `orphan`, `append`,
`gutters`, `walls`, `wall-pages`, `walls-small`, then `wall-pages` again. These
are staged one-shot operations; restore the 0.5.0 backup before reapplying.
Regenerate STBSP, package the mod, run the five regression suites and
`verify_composite_local_runtime.py`, then finalize and make the clean player ZIP.
The binary and configuration snapshot is
`output/repair-backups/20261007-before-local-repair`. The installed 0.5.0 mod
is also retained by the install helper. Historical ZIP releases are preserved.

Player distribution contains runtime mod files, a short README and a native
screenshot. Development scripts and ledgers remain in the workspace. Phase
Runner is not rebuilt or reinstalled in this release.
