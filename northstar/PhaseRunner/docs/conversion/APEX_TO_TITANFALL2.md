# Apex map conversion to Titanfall 2

Phase Runner 1.0.0 · 6 October 2026 · implementation notes and future converter design

This document records the tested conversion of Apex `mp_rr_arena_phase_runner`, rBSP version 47, to Titanfall 2 `mp_phase_runner`, rBSP version 37. It describes the code and data retained with this project. It is a specification for extending that prototype into a converter, not a claim that arbitrary Apex maps or later formats are supported. The release is a playable visual and collision adaptation; original Apex game logic is incomplete.

## Evidence and reproducibility

The authoritative accompanying data are:

| File | Purpose |
|---|---|
| [binary-layouts.json](binary-layouts.json) | All 128 source and target lump slots, lengths, versions, parser formats and actual writer layouts |
| [respawn_conversion_layouts.h](respawn_conversion_layouts.h) | Packed serialized records with size assertions; explicit decoding remains necessary |
| [engine-limits.json](engine-limits.json) | Observed binary capacities, format ranges, safety policies and current measurements |
| [MISSING_CONTENT.md](MISSING_CONTENT.md) | All omitted static model types and adaptation limits |
| [static-placement-inventory.json](static-placement-inventory.json) | Every source static placement and its disposition |
| [missing-static-placements.csv](missing-static-placements.csv) | Omitted placements with original and translated coordinates |
| [entity-inventory.json](entity-inventory.json) | Original entities, target entities and identity matching without inferred behavioral equivalence |
| [source-and-tool-checksums.json](source-and-tool-checksums.json) | Input and tool provenance |
| [conversion-project.schema.json](conversion-project.schema.json) | Proposed intermediate representation for an automated converter |

The developer archive supplies project Python/C++/PowerShell source, the harness mod, compiler patch and these ledgers. Original Apex/TF2 input archives, third party compiler installations and historical binary build baselines are not included. Obtain matching inputs and pinned tools separately. The release builder currently depends on retained intermediate releases; it is not a clean, universal one-command build. Replace that dependency chain with the explicit stages below before distributing an automated converter.

## Conversion architecture

Read and validate → extract assets → normalize geometry/placements → choose supported content → generate native render and collision structures → compile materials → bake lighting → validate in engine → package.

Each stage must consume immutable, hashed inputs, produce a machine-readable report and retain source ownership for every generated primitive. Do not silently omit unknown records or substitute invisible collision boxes. Give omitted content a reason code, source identifier and recovery requirements. Separate binary compatibility, visual fidelity, physical solidity, game logic and performance: success in one does not establish the others.

Recommended future commands are `inspect`, `extract`, `plan`, `compile`, `bake`, `validate` and `package`. These are proposed interfaces. Current implementations are separate project scripts.

## 1. Read the source BSP and entities

An rBSP header is 2,064 bytes: `<4s3I` magic/version/revision/last-lump followed by 128 `<4I` descriptors. Descriptors carry file offset, length, lump version and fourCC. This source uses a small main header and external `.bsp.XXXX.bsp_lump` files. Resolve each external slot before validating length; record whether bytes came from the main file or an external file. Bound every pointer and count with checked arithmetic and reject truncated data.

Version 47 and version 37 share some layouts but also repurpose slots. Apex slots 0x12–0x16 contain world BVH/packed vertices/heightfield data where this TF2 branch has no equivalent. Apex 0x2B/0x2C are not the target texture string lumps. Rewrite semantics and references; changing the version number is insufficient. [binary-layouts.json](binary-layouts.json) records actual differences, including empty slots, instead of relying on a broad compatibility label.

Entities exist in the BSP and external entity partitions. Read all five source partitions as well as the main entity lump. Preserve duplicate keys if encountered and original text. Source inspection found 701 entities: world/brush entities, effects, gameplay helpers and dynamic models. Identity matches in the inventory are only candidates for equivalence. Brush model geometry can be exported even when the source entity behavior cannot.

