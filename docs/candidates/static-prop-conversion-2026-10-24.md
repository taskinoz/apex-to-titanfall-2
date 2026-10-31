# Apex props as native Titanfall 2 static props (2026-10-24)

Follow-up to [br-visibility-2026-10-24.md](br-visibility-2026-10-24.md). That measurement found that
baking props into world geometry blocks whole-map ports. This note asks whether Apex models could
instead use Titanfall's own static-prop path. Everything here comes from local files: nothing was
converted or tested in game.

## How Titanfall 2 draws static props (retail evidence)

| Piece | Finding | Evidence |
|---|---|---|
| Placement | BSP `GAME_LUMP` `sprp` v13: model-name table plus 64-byte placements | Colony: 738 models, 18,056 placements (bsp_tool) |
| Model | `models/....mdl`, `IDST` version 53, with vertex (`IDSV`) and physics (`VPHY`) data embedded in the one file. Retail models were compiled from DMX (`dmx/..._LOD0.dmx`) | `rock_horizontal_01.mdl` from `englishclient_mp_colony02` VPK |
| Material | Path-referenced (`models\rocks\rock_horizontal_03`) RPak `matl` assets with `_fix` (static) or `_skn` (skinned) shaders and `depth\models\..._prepass/_shadow/_vsm` variants | `homestead.raw.rpak` strings |
| Culling | Props share the cell AABB tree with world meshes. Object references (lump 0x78) are **uint16** indices into one space: meshes first, then props. Lump 0x7b stores the prop count | Colony: 4,175 meshes, highest reference 22,215, 0x7b = (3800, 4137, 4156, **18056**, …) |
| Lighting | Light probes: `STATIC_PROP_LIGHTPROBE_INDICES` (0x66), 4 bytes per placement | Colony 0x66 = 72,224 bytes = 18,056 × 4 |

Our converted maps currently write an empty `sprp` (0 models, 0 placements), and
`repair_camera_visibility.py` builds object references for meshes only.

## Hard limit: 65,535 objects per map

Because object references are uint16, world meshes plus static props can't exceed 65,535 in one BSP.

| | World meshes | Props | Objects |
|---|---:|---:|---:|
| Colony (retail) | 4,175 | 18,056 | 22,231 |
| World's Edge (`mp_rr_desertlands_mu2`) | 57,659 | 451,863 | 509,522 (7.8× the limit) |

World's Edge can't map one Apex placement to one Titanfall prop. A whole-map port would need
**clusters**: merge nearby placements, foliage especially, into per-area cluster models. That keeps
the static-prop path's own culling, LODs and draw budget. To leave room for props, world meshes would
also need merging well below 57,659, which coarsens culling. Our arena builds (2,000–5,000 meshes)
already sit far under the limit.

## Model conversion route

No tool here turns an Apex rmdl (v54) straight into a Titanfall `.mdl` (v53). The pieces of a
working chain exist:

1. **RSX** (`tools/rsx-source`) exports SMD meshes plus a QC (`ExportModelQC`, in its
   `MODEL_SMD` setting). The QC is written in Apex's v54 dialect, so v54-only commands need trimming
   for a Source SDK compiler. Legion also exports SMD.
2. **studiomdl** (Source SDK 2013 / v48–49) compiles the QC into `.mdl/.vvd/.vtx/.phy`. It is **not
   installed** here; Source SDK Base 2013 is a free Steam download.
3. **mdlshit** (`tools/mdlshit`, headassbtw) converts v49 to v53 and embeds the vertex and physics
   data. It has a command-line mode (`--noui <mdl>`). It is **not built** here; CMake plus the MinGW
   at `C:/ProgramData/mingw64` should do.
4. **Materials:** RePak builds Titanfall `fix` materials (`Material_ShaderTypeFromString` accepts the
   r2 types gen, wld, fix, skn). They'd be cloned from a native `_fix` material and shader set, the way
   `prepare_composite_materials.py` clones the world-alpha material. RePak's model asset support
   (`mdl_` v9, rmdl v54) is Apex-only, so Titanfall models ship as loose files.
