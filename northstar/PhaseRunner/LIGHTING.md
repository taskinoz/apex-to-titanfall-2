> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Phase Runner static lighting tools

## Moving-model probes: 0.1.38

The zero-length character-lighting probe and lookup lumps in 0.1.37 are
replaced with native directional ambient, sky/sun visibility and local-light
samples. Surface lighting and all world light records remain unchanged.
See CHARACTER_LIGHTING.md for encoding evidence, coverage and client checks.

## Lighting environment repair: 0.1.33

The client screenshots from 0.1.32 revealed black surfaces outside a bright
rectangle and pilot/Titan menu shadows. A concrete bake defect was found:
the decorative photographic sky dome had been included as an opaque ray blocker.
It completely occluded sampled sun and sky light near the spawn and reported
gameplay locations. The nearby dynamic cascaded shadow region could override
that incorrect baked visibility, making illumination depend on a rectangle
around the camera. The exact client cascade behavior still needs verification.

`prepare_environment_bake.py` identifies the dome by its material binding,
excluding exactly 3,968 dome triangles while retaining 869,050 actual casters.
Original face IDs, atlas pages and lightmap UVs remain unchanged. The corrected
ray bake is `lighting-environment.bin`; the first bake is preserved separately.
687,100 real surface samples regain direct sunlight, excluding the dome's own
samples from that count. All sampled real surfaces have equal or increased sun
and sky visibility. `logs/environment-ground-lighting.json` records nearby
upward-face samples at reported gameplay positions, not exact-point/client tests.
The sky artwork receives constant 0.8 linear illumination and unused RTL entries,
so it no longer receives sun or character shadows like a physical ceiling.

Native Homestead, Colony and Coliseum BSPs and entity sidecars were inspected.
The preview had no `light_environment` entities, shadow environments, menu anchors
or menu lighting volume. The corrected map follows Coliseum's indexed layout:
gameplay environment 0 and a separate menu environment 1. The menu stage is at
`(-11776, 11856, 12736)`, its camera target at `(-11776, 11600, 12776)`, with a
native inline lighting volume of +/-3072 units. That volume excludes gameplay.
The entity placement follows the installed `sh_menu_models.gnut` attachment logic.

The WORLD_LIGHTS order is now native ambient0, ambient1, sun0, sun1. Gameplay
sun/ambient intensity and sun direction are preserved; the menu pair is native
Coliseum. The light table still refers to filtered hardware sun 0, not raw world
light record 2. Two native empty static-prop CSM roots are present because this
port's props are baked into world geometry. Compiled-world casters use a separate
native shadow stream: 107 opaque meshes, 608,260 exactly welded vertices and
869,050 triangles. Their mesh-local uint16 indices and global vertex offsets
match both native maps. Gameplay owns all shadow meshes; the menu owns none.
These meshes let nearby dynamic shadow rendering use the same actual geometry
as the static bake. They add about 12.5 MB and extra shadow-pass work. Foliage
is still treated as opaque; alpha-tested shadows remain unfinished.

Rebuild with the bundled Python and workspace lighting dependencies:

1. Run `prepare_environment_bake.py` using the existing confirmed atlas cache.
2. Compile `bake_phase_lighting.cpp`, then run its normal six positional
   arguments with `environment-caster-mask.bin` as the optional seventh argument,
   writing `lighting-environment.bin` instead of overwriting the original bake.
3. Run `repair_environment_lighting.py`. It starts from 0.1.32, replacing only
   entities, environments, lightmaps and native shadow streams.
4. Run `python -m unittest test_environment_lighting -v`, then package and load
   the isolated local server before installation.

Seven focused tests cover the actual opaque-ceiling ray regression, all caster
triangle positions, native shadow indexing and environment ranges, isolated
menu anchors/volume, light-table routing and sky encoding. Every other BSP lump
is byte-identical, except relocated absolute game-lump directory offsets.
All render geometry, material bindings, PBR channels, visibility, lightmap UVs,
colliders and both walkways are unchanged. Dedicated checks cannot verify GPU
lighting, menu shadows or performance; those require a restarted client.

## First bake reference: 0.1.31

The first lighting candidate is 0.1.31. Its input is the exact playable 0.1.30
BSP, with unchanged positions, diffuse UVs, vertex colors, mesh materials and
collision. Both tunnel walkways remain unchanged. Future catwalk and Nessie
work is recorded separately in ART_TODO.md.

## Rebuild

