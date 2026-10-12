# Composite conversion, preview 0.6.0

Source: `mp_rr_arena_composite` (Apex BSP 47, static-prop game lump version 50).
Target: `mp_arena_composite` (Titanfall 2 BSP 37), Northstar mod `ArenaComposite`.
This is a separate package from Phase Runner. It is a playable conversion preview,
not a recreation of Apex's arena rules, scripting or all visual effects.

## Recovered scene

The package has 942,146 serialized triangles (108 disabled spawn-cover
slots and 24 orphan lamp slots) and 4,264 static placements. Source transforms and author LODs
are retained, with incremental screen overlays documented below. Selected world
geometry, props and the photographic sky use native BSP world meshes.

Source primary albedo, normal, gloss and specular channels are rebound to native
Titanfall world materials. Textures have resident mip chains, capped at 1024
pixels, with a native version 8.0 STBSP material catalogue. This sidecar contains
empty spatial columns; it does not implement spatial starpak mip streaming.
Recovered opacity masks and decal albedo alpha use an embedded native alpha
shader. Source vertex colours, layered shader blending, animated screens and
full reflection behaviour are not reproduced.

Lighting uses the source sun direction, occlusion rays through recovered opaque
geometry, 60 selected local source lights, four 2048-pixel native lightmap pages,
and 2,907 native character probes. Most charts have four texels per triangle; 2,250 control-entrance wall
triangles use 16x16 or 32x32 charts. Spot
lights are approximated as point lights. There is no bounced GI or newly baked
reflection cubemap. The sky is a photographic sphere projection approximation.

Collision comprises 4,412 convex brushes and 529,156
triangles in 3,468 native headers. Source IRPS/BVH
surfaces retain their transforms independently of render LOD. Added closure
screens rely on the existing permanent room clips. See the collision ledger
for selected solids without decoded colliders.

## Rebuild pipeline

Run from the conversion workspace with its existing tool dependencies. Input
archives are read-only. Keep raw sources and extraction caches outside release
packages. A clean conversion requires the local Apex and Titanfall installations
and the existing Phase Runner native-container template.

1. Extract client/server VPK map files and external BSP lumps, verify CRCs, and
   inventory entities, meshes, static placements and packed collision models.
2. Decompress the map RPak with `decompress_rpak.py`. `stage_rpak_streams.py`
   stages only referenced starpak extents in owned sparse files, retaining original
   offsets and tail directories. Never truncate a source starpak.
3. Export with the isolated Legion instance. `composite_asset_audit.py` matches
   source model paths to recovered RMDL/VG/PHY files.
4. `prepare_composite_scene.py` imports the world OBJ and decoded VG author LODs.
   Resolve OBJ negative indices against each array's length **at the face**, not
   against the completed file. Keep material and collision ownership per placement.
5. `prepare_composite_materials.py` stages resident channels and builds the native
   material RPak. Validate every texture, shader and pass dependency against the
   package plus native common and Coliseum paks before launching.
   Alpha materials must bind only recovered channels; inheriting the native
   glass template's texture table stalled startup even though GUID availability
   checks passed. A dedicated regression and client cold launch cover this case.
6. `build_composite_map.py` writes native draw, collision and all-visible cell
   structures. `light_composite.py` ray-bakes surface lighting, local illumination,
   native light tables and character probes. `finish_composite_spawns.py` reapplies
   verified human/Titan markers without repeating the bake.
7. `present_composite.py` builds source loading artwork and native presentation
   assets. `package_composite.py` stages the independent Northstar package.
8. Run `test_composite_port.py`, the harness unit checks and actual game captures.
   Verify source-aligned floor traces, pilot/Titan hull clearance, both teams,
   horizontal/up/down views, interior views, material alpha and stock-map reload.
   Capture metadata must identify the active map; a match may finish and return
   to the lobby while later trace commands still succeed there.

## Binary and engine constraints

The native container is not made by changing a BSP version number. Rebuild draw
and collision records, material GUIDs, native light/probe formats and cell tables.
GAME_LUMP payload addresses are absolute file offsets: let the compactor relocate
unchanged game lumps; copying an old raw directory leaves invalid pointers.

Source world collision positions decode using model firstVertex and packed vertex
offset/scale. Inline models need their own model range and entity transform. Do
not apply the Phase Runner translation to this map. Prop Euler angles are mapped
to native pitch/yaw/roll as source stored components y/z/x. Visual and collision
transforms must be identical.

