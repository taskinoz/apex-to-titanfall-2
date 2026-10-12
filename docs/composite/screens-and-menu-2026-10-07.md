# Drop-Off 0.5.0 — screens, banner supports and menu isolation

Recovered 43 original placements: fifteen banner frames, fifteen support arms,
seven large wall displays and six translucent closure screens. The central
wall display uses source LOD0; other large displays use LOD2 with their original
LOD0 overlay section. Frames and arms use complete source LOD2 geometry. All
objects retain source origin, angles, scale and skin. No old props were removed.

The wall report near (-86,3464,797) identifies the central display. The north
barrier near (20,5534,80) and mirrored diagonal barriers near (+/-1560,2678,0)
are intentional room closures. Their original collision is preserved; original
screen quads now render over it. Native transparency uses the source 0.2 opacity,
explicit coverage and recovered albedo. The cyan grid is a static approximation
of Apex's animated effect, not a newly invented door or an accessible room.

## Lighting and menu stage

Two hardware light slots had no existing surface references. They now use the
previously omitted source hall lights 309 (east point) and 51 (west spotlight,
approximated as a point). The native light count remains 64, including the two
ambient environments; the hardware table still uses 62 entries. Scoped rebaking
updates 186,217 RTL charts and 287 character probes.
Surface sun visibility, bent normals and unrelated lighting tiles are preserved.
One hundred source screen charts receive constant illumination, including 32
existing world display charts. This is not an animated emissive shader or GI bake.

The native menu scene reference was (-11776,11856,12736), inside the photographic
sky sphere of radius 22000. Its client-created actors and effects could therefore
appear in gameplay. The scene reference is now (-25000,24000,24000). Its camera
target, environment entity, light volume and ambient/sun origins move by the
same delta (-13224,12144,11264). Relative placement and the independent menu
environment are retained. Native captures show menu actors at the new stage and
a clear gameplay sky. No render portals or new culling rules were introduced.

## Measured capacity and verification

Adds 5,262 triangles; total serialized occupancy is 941,236,
including 108 disabled spawn-cover slots. Native padded index use is
2,827,710 / 3,145,728
(89.89%).
There are 2,973 meshes and 347 static batch runs. The scene remains
below the 90% project index policy, with only about 1,100 triangles of policy
headroom. Further recovery needs geometry savings or a separately tested model
submission path. Resident textures keep the existing 1024-pixel cap. The native
STBSP catalogue is regenerated for all 230 bound materials.

All 29 regression checks passed. They verify source transforms, old render and
collision prefixes, intended closures, menu entity changes, scoped lighting,
material dependencies and STBSP GUID coverage. Native captures cover the reported
walls, barriers, banner supports, both hallways, gameplay sky and isolated menu
actors. Three room crossing traces hit their preserved collision. Native
postmatch returns to the lobby without process exit; stock Coliseum load and
Drop-Off reload pass in the same game process, with no script errors. These
checks do not establish multiplayer frame times or reproduce every earlier crash.

## Reproduction and rollback

`repair_composite_screens.py plan`, `materials`, `append`, `menu`, `screen-pass`,
then `lighting`. The append step uses the complete 0.4.0 caster snapshot rather
than the original, shorter bake cache. Rebuild the STBSP catalogue and package
with `package_composite.py`. Run the regressions and native harness checks before
packaging. The repair scripts are one-shot operations; restore the prior snapshot
before reapplying. Native binary snapshots are in
`output/repair-backups/20261007-before-screen-repair`. The install helper retains
the replaced 0.4.0 mod for rollback. Historical release ZIPs remain available.

The complete placement ledger now includes 4,261 objects, with 2,055 local budget
omissions, 147 asset omissions and 1,884 remote/menu/backdrop exclusions. The
building signage texture remains unrecovered; there is no substitute unrelated
atlas. See `MISSING_CONTENT.md` and the CSV for every excluded placement.
