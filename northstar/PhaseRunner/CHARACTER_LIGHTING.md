> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Moving-model lighting — 0.1.38

The 0.1.37 map had zero light probes, probe references, parent ranges and
lookup-tree records. Its surface lightmaps work, but moving pilots, Titans,
hands and weapons consequently have no authored spatial lighting samples.

This release adds 39,819 gameplay samples and two native samples for the
isolated menu stage. The ground-level grid is 256 units horizontally, with
closer samples along both complete catwalk routes and around the 30 existing
building/tunnel fixtures. A coarser grid covers upper and ejection space.
Total additional lighting data is about 2.84 MB uncompressed.

Samples are ray-baked against all 877,998 current world shadow triangles.
The photographic sky is already excluded from that stream. Each sample
stores first-order directional RGB ambient coefficients, a bent sky vector,
sun visibility and up to four visible local-light links. 17,923 gameplay
samples receive direct sun and 3,532 have local-light links. The ambient fill
matches the small artistic fill used in the surface bake; it is not bounced GI.

The installed native engine supplies the encoding evidence:

- `engine.dll+0xcd050` decodes the first 32 bytes as signed 16-bit values
  scaled by 1/8192. The first 24 bytes contain three XYZ/W ambient sets.
  They are not six RGB888 ambient-cube faces, as an older BSP parser suggests.
- `engine.dll+0xc8fc0` loads 48-byte samples and adds 32 to active local-light
  indices, reserving the dynamic-light portion of its hardware table.
- `engine.dll+0xc7a90` uses the native KD lookup when the optional probe BSP
  accelerator is absent. That supported path is retained here; no invented
  probe BSP records or visibility portals are introduced.
- Shipped Homestead/Colony links independently confirm the filtered hardware
  light index convention. Around 96% of tested links resolve within their
  fixture radius with filtering, versus 15–18% with raw world-light indices.

Native KD-tree child/leaf packing is checked against Homestead. Independent
queries match a spatial nearest-neighbor implementation at 707 positions;
the maximum pending tree stack is 14 and at most 93 references are tested.
All samples and parent ranges are valid. A synthetic enclosed-room bake
verifies blocked sun/sky, an interior fixture and occlusion through its wall.

Only BSP lumps 4, 101, 103 and 104 change. Every other payload is exact,
apart from relocated absolute game-lump directory addresses. Geometry,
collision, catwalks, visibility, sun/point-light records, all surface
lightmaps, shadow geometry, materials, loading artwork, translations and
STBSP content remain unchanged. Seven regressions and the existing native
collision/traversal checks pass, and the map loads without script errors.

Dedicated-server checks do not render player/weapon lighting. Restart the
client and check hands, weapons and other models outdoors, in a building,
and inside both pipe tunnels. Reflection cubemaps remain the existing native
fallback; probe spacing and transitions may need adjustment after that check.
The complete 0.1.37 mod and its archive are retained for rollback.