5. **Delivery:** loose `mod/models/*.mdl` in the Northstar package, as maps ship `mod/maps/*.bsp`.
   **Unverified** for models.
6. **BSP:** write `sprp` v13 placements, extend the visibility build to give props object references
   and bounds, set the 0x7b prop count, and assign light probes in 0x66.

Collision: Apex model physics doesn't carry across. This project already exports per-model collision
as STL through RSX; that could go into the QC's `$collisionmodel`.

## Suggested smoke tests, in order

1. **BSP side:** add a handful of `sprp` placements that use a stock model from
   `englishclient_mp_common` to a converted arena, with object references and probe indices. Confirm in
   the harness that the props draw, cull and light.
2. **Loose model:** ship a copy of a retail v53 `.mdl` under a new name in `mod/models/` and place it.
   That confirms Northstar loads mod-shipped models.
3. **One Apex model end to end** (RSX → studiomdl → mdlshit → `fix` material → placement), then
   compare its draw cost with the baked equivalent.
4. **Clustering** for foliage and small rocks, sized against the 65,535-object limit.

## Smoke test 1 result (stock props in Thermal Station)

The test used `add_stock_props.py`. It wrote 3 `sprp` v13 placements (pallet, pelican case, sandbags) into a
copy of the Thermal Station candidate:
- each placement copies a retail record, with the origin replaced and cubemap set to `0xffff`;
- props got object references from base 2864, `align16(LEVEL_INFO[2])`, in the conservative tree. **This was
  wrong:** see the correction below;
- `LEVEL_INFO[3] = 3`, and lump 0x66 holds probe indices.

**Established:**
- engine.dll reads the authored lump. Setting the count to 60,000 raised the native error "Too many static
  props in map (map has 60000, limit is 57343)".
- `0xDFFF` (57,343) is the engine's placement limit, checked in both the v12 and v13 loaders (engine RVAs
  `0x1b1290` and `0x1b1470`).
- The loader dispatches on the `sprp` version at `0x1b84a0`. It reads the model dictionary (128-byte names
  resolved through the model loader), then three ints: count, then two counters stored separately. The
  second is an index threshold compared during the placement loop.
- **Correction (29 October 2026):** the prop object base is `align64(LEVEL_INFO[2])`, not align16. engine.dll
  `0xcb2c4`–`0xcb2e6` adds 63 and masks with `0xffffffc0`, as MRVN-Radiant found (Gravemind
  `games/respawn/mrvn-radiant/tf2-decompile-and-rebuild`). The three maps checked here agree with both rules;
  Glitch (2903 → 2944) and Live Fire Stacks (1763 → 1792) only fit align64. Thermal Station's base is 2880, so
  this test referenced the wrong objects.
- The engine names 0x66 `LUMP_STATIC_PROP_LIGHTPROBE_INDEX`.
- Bytes 52–55 of a placement are read as a colour modulation (×1/255). bsp_tool labels them CPU/GPU levels.

**Not working (with the wrong base):** the props don't draw, from any camera, including straight down. That includes a placement
using the player's own loaded model (`pilot_medium_geist_m.mdl`), so model availability isn't the cause:
some further BSP-side requirement is missing. Candidates:
- per-cell data (retail Colony has 101 cells; the conversions use one flat camera-domain tree);
- `CSM_OBJ_REFERENCES` (0x64, empty in the conversions);
- the client gather path for props.

Side findings:
- `CreatePropDynamic` of `pelican_case_large.mdl` returned but drew nothing.
- With the retail `.mdl` files shipped loose in `mod/models/`, that same call hung the server script VM.
  Loose retail model copies are not a safe delivery test.

**Next:** re-run with the corrected base, which `add_stock_props.py` now uses. If the props still don't draw,
bisect from a retail map rather than toward one. Load a retail map such as `mp_lf_deck` with its BSP
overridden from a mod, then swap in one conversion-style structure at a time: the flat tree, empty 0x64, single
cell. The first swap that makes retail props vanish names the missing requirement.

