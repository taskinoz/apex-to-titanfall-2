> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Interior lighting and balanced textures: 0.1.34

The user confirmed 0.1.33 outdoor lighting looks good. This build preserves its
sun direction/intensity, sky artwork, sky-direction lightmaps, per-luxel sun
visibility, menu environments, geometry, visibility tree, collider data and both
tunnel walkways. The new light sources are local static native PBR point lights.

Twelve building fixtures use actual original Apex POINT-light positions, six per
building. Their cyan/warm colour ratios are retained with brightness calibrated
for the current preview. Eighteen new tunnel fixtures are spaced about 560 units
apart and sit 120 units above the confirmed walkways. These are traversal
adaptations rather than reconstructed original tunnel fixtures. There are no new
runtime dynamic-light entities, script light loops, or changes to movement.

The compiled WORLD_LIGHTS records follow native Homestead's POINT layout with
linear falloff to a bounded radius. Gameplay/menu suns remain hardware indices
0/1; interior points use 2–31. The native single 63-entry table supports those
indices. Each luxel keeps its original sun in RTL slot 0 and can select up to
three visible interior lights in slots 1–3. A CPU ray bake uses all actual static
caster geometry and rejects blocked light paths. 80,319 covered surface samples
receive local lights. The native shader evaluates their diffuse and specular
response with the existing normal/gloss/specular materials. A small artistic
ambient fill is added from visible fixtures; it is not indirect light transport.
Sun visibility and all unmodified ambient samples are preserved byte-for-byte.

Native static shadow geometry is regrouped from 107 draws to 27 draws per full
shadow submission. Mesh-local uint16 indices and exact global vertex offsets
remain valid; every caster triangle, position and winding is preserved. This
reduces draw overhead without changing the confirmed sun-shadow geometry.

The original material project held 703 custom DDS textures, about 886 MB, mostly
without mip chains. Exact-byte deduplication removes 136 repeated texture assets.
The remaining 567 textures have complete resident mip chains. Every albedo's
original highest-level compressed blocks is preserved exactly, as are rock and
terrain normal top levels. Other auxiliary channels have a maximum dimension of
1024; this reduces fine PBR detail on some props while retaining colour detail.
The resulting native RPak is 564,715,790 bytes, about 36% smaller than 0.1.33.
Material names, dimensions, shaders, Uber buffers and external dependencies are
retained; only custom texture bindings change to deduplicated assets. The existing
native STBSP material catalog remains valid and byte-identical. All mip levels
remain resident; starpak streaming and spatial mip coverage remain unfinished.

Mip generation uses [Microsoft DirectXTex 2026.5.8.1](https://github.com/microsoft/DirectXTex/releases/tag/may2026).
The official [texconv options](https://github.com/microsoft/DirectXTex/wiki/Texconv)
describe full mip generation and format-preserving conversion. Generated mip
chains are checked independently against DDS headers and native RPak headers.
Original top blocks are restored after conversion for every unscaled texture.

Rebuild steps in the workspace:

1. `optimize_preview_textures.py`, followed by RePak and
   `validate_world_materials.validate('output/phase-runner/balanced-materials')`.
2. `prepare_interior_lights.py`, then compile `bake_interior_lighting.cpp` and
   run it with triangles, existing atlas jobs, fixtures, output, width, height,
   pages and caster mask paths. It does not overwrite the confirmed sun bake.
3. `apply_interior_lighting.py`, then the seven `test_interior_lighting` tests.
4. Package the separate candidate and run the isolated native server before
   `finalize_interior_release.py` installs it.

Tests include a real wall/point-light ray regression, native light-table ranges,
unchanged outdoor sun/sky samples, exact caster reconstruction, complete native
mip residency, albedo/terrain-normal top-block fidelity, material/dependency
preservation and unchanged geometry/collision. Headless runtime checks establish
map loading and collision; interior brightness, PBR highlights, performance and
whether the reported popping improves still require client verification.
The popping's exact cause has not been established from still screenshots.
