> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Phase Runner 0.1.43: freight supports, pipes and road markings

Restores 22 omitted source props at their authored positions: two freight cargo
holders, four wheeled freight modules, four navigation attachments, four hitches
and eight fence-wall sections. These support the two reported floating cargo
containers and the pipe/conduit assemblies in the central area. Cargo containers
are not lowered or moved. Supports use their original convex collision shapes,
adding 28 brushes; all previously active collision shapes remain active.

The two distorted pipe pieces near 817 -2326 -1280 now use their full source
meshes, replacing 58 simplified triangles with 1,120 triangles. Source positions,
rotations, scales, UVs and normals are preserved. Their existing collision is
unchanged. Other unavailable valve and connector meshes remain omitted.

All 644 road-marking triangles now use the recovered road atlas's transparency
mask and native decal depth bias. This removes opaque black areas around markings
and addresses overlapping asphalt decals. Existing ground geometry, UVs and
lightmaps are preserved. The markings no longer cast opaque live shadows.

New supports and rebuilt pipes receive a separate sun/sky lighting bake. Existing
map lightmaps, player lighting, console/truck glass, catwalks and visibility
settings are preserved. No connected portals are added. New textures are resident.
The fence's sewer-wall material uses recovered albedo, normal and gloss with a
neutral dielectric specular fallback because no labelled specular map was found.

Validation: seven scene/material/collision preservation tests and three native
renderer-capacity tests pass. The isolated native server loaded the map and
passed 4,156 collision and traversal checks. Four old pipe diagnostic starts were
raised above the newly restored fence; their end targets and physics are unchanged.
The scene has 952,348 triangles, 472 static draw batches and about 9% world-index
headroom. Dedicated-server checks do not verify client GPU appearance.

Restart Northstar and load `map mp_phase_runner`. Recheck both cargo containers,
the central pipes and the road markings at the supplied coordinates.

Full prior snapshot:
`output/installed-backups/PhaseRunner.Preview-0.1.42-before-art-supports`

Prior archive: `output/PhaseRunner.Preview-0.1.42.zip`.
