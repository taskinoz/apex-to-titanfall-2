# Native water, source fog and material recovery in 0.3.0

The three new previews retain their 0.2.0 rollback packages. Phase Runner and
Drop-Off are unchanged. Source textures and constants are converted for native
Titanfall shaders; this is not a full Apex rendering-system port.

## Firing Range water

The reference audit reads the installed `sp_crashsite` (BT-7274) and
`sp_training` (Gauntlet) assets without changing the game archives. The
Gauntlet `water_wild_02` shader supplies native world-lightmap and scrolling
water behavior. BT-7274's `water_wild_01_opaque` supplies normal, distortion,
gloss and specular maps. Its opaque render state is used for the existing
non-solid backdrop; the Gauntlet shader's original transparency is not copied.
The recovered Apex backdrop albedo remains, with neutral tint instead of the
previous strong blue ambient multiplier. Tiling is adapted for the much larger
sky-water surface. Sea height, geometry and gameplay colliders are unchanged.

BC5 normal/distortion channels remain BC5 through DirectXTex mip generation.
Decoding these as ordinary RGBA images produces a zero blue channel and changes
their native encoding. Two fixed-camera captures several seconds apart show
changing ocean surface detail. Exact Apex waves, refraction, underwater behavior
and a freshly captured reflection environment are still absent.

## Source colours and glow

`apex_material_constants.py` reads the unpatched v8/v15 source packs used here
and obtains CPU field offsets from compiled pixel-shader DXBC reflection.
The source groups albedo tint at offset 352 and emissive tint at offset 368
inside four-float fields; their first floats are unrelated blend parameters.
Reading the struct as an assumed vector layout gave incorrect colours.
Other versions require an upstream loader and a separate layout audit.

Native HDR world shaders bind original Apex albedo, normal, gloss, specular and
emissive masks. Source HDR tint values are retained. Colour and emission DDS
files explicitly use sRGB; normal/data textures stay linear. Where maps are
absent, small neutral PBR channels complete the shader's required bindings.
These contracts are checked against the generated RPak before native testing.

Generic vertex RGB interpretation is disabled in this delivery. Terrain and
multi-layer materials put blend weights in COLOR; treating these as RGB made
the Firing Range ground red. Even some `_vc` surfaces use palette/weight data:
the next candidate produced green structures absent in the matched Apex views
and was also rejected. Naming alone is insufficient. Original vertex bytes
are retained, and a per-material reviewed shader/palette mapping is required
before enabling this path. Source texture pixels and reflected tint constants
are recovered independently.
Existing two-layer Overflow lava approximations are preserved. Advertisement
atlases use native unlit rendering where appropriate; animation is still frozen.

| Map | Materials adapted | Native HDR masks | Explicit vertex-colour materials |
| --- | ---: | ---: | ---: |
| Firing Range | 74 | 5 | 0 |
| Party Crasher | 229 | 15 | 0 |
| Overflow | 143 | 12 | 0 |

One Overflow material's source shader dependency is unavailable; its tested
baseline stays in place and the omission is recorded. Alpha/cutout emission
retains its earlier frozen approximation. The native material shaders keep
their compiled bytecode; no executable or shader instruction patch is applied.

## Party Crasher recovery and fog

The recovery adds 14 source signs/screens and 283 small wall-light fixtures at
their exact source transforms and authored LODs. They occupy 29,996 triangles,
bringing the map to 90.73% of the measured world-index capacity and 339 static
draw batches. Source-owned collision is used where the source marks an object
solid. No dynamic prop entities are added.

Each preview now has a native global `env_fog_controller` based on its source
height, distance, density, direction and colour fields. The remote editor-room
origin is relocated and the controller is enabled as the master. This is an
adaptation; source volumetric scattering, local fog volumes, colour-correction
LUTs and full sky-vista rendering remain incomplete. Fog does not introduce
selective portals or alter visibility bounds.

## Evidence and failed candidates

The first material candidate crashed during RPak loading in
`materialsystem_dx11.dll + 0x507fb`. A corrected candidate with complete PBR
bindings and explicit colour formats loaded successfully. Those changes were
applied together; the precise individual cause has not been isolated. The red
terrain candidate also loaded but failed visual review and was replaced.
The green-palette candidate is retained separately as a rejected comparison
snapshot; the current snapshot excludes that shader interpretation.
The BT opaque water preset rendered the world backdrop too dark; the final
adaptation uses the Gauntlet shader's world-lightmap path instead.

Ten focused regressions cover source reflection, terrain mask scope, required
PBR bindings, native/v8 sparse stream caches and previous source-feature checks.
Each delivered payload is gated by its own binary, material-contract, native
capture and gameplay/reload receipts in `port-0.3.0`. Tests use one local client;
they do not establish multiplayer load, all hazard/zipline traversal or AI.
The older repeated shared-session mode-change crash remains unresolved; restart
between the new previews. Candidate failures are not erased by final successes.
The final Overflow shader pack also encountered a mode-switch loadout error:
`CodeCallback_GetWeaponDamageSourceId` received a null class name while giving
a pilot loadout. No native crash was reported for that run. A clean-process
retest then passed PS, FFA, postmatch and stock-map reload checks with no script
errors or native crashes. Its success is recorded separately from this failure.
The individual root cause remains unresolved.

Campaign references and rollback/build caches live on the larger owned build
drive. A temporary reference extraction filled C: and was moved there; original
game files and existing release packages were preserved.
