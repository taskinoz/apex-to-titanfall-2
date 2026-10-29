# Thunderdome 0.2.0 user report (29 October 2026)

There are seven reported positions. They are `cl_showpos` foot positions, so the harness eyes sit 60 units higher.
Route: `test-harness/routes/thunderdome-user-report.json`, four yaws plus a downward view at each. Captures:
`test-harness/output/20261029-155142`. The cause of each report comes from `scene.json` and `scene.npz` in the
Thunderdome work folder: a ray straight down for the drawn surface underfoot, and omitted placements within 500
units.

| # | Position | Report | Cause |
|---|---|---|---|
| 1 | −4196, −2951, 560 | No more map after this | Nothing is drawn underfoot; the ray reaches the sky. The ground here is omitted rock clusters (`desert_rock_cluster_small_01/03/04`, `rock_tropics_rough_03`) and `td2_imc_portable_wall_*_xtall`. Their collision remains, so the player stands on invisible ground at a cut edge. |
| 2 | −4368, −1624, 798 | Ground texture blurry | `sand_desert_02_dirt_desert_05_bm_wld` and `homestead_dirt_01_to_dirt_desert_05_eld` stretch one texture repeat over 8,730 and 6,600 units. |
| 3 | −4017, −982, 796 | Ground flat green | `td2_manicured_grass_green_01_to_homestead_dirt_01` has world-unit UVs (one repeat per unit, ±5,000), so only the smallest mip is sampled. Its grass cover (`divided_grass_short_01/02`, `flowers_ground_01`) is also omitted. |
| 4 | −5605, −849, 848 | Building interior missing | Omitted `spectre_shack_refactor_01` ×2, lockers, `td2_spawn_zone_door_01`, lamps and sewer grates. |
| 5 | −5436, −318, 1101 | Missing texture | The player stands 253 units above the nearest drawn floor, on omitted `underbelly_cage_framework_512_256_a` (8 nearby). |
| 6 | −3558, −452, 971 | Invisible geometry | The player stands 144 units above the drawn ground, on omitted props: the military truck, `power_cell_64` and flexscreens. |
| 7 | 1677, −2249, 1162 | Hole in the map | Nothing is drawn underfoot. The ground here is omitted rocks (`desert_rock_cluster_small_03/04`, `rock_tropics_rough_03/05`) and `tree_kapok_ground_roots_03`. |

## Omitted placements (reports 1, 4, 5, 6, 7 and the grass cover in 3)

The 920,000-triangle world budget left out 6,608 of 12,200 local placements. They cover 259 unique models, and
2,745 of the placements are foliage. Solid modes: 5,697 vphysics (6), 393 (7), 58 BSP (1), 460 not solid (0).
Their collision is still in the world collision, so they act as invisible floors, walls and holes.

The static-prop path is now proven end to end in Thermal Station (`static-prop-conversion-2026-10-24.md`, smoke
test 3): compiled Apex models draw outside the world index cap, and become solid with kind 0x60 grid primitives.
The omitted placements fit its limits: 3,175 meshes + 6,608 props is under the 65,535 objects, and under the
57,343 placements. These props already have world collision, so they need render-only placements, not 0x60
primitives.

## Ground UV fix (reports 2 and 3)

Current Apex terrain shaders scale UVs with a constant that the stripped shaders don't expose. `rescale_world_uvs.py`
measures each world material's median UV density in the BSP. It rescales a terrain material (name containing
dirt, mud, sand, grass or rubble) to 256 units per repeat when that material has under 8 or over 2,048 units per
repeat. Lightmap UVs, blend alpha and lighting are unchanged. Atlases, trims, vehicles and the sky (2,000–88,000
units per repeat) are excluded by name.

The nine materials changed are listed in `uv-rescale.json` in the candidate
`new-arena-ports/candidates/ArenaThunderdome-uv`. In game (`test-harness/output/20261029-160955`), grass shows
blade detail instead of flat green, and dirt is sharp instead of smeared.

The ground fix is installed as Thunderdome 0.2.0. The previous folder is in
`R2Northstar/mod-backups/2026-10-29/ArenaThunderdome-0.2.0`.

## Omitted props as native static props (first pass, no foliage)

`build_native_props.py thunderdome <package>` writes `<package>-props`. Candidate:
`new-arena-ports/candidates/ArenaThunderdome-uv-props`, receipt `native-props.json`.

- **Selection.** 3,863 budget-omitted placements, excluding foliage, covering 275 (model, skin) combinations.
  274 compile; the god-ray model has no drawable sections. Each model gets every Apex LOD as `$lod`. LOD1
  switches at 12× the model radius (at least 384 units), and each further LOD doubles that distance. There is
  no physics, since the world already collides. The models total 112 MB.
