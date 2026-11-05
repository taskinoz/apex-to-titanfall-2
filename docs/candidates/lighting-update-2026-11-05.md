# Lighting and scenery update — 5 November 2026

What MRVN-Radiant's November research (taskinoz/MRVN-Radiant `respawn-format-research`,
`docs/respawn/RESPAWN_TF2_LUMPS.md`) showed the Apex ports were missing, and what this update changed. Upstream
MRVN-Radiant and the r2 model compiler had no newer changes.

| Map | Version | Changes |
| --- | --- | --- |
| Thermal Station | 0.2.0 | Native props and foliage, prop sun shadows, cubemaps, shadow weld |
| Thunderdome | 0.4.0 | Cells removed, prop sun shadows, cubemaps, shadow weld |
| Drop-Off | 0.11.0 | Apex's sun, cubemaps, shadow weld |
| Overflow | 0.5.0 | Cubemaps, shadow weld |
| Party Crasher | 0.7.0 | Cubemaps, shadow weld |
| Firing Range | 0.6.0 | Cubemaps, shadow weld |

All six passed `release_map.py acceptance` on Northstar 1.31.14: every spawn clear and supported in PS and FFA, both
team respawns, weapon fire, postmatch lobby, stock and map reload, and clean logs. Validation receipts are in
`docs/candidates/<mod>/port-<version>/`.

## Survey against retail

| | Apex ports | Homestead | Colony |
| --- | --- | --- | --- |
| Sun-shadow positions (0x7C) | 2.66–2.96M, three per triangle | 86k | 0.04M |
| Cubemaps (0x2A) | 0 | 4 | 7 |
| Props in the CSM tree (0x64) | 0 | 6,833 | 5,020 |

The world drawing limit is per frame: engine.dll stops world submission past 0x300000 indices (about 1.05M
triangles). Shadow meshes and static props don't count toward it, so welding shadows frees no scenery budget; more
scenery has to come from native props (`run_prop_pipeline.py`).

## Changes

- **Shadow weld (`weld_shadow_meshes.py`):** each opaque shadow mesh stores each position once. The six maps go from
  2.66–2.96M positions to 0.61–0.71M, 24–28 MB smaller each. Every mesh is decoded again and compared before
  writing.
- **Drop-Off's sun (`rebake_sun.py`):** `build_composite_map.py` used Phase Runner's sun (38.4°, 142°). Apex's
  `mp_rr_arena_composite` sun is 45.2714°, −46.919°.
  - The re-bake rebuilds the bake input from the BSP: lit-bump triangles receive light, and the opaque shadow meshes
    cast.
  - Baking with the old sun reproduced the installed sun visibility on 98.6% of 6.29M texels, within 8/255.
  - The new sun changes the sun-visibility channel, the sun world light, the shadow environment and the entity. The
    character probes' sun byte is replaced too; their coefficients come from a later bake and are kept.
  - In the comparison shots, the tower faces Apex shows sunlit are now sunlit.
  - Apex's sun intensity (89) was not applied: on the new ports' scale it would be about a quarter of the current sun.
  - Drop-Off's Apex sky is night-time and the port's is day; that is not changed.
- **Prop sun shadows (`add_csm_props.py`):** CSM tree (0x63/0x64) in light space: z = −sun,
  x = normalize(sun.y, −sun.x, 0). With that basis, 6,809 of Homestead's 6,833 referenced prop origins lie in their
  leaf boxes, against 5 with the sun negated. Grass and ground cover, and props under 48 units, are left out.
  Thunderdome has 3,344 casters and Thermal Station 456. The FPS cost was not measured.
- **Cubemaps (`build_cubemaps.py`):** five per map (seven on Thunderdome): one in each team base and three between
  them.
  - Each is six in-game views at fov 106.26 (90° vertically at 16:9), with the RUI HUD hidden
    (`rui_drawEnable 0`).
  - The views are resampled to D3D cube faces with MRVN's Source-vector mapping; a shared edge differs by 0.06,
    against 0.28 for unrelated edges.
  - texconv compresses them to BC6H. Each map gets a VTF 7.5 in a stored `XZP1 0` pakfile, a cubemap byte on every
    lit mesh, and cubemap 0 in every material sort, as Homestead stores.
  - The effect in game is subtle: shaded rock, grass and metal pick up reflected light.
- **Thermal Station native props:** `run_prop_pipeline.py thermal-station` adds the 4,628 placements its world budget
  left out (4,013 foliage), with:
  - re-baked shadows on 10,010 tiles;
  - 615 solid props colliding (30,516 triangles);
  - 607 small-prop fades.
  The world-materials stage is Thunderdome's only; it had copied Thunderdome's world RPak into the package and now
  refuses other maps.

## Visibility cells withdrawn

Thermal Station's cells build drew no ropes in other cells than the camera's. A copy whose cell BSP sends every
point to the all-visible cell drew them. The engine culls entities by cell, and with no portals only the camera's
cell is visible. A player in another cell was therefore very likely invisible.

Spawning a test entity across a cell boundary was inconclusive:
- static-prop models used as dynamic props stalled the server;
- dropped weapons ended up behind geometry.

Thunderdome 0.3.0 shipped with cells, and 0.4.0 removes them (`disable_visibility_cells.py`). The pipeline no longer
builds cells; `build_visibility_cells.py` needs portals before it is used again.

## Tooling

- `release_map.py`: release_thunderdome.py's stage, acceptance and finalize steps for any mod.
  - It counts Titan spawns in the declared total.
  - It stages scripts, resources and presentation packs from `northstar/<mod>`, because installed copies can carry
    regenerated presentation packs.
- `refresh_site_captures.py`: takes `--snapshot`, `--only` and `--package-dir`, and skips port-only galleries.
  - The site snapshot is `2026-11-05-lighting-refresh`.
  - Phase Runner keeps its 18 October captures.