Static placements are primarily in `GAME_LUMP.sprp`, not an entity-only prop list. The tested version-13 record is 64 bytes (`<7fH2B2H4f4b4B2H`), with a model dictionary and placement data. Validate dictionary indices, skins, leaf references and flags. Moving the game lump changes embedded absolute offsets; `compact_preview_bsp.py` relocates these while aligning output lumps to 16 bytes.

Relevant code: `audit_compatibility.py`, `extract_map.py`, `build_preview_source.py`, `compact_preview_bsp.py`, `document_conversion_release.py`.

## 2. Coordinates, transforms and ownership

Apex and Titanfall use the same XYZ world axes for this source. There was no supported XYZ swap behind the earlier culling problems. Phase Runner is recentered by subtracting `[26000,19000,0]` from world coordinates. Apply that translation exactly once to meshes, prop origins, collision, lights, cameras, bounds and probes.

For each static prop, compute `world = local @ R.T * scale + translated_origin`; `stage_prop_geometry.rotation` implements the Source pitch/yaw/roll convention. The parser's named angle components are unusual: use the tested accessor ordering rather than assuming field names represent world axes. Preserve rotation, scale, skin and source identity. Carry a placement record through geometry, collision and material generation so they cannot drift apart.

The tree correction demonstrates why origin alone is insufficient. Source placement 10414, nearest the supplied camera position `[-3213.1,-200.6,-1071.7]`, had a trunk bottom roughly 47.6 units above rendered snow. Nearby omitted placements were small vegetation, not a recovered structural support. `audit_tree_grounding.py` measures the bark root and intersects rendered ground vertically at the origin and eight nearby samples. It excludes the added trees themselves. The release lowers nine of twenty trunks to eight units below their minimum sampled support. Eleven embedded trunks remain unchanged. Collision, lighting and shadows use the same adjustment. No additional geometry or draw budget was added.

Ground sampling is a specific repair policy, not a universal placement correction. Mark intentional deltas separately from original transforms; do not snap suspended cables, cranes or source objects intentionally mounted on another prop. The audit and `trees.json` preserve the before/after evidence.

## 3. Recover models and material assignments

Extract RMDL/VG/PHY and RPak materials from the matching source archives. Presence of an exported QC/SMD is not sufficient, and absence of QC/SMD does not mean a compiled model is unavailable. The earlier QC-only missing-model audit became stale after direct compiled recovery. Current inventories distinguish available RMDL+VG, PHY and actual selected placement status.

The tested VG header is 160 bytes, magic `0x47567430`, version 1. Eighteen uint64 offset/count values begin at byte 16. Mesh records are 72 bytes (`<18I`), LOD records eight bytes (`<2hf`), with strip metadata. `read_vg_static.py` handles float positions or packed static positions and packed normals. Skinned data with flags `0x5000` needs skeleton/bone processing and is not covered by the static decoder. Validate vertex stride, flags, index bounds, strip range and mesh material slot per LOD.

Read RMDL skin and submesh material assignments instead of applying material zero to an entire model. The control-room consoles previously showed unrelated atlas fragments because this mapping was lost. Preserve original UVs; compiled recovery uses `v = 1-v` where required by the extraction convention and target triangle order `[0,2,1]`. Perform winding/UV conversion once, then check normals and tangent handedness. Double conversion yields inverted faces or incorrect normal maps.

This release bakes static model geometry into the native world mesh path. That makes native model conversion unnecessary for the selected content, but consumes world triangle/index capacity and discards animation and dynamic LOD. A future converter should support a separate native-model backend to recover dense foliage and repeated props within world budgets. That backend needs its own format, loading, collision and engine-limit validation; it cannot inherit the world-path limits.

Relevant code: `stage_prop_geometry.py`, `read_vg_static.py`, `prepare_model_sources.py`, `recover_model_slots.py`, `build_phase_runner_firs.py` and the model inventory scripts retained in the developer archive.

## 4. Generate native render structures