- **Materials.** 261 Apex materials as `fix` + `skn` clones in `thunderdome_props.rpak` (181 MB, textures
  ≤ 512):
  - 66 reuse the 0.2.0 world textures, copied into the pak;
  - 151 are converted from the Legion exports, including `<name>_avt` variants;
  - 36 come from RSX exports. Cast names unexported materials by the top 13 hex digits of the material GUID,
    which is the pak GUID of `material/<json name>_<shader>.rpak`. For example, `0x40AEDBA289B54` is
    `models/rocks/desert_rock_cluster_small_rgdp`. Materials that no export has are looked up in the repair's
    `all-assets.csv` and exported from the retail paks (26 this run);
  - 8 remain neutral grey.
- **BSP.** 3,862 `sprp` placements (solid 0), object references from 3,200, and the nearest light probe per
  placement (lump 0x68 positions).

**Pitfalls:**
- A `Postload` entry keyed to another mod pak (`thunderdome_world.rpak`) never loads. Every prop then draws
  with the missing-material checker. Key it to the game pak the world pak follows (`mp_coliseum.rpak`).
- Materials that reference world-pak textures by GUID made the map load spin after the main menu, with the map
  never starting. A self-contained pak loads.

In game (`test-harness/output/20261029-171827`):
- **Report 1:** the cut edge is enclosed by the walls and rocks that bound it in Apex.
- **Report 7:** the hole is closed by ground, rubble and textured rocks.
- **Report 4:** the building has its walls, lockers and interior.
- **Report 5:** the cage floor draws.
- **Report 6:** the truck you were standing on draws, along with crates and rocks.

No script errors or native crashes. The harness frame rate reads 17–19 with or without the props, so it's
capped and says nothing about cost. Performance needs a normal client.

## Foliage and cutouts (second pass, installed)

`build_native_props.py thunderdome <package> --foliage` now covers all 6,607 drawable omitted placements (291
models, 277 materials). Alpha testing is decided per material, not by model name: an albedo is a cutout when more
than 2% of its texels have alpha below 128. 39 materials qualify, including grass, flowers, branches and the metal
grates the first pass drew opaque. Model names alone would also have caught the treehouse building.

Cutout materials clone Homestead's `models\foliage\grass_golden_long_01` `fix`:
- glue `0x560000B0`, rasterizer `0x2` (two-sided);
- shader set `0x512DC906D88B4D1C`, resident in common.rpak;
- per-material shadow, prepass and VSM depth materials, cloned from its `depth\models\foliage\...` materials.
  Their shader sets are resident too, and they sample the albedo's alpha. RePak builds them from JSON paths.

Reusing the opaque `code_private` depth materials would have made each grass card solid in the depth prepass.

**Light probes.** Probes on the baked grid that are inside geometry keep a flat default record (the first eight
int16 values are 0, 0, 0, 180, 0, 0, 0, 213). Props assigned one drew black, for example grass on the dirt at report 7.
`nearest_probes` now picks the nearest lit probe.

In game (`test-harness/output/20261029-180108`), the turf is covered by cut-out grass clumps; flowers, desert
grass and trees draw. Some props near the newly drawn rocks are still dark. The likely cause is real-time sun
shadows from those rocks, while the world lightmaps were baked without them.

Installed (29 October) with the ground fix, as Thunderdome 0.2.0 (1.8 GB). Backups are in
`R2Northstar/mod-backups/2026-10-29/`: `ArenaThunderdome-0.2.0` (original), `-ground-fix` and
`-props-no-foliage`.

## Foliage fade and re-baked lighting (third pass, installed)

**Fade.** Retail foliage fades at two levels:
- the model header's `fadeDistance`: 1,035 for small ground plants (radius 34–80), about 2,300–4,100 for larger
  plants and bushes, 5,520 for a birch (73 Homestead and Colony foliage models surveyed);
- the placement's fade distance at record bytes 36–40, which bsp_tool labels `forced_fade_scale`, with −1 meaning
  the model's. Homestead grass uses 1,200–2,800 and bushes 3,000–4,000.

Retail grass placements also carry flag `0x10`, Source's no-shadow flag, which non-foliage props almost never have.
`build_native_props.py` now writes both fade values by radius: under 150 → 1,500, under 600 → 3,500, else 6,000,
with the placement value scaled by the prop's scale. Small foliage gets `0x10`. 16 foliage models are faded
(11 / 4 / 1).

