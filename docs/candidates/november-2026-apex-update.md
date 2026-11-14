# November 2026 Apex update: Thunderdome 0.4.1, Skulltown 0.1.1 and ApexMaps.UI 0.3.0 — 14 November 2026

Apex build `R5pc_r5-310` (game version v3.0.1.30) has the same sixteen maps as October's install. Every pack was
rebuilt, and the maps now save as BSP **v54.1**.

## Toolchain

- **BSP v54.1.** Lump versions and record sizes match v52.1. bsp_tool loads Skulltown and Thunderdome with the v52
  layout once `apex_legends52.GAME_VERSIONS` lists `(54, 1)`, a local patch like RSX's. As before, only the light
  probes mis-size, and the ports rebuild their own.
- **RSX.** This build's models are asset version 21. The October RSX exported none of them and logged no error.
  Upstream r-ex/rsx 2.4.1 (3 November) added the version, so RSX is now upstream `a75bd4d` plus the two local patches
  (raw BSP export, `--exportformats`). Three things to know:
  - It builds only with vcpkg's MSBuild targets imported explicitly
    (`/p:ForceImportBeforeCppTargets=<vcpkg>/scripts/buildsystems/msbuild/vcpkg.targets`).
  - Material textures export only with `-matltextures`.
  - RSX reads one `--exportformats` argument, so formats go comma-separated
    (`txtr=DDS (Highest Mip),matl=Uber (Raw)`). A second argument is ignored, and the textures came out as PNG.
- **Model names.** RSX now lists models by GUID; the Cast exports still carry the names.

## Thunderdome 0.4.1

The new build differs from October's in 43 of 70 BSP files. Comparing their contents:

| | Change |
| --- | --- |
| World meshes, triangles, materials | None: 6,460 positions reordered, the same set |
| Static props | None: 12,489 placements, the same models and transforms |
| Spawns | A `gamemode_freelance` flag only |
| Lighting, probes, cubemaps | Re-baked by Respawn; the port bakes its own |
| Models | 14 of 589 changed: solar water heater (2,476 to 5,587 triangles), stasis lights (2,058 to 2,950), alien tree (+14), and material swaps on the screen tower, liquid tank, roof tanks, locker, light tower and search light |

The new extraction replaced October's, and `run_prop_pipeline.py thunderdome … --foliage` rebuilt the props. A first
run without `--foliage` dropped the grass, trees and treehouse; `release_map.py finalize` refused it. Then:

- shadow weld (2.96M to 0.66M positions);
- 3,344 sun-shadow casters;
- the seven 0.4.0 cubemap origins, captured again.

Acceptance passed on Northstar 1.31.14: 96 spawns clear and supported in PS and FFA, both team respawns, weapon fire,
postmatch to the lobby, and stock and map reload.

## Skulltown 0.1.1 (new)

`mp_rr_freedm_skulltown` is Apex's team deathmatch Skull Town. Spawns cover about 10,000 × 10,000 units: 189 spawns and
108 starts, of which the native build keeps 48 starts. The world has 1,590 meshes (138k triangles) and 24,849 props.

| Step | Result |
| --- | --- |
| Scene | Bounds: spawn hull ± 3,000 plus the cliffs. Backdrop: the overhead rail ring. 134k world triangles and 8,713 props in the world; 16,036 placements native |
| Native props | 277 models, 16,036 placements, foliage included |
| Prop collision | 9,774 solid placements at a 1,000-triangle collision LOD; 61,531 of 65,535 headers |
| Collision weld | 25.5M to 9.3M positions, 194 MB smaller |
| Shared materials | 24 world materials recovered from Apex's common packs (165k triangles), including the skull, the rib bones and the sand |
| Retired meshes | Skyline-projection wall faces, their test-colour backing and connector trims, two tool volumes and an ambient-occlusion overlay |
| Hidden geometry | 154,246 enclosure triangles outside the wall line and below the overhead ring |
| Prop shadows | 7,276 sun-shadow casters (1,023 tree nodes) |
| Cubemaps | Five |
| Acceptance | 96 spawns clear and supported in PS and FFA; postmatch to the lobby; stock and map reload |

New tools and settings:

- **`recover_shared_materials.py <port> [package]`.** Thunderdome's shared-pack material repair, for any retail port:
  - It exports the unresolved materials again from `common*.rpak` plus the map pack.
  - It resolves GUID-named materials through an asset list.
  - Layered (`_bm`) materials get their first layer.
  - It rebuilds the world RPak; the BSP is unchanged.
- **`prop_collision_triangles`.** A per-port setting for `add_native_prop_collision.py`. At the default 1,200,
  Skulltown's 28,819 world headers plus 38,310 prop headers exceed the uint16 index.
- **Hiding meshes.** Meshes are retired by collapsing their indices to one vertex. Deleting them would renumber the
  objects that the prop sun-shadow tree references, and `repair_native_render_partitions.reorder` refuses that.

Apex projects a skyline onto the walls around the arena. Titanfall draws those faces as flat grey, so they are retired.
The structure behind them, from the overhead ring down, is hidden, and the sky shows instead. One concrete enclosure
wall behind the ribs still draws.

Doors (66), breakable windows (17) and ziplines (6) are Apex script entities. They are not converted; the ziplines
become ropes.

### Base pack (0.1.0 crash)

0.1.0 crashed the game on load in a full install. Every port aliases its map pack to `mp_coliseum.rpak` and lists
its world packs as postloads of it, so loading any converted map loaded every installed port's world packs. Eight
ports at once ran out of heap during script loading. 0.1.1 aliases `mp_skulltown.rpak` to `mp_coliseum_column.rpak`
instead: a Coliseum-mode stock map whose pack provides the same base. Its packs are postloads of that pack
(`CONFIG['skulltown']['base_pak']`).

| Mounting | Result |
| --- | --- |
| Packs keyed to `mp_skulltown.rpak` | Never load: Northstar resolves the alias first |
| Map regex (`^mp_skulltown$`) | Load before the base pack and draw pink |
| Packs keyed to `mp_skulltown_patch.rpak` | Load after the base pack but still draw pink |
| Alias to `mp_lf_stacks.rpak` | Correct |
| Alias to `mp_coliseum_column.rpak` | Correct (released) |

In a test with all eight ports installed, Skulltown loaded only its two packs, and Thunderdome loaded the other seven
ports' packs but not Skulltown's. The other ports still share `mp_coliseum.rpak`, so each of them still loads all seven.
Giving each port its own small stock base pack (`mp_lf_*`, `mp_coliseum_column`) would end that, at the cost of
re-releasing each port.

## ApexMaps.UI 0.3.0

The shared atlas holds eight maps, the minimap row's limit. `build_shared_map_ui.py` changed in two ways:

- It keeps each map's existing `Postload` order. It used to rebuild that order from the file listing, which put
  `*_props.rpak` before the world RPak whose textures it references.
- It writes the receipt with portable paths.

Every map's loading pack came out of the rebuild with different bytes, even though its materials were verified
unchanged. The seven existing maps keep their released loading packs.

## Harness

The Northstar 1.31.14 launcher's Origin sign-in took about three minutes on two launches. The map had loaded by then,
but acceptance had already timed out at 240 s, so `release_map.py` now waits up to 600 s.

One crash on Skulltown, in `GiveOffhandWeapon` during the first spawn, came while camera commands were running. It did
not recur in five later loads or in acceptance.