The target needs consistent positions (0x03), normals/tangents (0x1E), vertex streams, indices (0x4F), meshes (0x50), mesh bounds (0x51), material sorts (0x52), lightmap headers (0x53) and level partitions (0x7B). The release primarily uses 44-byte lit-bump vertices (0x49). The native vertex holds position/normal indices, UVs, RGBA, lighting fields, tangent index and auxiliary data. The tangent index high bit encodes mirrored handedness. See the accompanying packed header and JSON for exact layouts.

Mesh indices are uint16 local to the material sort's vertex base, not indices into an unlimited global buffer. Split streams conservatively at 60,000 vertices. Preserve actual per-mesh geometric bounds, normals and radius. Mesh partition order is opaque first, transparent last: `opaque_end == transparent_start`, then total. Remap every mesh reference whenever sorting changes.

Native submission pairs triangles. For an odd triangle count, emit a padded degenerate triangle repeating the final index while keeping the mesh's real triangle count unchanged. Budget with `3 * sum(n + (n & 1))`; counting only real triangle indices underestimates native use.

Phase Runner 1.0.0 has 4,982 meshes, 972,628 real triangles, 2,924,184 native padded indices, 483 material sorts and 479 static batch runs. It uses 92.96% of the observed world index capacity. The 95% project policy leaves 64,257 additional indices; raw capacity leaves 221,544. Those are not promises that any particular prop set will fit: padding, material splits and dynamic lights also matter.

Relevant code: `optimize_portalfree_render.py`, `audit_world_draw_budget.py`, `guard_native_sort_capacity.py`, `package_northstar.py`.

## 5. Visibility and portals

The current release uses conservative native cell/access-path data with no connected selective portal graph. The camera envelope is `[-16384,-16384,-8192]` to `[16384,16384,8192]`. Access-path boxes admit that envelope while mesh bounds remain genuine geometric bounds. Cell nodes use 32-byte records, references uint16 and reference bounds 32 bytes. All sorting changes must remap this graph, including the transparent partition.

Earlier selective portals culled the sky and caused hall-of-mirrors artifacts. Earlier pop-in also involved native draw capacity, partitions and access-path culling. A larger source map and unusual camera angle are not evidence of an axis mismatch or a simple player-out-of-bounds rule. Validate these systems independently.

A future portal builder should construct watertight cells and correctly oriented apertures, connect interior/exterior cells, propagate sky/background visibility, retain required loading dependencies and test the full camera/hull movement envelope. Doors require explicit state-dependent portal behavior. Until those tests pass, conservative visibility plus geometry/material optimization is the verified fallback. Do not restore selective portals merely to recover budget.

Relevant code: `repair_camera_visibility.py`, `native_preview_cells.py`, `test_phase_runner_release.py`.

## 6. Source world collision and prop physics

Apex BVH nodes (0x12) are 64 bytes: `<24h4I`. Bounds are grouped by axis, with four minima then four maxima per axis; they are not interleaved child XYZ boxes. Child indices come from words shifted right eight bits. Contents and child type bits share those words. Apply the source model collision frame and its `first_vertex` offset; the tested world model uses `first_vertex = 1`. Omitting that offset produced visibly desynchronized collision.

The decoded node kinds are 0 node, 1 empty, 3 compound, 4 regular triangle, 5 packed triangle, 6 regular quad, 7 packed quad, 8 inline STAR collision and 9 static-prop references. Compound and inline records require their local palettes, cursor alignment and coordinate frame. Packed signed global coordinates and unsigned local inline coordinates require different handling. Keep degenerate, clipped and unsupported counts in the report. Heightfield collision is not implemented as a general fallback.

PHY files use a tested 20-byte `<5I` header and relative-pointer IRPS graph. Root descriptors contain four int64 relative pointers; group records are 144 bytes, convex pieces 64, vertices float XYZ and faces signed-byte vertex lists terminated by -1. Validate every relative pointer against its owning base, piece vertex/face limits and winding. Triangulate polygon faces deliberately. `read_prop_physics.py` implements this tested layout. Without PHY, some tested RMDLs have an embedded collision BVH pointer at offset 532; this is a layout-specific fallback, not a universal RMDL constant.