**Re-bake.** `rebake_native_prop_shadows.py thunderdome <package>` re-runs the port's sun, local-light and
character-probe bakes with the non-foliage props as casters: 3.6M triangles at the first LOD of ≤ 1,500
triangles. They're appended as caster-only triangles: jobs with zero UVs, which both rasterisers skip.
- **Lightmaps.** The current lightmaps carry post-bake edits (two glow passes, the atmosphere step). So they
  aren't rebuilt: only the 4×4 tiles whose sun, sky or local-light visibility changed against the original
  `sun.bin` and `local.bin` are updated. That updates sun and local visibility in 0x69, and the ambient change
  (decoded RGBM plus the bake formula's difference) and bent normal in 0x62. 501,836 tiles changed. 1,536,671
  texels lost sun and none gained it, which is the expected signature when only occluders are added.
- **Probes.** The old probe bake reproduces the installed 0x65 exactly, so 0x65 is replaced. 1,158 of 1,835
  probes are now sunlit, and the props' 0x66 lit probes are re-picked.

In game (`test-harness/output/20261029-202509`), the ground under the newly drawn rocks and trees is shadowed to
match the props, with no artifacts. No script errors or native crashes.

Installed. The previous files are a partial backup in
`R2Northstar/mod-backups/2026-10-29/ArenaThunderdome-0.2.0-foliage-no-fade` (copy them over the mod to
restore).

## Second user report: collision, grey plant, z-fighting (installed 29 October)

- **Collision.** None of the omitted placements own collision in `physics.json`. A kind 0x60 primitive plus
  the per-triangle tree does not collide either: a player dropped on a native rock fell to z −608 with or without
  it. The engine traces a static prop's physics (map-collision block), and Apex's collision for these models is
  concave triangle soup. `add_native_prop_collision.py` appends the solid props' drawn geometry (first LOD ≤ 1,200
  triangles, radius ≥ 24) as world triangle collision, as `append_collision` does: 2.64M triangles, 27,506
  headers (58,106 of 65,535). Native traces land on the drawn tops (rock 1,921 → 1,923, wall 1,076 → 1,076).
- **Grey plant.** `tree_acacia_small_01`: Cast drops material variant suffixes (`tree_acacia_small_01_wind_avt`).
  The builder now takes the shortest `<name>_…` variant, leaving 6 grey materials.
- **Z-fighting.** Overlay layers (`*transparent`, `*blend2trans`, `*decal`) are coplanar copies that Apex fades
  by vertex alpha.
  - Native props drop fully transparent overlay triangles and lift the rest 0.4 units along their normals.
  - Baked-world overlays have lost their vertex alpha (stored as 255). `separate_world_overlays.py` lifts their
    vertices 0.4 units on new positions: 12 materials, 37,317 vertices. They now draw opaque with hard edges
    instead of flickering.
- **Pale ground** (shots 4, 5, 9) is already in the original 0.2.0, on `sand_desert_02_dirt_desert_05` and
  `canyonlands_crater_mud…` patches. Its lightmap, normals and textures look normal; cause not found.

Pipeline order: `build_native_props.py --foliage` → `rebake_native_prop_shadows.py` →
`add_native_prop_collision.py` → `separate_world_overlays.py`. Previous files are in the partial backup
`R2Northstar/mod-backups/2026-10-29/ArenaThunderdome-0.2.0-fade-rebake`.

## Third user report: zipline arms, grey paths, decals (30 October)

Compared against the original 0.2.0 at the reported views (`test-harness/output/20261029-234453` vs `-234723`):
- **Grey paths** were `road_tracks_dry_03_blend_2_trans` and `sand_desert_02_bm_transparent`. The 0.2.0 repair
  deferred them, leaving `composite_fallback_albedo` (bluish grey). That was the "pale ground" too. Lifting
  overlays made them fully visible. Overlay meshes aren't exactly coplanar with the ground (the road dips about
  0.7 units below the sand in places), so a lift alone can't fix them. `patch_world_materials.py` exports their
  textures (RSX) and rebuilds the world RPak from the 0.2.0 manifest.
- **Zipline arms** were among 150 placements omitted as "Compiled source model not recovered": `zipline_arm`,
  `barrel`, `gun_rack_arm_down`, `rock_desert_04`, `pipe_modular_grey_bracket_cap`, `loot_candy_debris_pink`. The
  first export only read the map pak. `build_native_props.export_models` exports them from the common paks, and
  the selection now includes them.
- **Black outlines that fade:** `td2_skull_metal_01_decals` (`td2_metal_sheet_seam_01`), a separate decal model
  coplanar with `td2_skull_metal_01`. Models named `*decal*` are now all overlay.
- **SYPHON text** (already in 0.2.0): world `font_logik_black_01_vc` coplanar with its panel. The overlay
  pattern now includes `font_`, `seam` and `stencil`.
- **Red/yellow/green track** (already in 0.2.0): `stamped_metal_large_clean_painted_01_vc`, Codex's "native
  vertex paint" for `_vc` materials. Left as is.
- **Bridge blend:** `td2_center_platforms_01` uses a two-layer grass/dirt blend. The static-prop `fix` shader draws
  layer 0 only. Not fixed.

Pipeline order: `build_native_props.py --foliage` → `rebake_native_prop_shadows.py` →
`add_native_prop_collision.py` → `separate_world_overlays.py` → `patch_world_materials.py`.

**Open:**
- Performance on a normal client.
- LOD switch distances (12× radius, doubling) are untuned.
- Two-layer blend materials on native props.
- 10 unresolved (grey) materials.
- Foliage doesn't cast lightmap shadows (retail grass doesn't either), and cutout grates cast as solid in the
  re-bake.
