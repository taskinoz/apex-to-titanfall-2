# November 2026 Apex update: Thunderdome 0.4.2, Skulltown 0.1.2, standalone level packs for every port and ApexMaps.UI 0.3.0 — 14 November 2026

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

## Standalone level packs (all eight ports)

Skulltown 0.1.0 crashed the game on load in a full install. Every port aliased its map pack to `mp_coliseum.rpak`
and listed its own packs as Postloads of it. Northstar's Postloads are global, so loading any converted map loaded
every installed port's packs (about 5 GB with eight ports), and the game ran out of heap while loading scripts.

What the ports took from Coliseum is small. Every port's world pack references 1,334-odd Coliseum asset ids, all of
them one world shader set (`uberSamp2222_wld`) and three depth-pass materials (`code_private/depth_{shadow,prepass,vsm}`,
on `uberDepth_wld` and `uberDepthVsm_wld`). Props and other packs use only `common.rpak`. `standalone_map_pak.py`
rebuilds those assets with RePak at Coliseum's original asset paths (`docs/conversion/coliseum-asset-names.json`), so
their ids are unchanged: 1.4 MB, shader code and constants copied unchanged.

Tested in the harness on 14 November:

| Mounting | Result |
| --- | --- |
| Postloads keyed to the map's own `mp_<map>.rpak` shipped in the mod | Never fire: Northstar loads it by its mod path |
| Map regex (`^mp_<map>$`), with or without the Coliseum copies loaded first | Pink: the packs reload around the level change |
| Postloads keyed to `mp_<map>_patch.rpak` | Pink |
| Alias to another stock level pack (`mp_coliseum_column`, `mp_lf_stacks`) | Correct, but shared with that stock map (Skulltown 0.1.1) |
| **One `mp_<map>.rpak` in the mod holding every map asset, no alias** | **Correct; nothing else loads** |

`merge_map_paks.py` builds that pack for a port: it finds the RePak project of each released runtime pack by the
sha256 of its build output (projects moved to project-storage are followed), merges them with the Coliseum copies, and
requires the result to hold exactly the released packs' asset ids, types and header sizes plus the copies. All eight
ports matched:

| Port | Packs merged | Level pack | Assets |
| --- | ---: | ---: | ---: |
| Phase Runner | 9 | 889 MB | 1,500 |
| Drop-Off | 4 | 640 MB | 1,546 |
| Firing Range | 1 | 368 MB | 727 |
| Party Crasher | 1 | 967 MB | 1,900 |
| Overflow | 1 | 628 MB | 1,221 |
| Thermal Station | 2 | 661 MB | 1,549 |
| Thunderdome | 2 | 1,047 MB | 3,487 |
| Skulltown | 2 | 756 MB | 2,693 |

With all eight installed, loading Skulltown, Thunderdome, Phase Runner and Drop-Off in turn loaded one pack each, the
map's own, and Coliseum not at all.

Released standalone (each passed acceptance on Northstar 1.31.14): Drop-Off 0.11.1, Firing Range 0.6.1, Party Crasher
0.7.1, Overflow 0.5.1, Thermal Station 0.2.1, Thunderdome 0.4.2 and Skulltown 0.1.2. **Phase Runner stays at 1.7.2**:
its standalone pack loaded and respawned three times on 1.31.15, but crashed at the first spawn on 1.31.14 in three of
four launches (`GivePilotLoadout`, server.dll), while 1.7.2 passed the same acceptance. Bisecting showed the world pack
alone, and world plus art supports and banner displays, load cleanly; the crash came with the blend and detail packs,
and the bisection stopped when the EA app's sign-in stopped completing. Phase Runner 1.7.2 still mounts on Coliseum,
but nothing else does now, so it loads only its own packs and none of the other ports load with it. `rpak.json` keeps only the loading-screen alias and the loading pack's Postload;
`map_pack_lifetime.audit` checks that layout. New ports run `merge_map_paks.py` as the last step before release
(`base_pak` remains for testing packages before the merge).

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