Closed convex solids can become native brushes. Concave rocks, tunnels, rails and visible-frame surfaces require actual triangle collision or a documented compound decomposition. A whole-object AABB can block an entire tunnel or produce invisible walls. Keep visual collision fallbacks explicit and conservative; foliage cards should not become solid surfaces by default.

Target native collision uses:

| Lump | Role |
|---|---|
| 0x55 / 0x56 | Collision grid and uint16 first/count grid cells |
| 0x57 / 0x58 | Geosets and packed bounds |
| 0x59 / 0x5A | Primitive words and packed bounds |
| 0x5B | Contents mask palette |
| 0x5C–0x5F | Brushes, plane offsets, side properties and texture vectors |
| 0x42 / 0x44 / 0x45 | Encoded triangles, packed nodes and 44-byte triangle headers |
| 0x60 / 0x61 | Bevel starts and shared bevel indices |

Primitive words encode kind in the top byte, target index in the middle 16 bits and contents palette index in the low byte. Kind zero refers to a brush; `0x40` refers to a triangle header. Multi-primitive geosets reference a primitive range. Brush records contain center/extents, cut/bevel counts, brush identifier and plane base; six axial planes are implicit. Side properties must retain solidity and bevel interpretation. The current conversion predominantly uses solid contents and does not reproduce all Apex player/titan/NPC/glass/trigger contents semantics.

Triangle headers use `<6h4i4f`: flags, texture flags/id, vertex/triangle/bevel counts, first vertex/triangle/node/bevel, origin and scale. Encoded triangle words use a 10-bit base and two seven-bit deltas plus orientation bits. The project's 96-triangle groups are an encoding choice; the helper supports up to 300. Bounds centers and extents must each fit signed16. Clipping positions to ±32760 does not alone establish representable extents.

The release stores 7,654 brushes and 25,948 triangle headers; 7,134 brushes and 25,866 headers are active in the grid. Stored triangle count is 2,451,620. Disabled tunnel caps still occupy storage and must not be counted as active colliders. The historical ownership baseline is explicitly named `collision-ownership-baseline.json`; apply current tunnel/catwalk/art/tree overlays for the final state. A future converter should emit one merged active ownership ledger directly.

Tunnel repairs remove only verified tool-material caps intersecting the tested apertures, not every clip/nodraw surface. Some original portal PHY represented a filled disk and needed replacement with collision for the visible frame. The catwalk adaptation retains an 80-unit deck, 71-unit passage clearance, 42-unit rails and open entries; its full route is checked with player hull traces.

Relevant code: `decode_collision.py`, `read_prop_physics.py`, `rebuild_complete_collision.py`, `native_triangle_collision.py`, `repair_tunnel_passages.py`, `build_phase_runner_catwalks.py`, plus overlay reports. Search the retained sources for these concepts if a script has a different historical filename.

## 7. Native materials, PBR and asset loading

The release uses TF2 RPak version 7 and native `matl` version 12. Native world materials need correct shader dependencies, uberbuffer, glue, rasterizer/depth/blend states and matching depth passes. The four channels used here are albedo, normal, gloss and specular. Apex metalness/roughness textures need a deliberate adaptation; renaming them does not reproduce the original BRDF.

Dependency closure is essential. A road/decal shader that depended on an unmounted Glitch asset caused a previous loading hang. The fixed package embeds its own compatible shader dependencies with distinct GUIDs. Custom material packs must load after their required native common/Coliseum packs and must not rely on another map having previously been visited. The release uses a raw-map alias to the installed Coliseum pack and separate custom world/detail/glass/art/fir/presentation packs.

The twenty trees use fixed LOD2, 62 bark plus 952 foliage triangles per tree, with original UVs. Leaf alpha combines albedo alpha with opacity; mip generation preserves coverage. Compatible native two-sided foliage rasterization is retained. Leaf cards are excluded from static shadow casting to avoid rectangular card shadows; trunks cast shadows. There is no source wind animation or dynamic model LOD. Glass uses a compatible transparent native world pass rather than only lowering alpha on an opaque shader.

Texture names, GUIDs, source channel mappings, shader provenance and per-slot assignments should become explicit records in the future IR. Validate every external dependency before packaging and measure residency separately from geometric draw limits.