Use the bundled Python with `tools/lighting-python` dependencies (xatlas 0.0.11,
SciPy 1.18.1, NumPy 2.5.3), and set OPENBLAS_NUM_THREADS to 1.

1. Run `prepare_lighting_scene.py`. It exports all 873,018 render triangles,
   normals, mesh membership and independent lightmap UV charts. xatlas performs
   parameterization; the original render topology remains the source of truth.
2. Compile `bake_phase_lighting.cpp` with C++17, optimization and threading. Run
   the resulting tool with `triangles.bin jobs.bin lighting.bin 4096 4096 2` in
   `output/phase-runner/light-bake`. The positional arguments are paths followed
   by atlas width, height and page count; use scene.json for another scene.
3. Run `apply_baked_lighting.py`. This writes a separate preview-baked BSP.
4. Run `python -m unittest test_static_light_bake -v`, then package and load in
   the isolated Northstar test profile before installation.

The CPU baker uses a read-only triangle BVH, one static sun ray and 24 sky rays
per covered luxel. It rasterizes and interpolates original vertex normals.
Shadow rays are two-sided, exclude their originating triangle, and start 1.25
units above the surface. Chart padding is three texels. Gutter pixels use the
nearest valid luxel rather than averaging packed light IDs or mixing directions.
The current bake covers 9,616,777 luxels. Sixteen 1024-pixel chart atlases are
tiled into each 4096-pixel native page without resampling.

## Native shader evidence

`output/phase-runner/lighting-audit/333378215666496929.asm` is a read-only
disassembly of the shipped Coliseum `uberSamp2222_wld_ps` shader. The matching
vertex shader is `17958406736974352575.asm`. The material template already
supports recovered albedo, normal, gloss and specular channels at slots 0–3.

- Normal slopes: shader samples normal RG and computes
  `RG * 2.867661 - 1.439453`, then combines tangent, bitangent and geometric
  normal. It does not use normal B as a reconstructed unit-vector Z.
- Gloss: sampled red; roughness is `max(1 - gloss, 0.04)`.
- Specular: sampled RGB. The shader evaluates roughness-dependent highlights
  and indirect cubemap reflection. No material texture or RPak is changed in
  0.1.31; this pass corrects tangent frames and lighting inputs.
- SKY A: linear RGBM decoded as
  `RGB * (alpha * 3.984375 + 0.015625)`.
- SKY B: world-space sky vector decoded as `RGB * 2.007874 - 1`.
  The writer encodes a sampled bent direction with a visibility-dependent
  magnitude. The native shader applies its own wrapped directional sky response.
- RTL A: four six-bit hardware light-table entries plus an eight-bit table page.
  Entry 63 is unused. `0x00ffffc0` selects slot zero and skips the other three.
- RTL B: four visibility channels, in the same order as RTL A's light slots.
  The first channel stores the baked sun visibility.
- The internal native RTL layout also contains a half-resolution third plane.
  That plane is zeroed; this shader does not sample it.

In the first bake, source WORLD_LIGHTS ambient and sun records remained unchanged. The table
references hardware light 0 for the single sun, after the ambient record is
handled as sky constants. Homestead/Colony native lighting data and shader
disassembly informed this mapping; client rendering must confirm that the sun
visibility is actually bound and applied. A dedicated server cannot verify GPU
lighting, highlight appearance or reflection correctness.

The writer computes orthonormal tangent frames from the original diffuse UVs,
including mirrored UV handedness. Tangents are appended to the native normal
buffer; its existing prefix remains byte-identical. Geometry fingerprints check
every triangle's winding, positions, normal indices, diffuse UVs, colors and
material, independently of the new atlas ordering. Every collision and other
non-lighting/non-draw lump is compared byte-for-byte against 0.1.30.

## Current limits

This is a first direct-sun/sky bake, not a finished light transport solution.
There is no indirect bounce, area-light/emissive bake, alpha-tested foliage
shadowing or new spatial reflection-probe set. Reflection assets still come from
the existing native fallback. Sun shadows use one ray and can have hard texel
edges; sky occlusion has 24 samples. Tiny triangles may lack an interior luxel
and receive lighting from chart dilation. Alpha/layered Apex terrain materials
remain approximations. The bake adds about 570 MB of uncompressed lightmap
payload, so client memory use and load time need checking. Resident texture
streaming behavior and STBSP are unchanged.

The native render budget remains protected: 2,625,306 padded indices out of
3,145,728, 873,018 real triangles, and 4,561 material sorts below the 8,192 limit.
All current static mesh placements and collider records are preserved.