## Smoke test 1 re-run (29 October 2026): props draw

`add_stock_props.py` now uses the engine's base, `align64(LEVEL_INFO[2])` = 2880 for Thermal Station.
Nothing else changed: same three placements, same flat conservative tree, empty 0x64, one cell. All three
stock props draw in the native client, with plausible probe-lit shading, from above, from the side and from
a distance (harness session `20261029-133955`).

So the 64-alignment was the only missing requirement. A converted map can carry native static props alongside
its baked world geometry without retail-style cells or `CSM_OBJ_REFERENCES`.

Prop collision is still unverified. The harness trace only tests brush collision; it still reaches the ground
(z −81) through the pelican case.

## Smoke test 3 (29 October 2026): one Apex model end to end, and prop collision

`build_apex_static_prop.py thermal-station farmland_crate_md_80x64x72_03` converts the Apex plastic crate
(916 triangles, LOD0) without studiomdl or mdlshit:
- **Geometry.** VG LOD0 → SMD → r2studiomdl v0.5.0 (`tools/r2-model-compiler-v0.5.0`) → an 81 KB v53 `.mdl`
  with zero compiler warnings. The SMD undoes two studiomdl conventions: it writes V as 1 − v, and it pre-rotates
  by −90° yaw for `$staticprop`. VG triangles are already counter-clockwise about their normals, as SMD expects.
  Reversing them, as the first build did, drew the crate inside out. The compiled hull (±32.25, ±40.34, 0–74.66)
  matches the Apex bounds plus the compiler's 0.25 expansion.
- **Collision.** The raw render mesh was rejected ("degenerates at PHY float precision"). The convex hull of the
  render vertices (67 points, 130 triangles) compiles as one piece.
- **Materials.** `models/apex/crate_plastic_large` is built as both `fix` and `skn` RePak materials in a new
  `thermal_station_props.rpak` (Postload after `mp_coliseum.rpak`). Each clones common.rpak's
  `models\containers\can_soda` (flags, uber constants, depth materials) and keeps its shader set by GUID
  (`fix` 0x0E65A5F64BB90A55, `skn` 0x78770D4C64604199), since common.rpak is always loaded. Textures are the
  ones the world RPak already built. A material's GUID is `material/<name>_<fix|skn>.rpak`, so one name has two
  assets. RePak needs 8 blend states; retail stores 4, so 4 zeros are appended.
- **Delivery.** The model ships loose as `mod/models/apex/farmland_crate_md_80x64x72_03.mdl` and loads. That
  settles smoke test 2: the earlier hang was specific to loose *retail* copies used with `CreatePropDynamic`.

In game (harness `20261029-154104`), the crate draws closed and textured, with its blue tarp lid, beside the
stock props.

**Static-prop collision needs grid primitives.** At first neither the stock props nor the crate were solid: a
player dropped onto them fell to the floor. Retail maps reference every solid static prop from the collision
grid as a primitive of **kind 0x60**. Its index (bits 8–23) is the placement and its low byte the contents.
Homestead has 5,659, Live Fire Deck 2,052, and the conversions had none. `add_stock_props.py collision()`
appends one single-primitive geoset per placement to each 2×2 grid cell its box touches, with contents
`CONTENTS_SOLID`. `package_northstar.validate_bsp` now accepts kind 0x60 up to `LEVEL_INFO[3]`. After that,
drops land on top of each prop:

| Prop | Lands at z (floor −80.1) | Model height |
|---|---:|---:|
| Apex crate (compiled) | −5.6 | 74.4 |
| Pelican case | −48.1 | |
| Sandbags | −43.8 | |
| Pallet | −76.1 | |

So the engine traces the model's own collision once the grid points at the placement. No world brushes are
needed. A whole-map port can therefore drop the baked prop collision as well as the baked render geometry.

## Not established

- The static-prop renderer's per-frame budget and its total placement or model limits beyond the
  uint16 references.
- Whether mdlshit output is accepted for static props (versus dynamic props, which community guides
  cover).
- How large a cluster model v53 accepts (vertices per mesh, LOD count).