## 8. Lighting, lightmaps, menu stage and character light

The baker builds sunlight, sky and local-light data against converted geometry. The current map has seven lightmap pages and thirty local interior lights. It does not provide a general GI solver or freshly captured reflection cubemaps. Keep caster, receiver and decorative sky-dome masks explicit; photo sky geometry must not become an opaque sun blocker.

Native SKY A uses RGBM: decoded RGB is `rgb * (alpha * 3.984375 + 0.015625)` in linear units. SKY B stores direction, decoded as `rgb * 2.007874 - 1`. RTL A packs four six-bit light entries and an eight-bit page; unused entry is 63. RTL B stores visibility channels plus a half-resolution plane. The target's RTL light-page table must agree with hardware light indexing.

World-light records are 112 bytes in the tested lump version. Ambient entries are filtered from the native hardware table, so a raw WORLD_LIGHTS index is not a hardware light index. The sun at source/world slot one maps to hardware slot zero. Using menu-stage environment/light slots produced player/titan menu shadows and a small rectangular lit region around the camera.

TF2 multiplayer maps contain a physical menu/customization stage. This conversion retains an isolated native menu environment near `[-11776,11856,12736]`. Gameplay lighting and the stage use separate environments. Character lighting has 39,819 gameplay plus two menu probes, 39,821 total, and 16,383 KD nodes. Probe records are 48 bytes: fixed-point ambient coefficients (divide by 8192), visibility bytes, four local-light references and reserved fields. Native dynamic-light indexing also applies its reserved offset. Use filtered hardware IDs, rebuild the KD access structure and keep stage probes separate.

Current code and reports cover these exact relationships. General conversion must infer them from target format and native reference maps rather than assuming every source has one sun and thirty point lights. Retain native reference-map probes, captures and light tables as test fixtures.

Relevant code: `apply_baked_lighting.py`, the retained C++ baker sources, `character-lighting.json`, `interior-lights.json`, and `loading-repair.json`.

## 9. STBSP and texture residency

Titanfall requires an STBSP asset catalog alongside the BSP. `build_preview_stbsp.py` writes the tested v8.0 header, 392 bytes, magic `0xCB00CBB5`. Six uint64 offset/count descriptors begin at byte 168. Material-info and column counts are record counts with 24-byte strides; other blocks use byte counts. Physical block order is `[1,2,3,0,4,5]`. Offsets are absolute within the file.

Material records link names and 64-bit asset GUIDs. Column records contain payload-relative offset, size, coverage scale and packed bounds. This release supplies a resident catalog with empty coverage columns and custom textures marked nonstreaming. It does not implement complete spatial mip streaming. STBSP and texture STARPak are different systems. A future streaming backend must implement verified spatial coverage/residency semantics and test camera movement under real VRAM pressure.

## 10. Limits and capacity planning

Limits below are scoped to the installed binary hashes in [engine-limits.json](engine-limits.json). Instruction addresses can change between versions.

| Constraint | Evidence / interpretation |
|---|---|
| 3,145,728 submitted world indices | Native capacity, engine RVA 0xB72AF |
| 2,048 world draw batches | Native capacity, engine RVA 0xB7304; dynamic light masks can split static batches |
| 8,192 material sorts | Native loader fixed bitset; exceeding it previously corrupted loader state |
| 65,535 uint16 mesh/local vertex/primitive index | Serialized maximum index, not a universal total-prop limit |
| 255 cut/bevel or cell child/direct-reference counts | Serialized byte fields |
| 32,767 packed center/extent | Signed16 maximum, requiring both center and extent checks |
| ≤95% world indices; <512 static batches | Project margins, not native limits |
| 60,000 local vertices; 96 triangles per collision group | Conservative writer policies |

No universal playable map dimensions, safe native entity/prop total, VRAM residency cap or complete portal capacity was established. Do not extrapolate a total-object limit from world-baked triangles. Allocate budget by backend, native padded cost and material keys, then validate worst-case simultaneous visibility. Dense foliage is the largest omitted category and should be planned before export rather than appended until the engine stops drawing.