The installed engine's audited world submission capacity is 3,145,728 padded
indices, not an unlimited triangle count. This scene uses 2,703,882 (86%). It has
2,836 mesh records and 322 base draw keys, below the audited 2,048 batch limit;
local light masks can split draw keys at runtime. Native material-sort capacity
is 8,192. Local vertex/mesh references are unsigned 16-bit; collision primitive
references are also 16-bit. Packed collision centers/extents must fit signed
16-bit values. Brush cut/bevel counts and cell child counts are unsigned bytes.
See `engine-limits.json` for evidence and binary fingerprints. Safety margins and
encoding choices are distinguished there from proven hard limits.

All-visible camera cells avoid the known Apex-to-Titanfall angular culling
incompatibility. This consumes more render budget than a correct selective PVS.
It is not a frame-rate benchmark or a universal limit for every Titanfall build.
Future selective cells must retain sky coverage and interior geometry when the
camera is inside it; replay angle and position sweeps before shipping.

## Gameplay scope

There are 24 team human starts, 24 neutral human respawns, six team Titan starts
and six neutral Titan respawns. IMC uses the west side and Militia the east side.
All human start positions were checked with floor and pilot-hull probes; Titan
areas were checked with a 200x200x400 hull. Intro and epilogue are disabled.
The preview targets Skirmish, Pilots vs Pilots and Free For All. Presence of spawn
flags alone is not proof of every mode's runtime behaviour; consult validation.

CTF, Hardpoint, Attrition AI, Frontier Defense, Fastball and scripted Apex systems
need separate entities, objectives and/or navigation work. Dropship intro and
evac are not provided. Door, mover, zipline, train and FX/audio logic is not
transplanted. Native map labels are supplied for thirteen language files; the
description remains English. The user-facing map name is Composite.

## Evidence and future automation

The shipped inventory records every local static placement and exclusion reason,
missing source collision owners and missing material aliases. `validation.json`
records actual client checks separately from binary checks. A future converter
should retain this separation and fail on missing shader dependencies, out-of-range
native indices, invalid absolute game-lump pointers, decode failures or incomplete
collision ownership. It should not silently invent colliders or label an untested
package as verified.

Reusable low-level layouts and conversion methodology are documented in the
workspace's `docs/conversion/` guide, `binary-layouts.json` and
`respawn_conversion_layouts.h`. Their Phase Runner-specific offsets, entity
repairs and budgets are not universal settings for another Apex map.

## Source-layout correction in 0.3.0

See `../dropoff-source-layout-2026-10-07.md`. Conditional arena start covers
are excluded from permanent rendering. Source zipline GUID pairs provide the
endpoints; intentional toolclip room closures are retained.

## Incremental source-detail recovery in 0.4.0

`recover_composite_details.py` appends stable draw/collision streams, source
material bindings and new lighting charts in unused texels. See
`detail-recovery-2026-10-07.md` for relocation rules and budget policy.

## Screens, targeted RTL and native menu isolation in 0.5.0

`repair_composite_screens.py` restores source screen assemblies, relocates all
menu anchors and lighting together outside the sky sphere, and reassigns two
unused local light slots to hallways. Native mesh UVs reconstruct raster jobs
for targeted RTL rebaking; old charts outside the scope and unrelated probes
remain unchanged. See `screens-and-menu-2026-10-07.md` for details.

## Local source attachments and chart allocation in 0.6.0

`repair_composite_local.py` restores four source objects, suppresses one orphan
lamp and repairs chart gutters. Native fullbright distinguishes material faults
from lighting faults; sparse vertex-edge ray samples explain the triangular
wall artifacts. High-resolution receivers use spare atlas rectangles, with
inset raster samples and gutters confined to their own charts. Split native
mesh/material-sort groups by atlas page; changing vertex UVs alone binds the
wrong page. Repartition indices with native odd-triangle pair padding, rebuild
conservative visibility/bounds and audit both index and batch limits.

Check atlas rectangle reservations before appending receivers. Collider source
ownership can reside in world BVH rather than the omitted static-prop table;
compare actual triangle bounds and native rays before adding duplicate hulls.
See `local-repairs-2026-10-07.md` for exact scope and retained evidence.