## 11. Validation and failure diagnosis

Run structural validation before starting the game: lump strides and versions; finite values; all indices; relocation; dictionary/asset dependency closure; skin/submesh/UV mapping; material-sort count; opaque/transparent partitions; reachable mesh references; index padding; collision grid and active ownership; contents and bounds; light/probe references; loading metadata. Fail with a specific source ID rather than allowing a corrupt intermediate onward.

Then use the native harness with an isolated profile. Cold launch, inspect all important regions, test tunnel route hull clearance and floors, look horizontally/up/down, stand on stairs, grapple surfaces, return to a native map and reload. Compare camera captures with native screenshots and source provenance. The release checks include 4,196 native collision/clearance probes across terrain, props, trees, catwalks, rails, truck supports and routes; they are sampled tests, not proof of every possible player trajectory.

The harness controls local server/client/UI script contexts through authenticated localhost HTTP. It launches owned processes, uses native map/camera commands and the game's screenshot command, and exports redacted logs. It does not require desktop input simulation. Keep tokens/session logs outside published developer packages. Clear custom cameras before disconnecting. Record failed runs too: a first same-map reload with an active camera produced a stock loadout/server exception; subsequent validation must establish the corrected reload procedure independently. Do not suppress that incident in provenance.

| Symptom | Investigate first |
|---|---|
| Visible only at some angles | Access paths, partitions, native index/batch exhaustion, then actual mesh bounds |
| Hall of mirrors | Sky/background culled or incompatible render structures |
| Grapple/native crash | Sort capacity, corrupt collision/index references and loader memory |
| Invisible tunnel barrier | Filled IRPS cap, broad convex fallback or tool clip ownership |
| Collider offset from model | Placement translation/rotation/scale and source collision first-vertex frame |
| Console atlas fragments | RMDL skin/submesh mapping and UV conversion |
| Black map with camera rectangle | Sun environment, RTL hardware index and sky caster mask |
| Infinite loading | Missing RPak shader/dependency closure, residency and main-map alias |

## 12. Package and future implementation requirements

A mod contains `mod.json`, `mod/maps/mp_phase_runner.bsp`, matching STBSP/partitions, `paks/rpak.json`, custom RPaks, scripts, native loading artwork and localization. Local-test reporting/auth settings must be opt-in and disabled in the shipping default. Require the installed native common/Coliseum assets; avoid redistributing whole original game archives in a developer kit. The map remains an adaptation with no complete Apex portal teleport/gameplay/entity implementation or certification of all TF2 modes.

The next converter should provide version-dispatched readers; checked binary parsing; complete placement/entity/collision ownership; both world and native-model render backends; source skin/material adaptation; shader dependency closure; terrain blending; streaming catalog generation; robust cell/portal construction; collision contents translation; lighting/probe/cubemap generation; explicit budgets; engine regression routes; and deterministic output hashes. Unknowns need an unsupported report, never silent data loss.

The intermediate schema supplied here is a proposed contract. Extend it per format version, keep source records immutable, distinguish deliberate adaptations from unsupported features, and make each stage resumable by hash. Existing scripts constitute reference implementations and test evidence for this map, not a universal parser library.

## Primary references

[bsp_tool Titanfall format coverage](https://github.com/snake-biscuits/bsp_tool/blob/master/docs/supported/titanfall.md), [Northstar RePak material documentation](https://docs.northstar.tf/Modding/repak/assets/material/), [MRVN Radiant project](https://mrvn-radiant.github.io/), [r-ex RSX](https://github.com/r-ex/rsx). The local source/tool checksums and compiler patch identify the versions actually used; an upstream page alone does not pin a reproducible build. MRVN Radiant is useful for format/compiler reference, but this project does not rely on a complete interactive map editor.


## Gameplay authoring update � 1.1.0

See [gameplay layout and mode hooks](GAMEPLAY_MODES.md) for native team spawns, CTF, hardpoints, Fastball and verification. Earlier inventories describe the 1.0.0 source conversion; gameplay-layout.json records the additional authored target entities.
