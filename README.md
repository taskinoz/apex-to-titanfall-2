# Apex to Titanfall 2 map ports

New **0.1.0 early Northstar previews**: Overflow (`mp_overflow`), Party Crasher
(`mp_party_crasher`) and Firing Range (`mp_apex_firing_range`). These have native
geometry/collision, materials, direct lighting, loading artwork and minimaps.
Pilot modes and single-client spawn/reload checks pass; substantial scenery,
source shader behavior and Apex interactions are still missing. See the
[new-port report and Olympus feasibility](docs/candidates/approved-port-work-2026-10-13.md).
Clean player ZIPs are local in `output/`. Enable one new preview at a time.

Current builds: **Phase Runner 1.6.0** and **Drop-Off 0.10.0**. Restore
432 and 366 source scenery placements respectively, reaching 97.04% and
97.06% of the native world index capacity. No dynamic entities are added.
Existing minimaps, lighting, gameplay, collision exclusions and catwalks remain.
AI navigation is still incomplete. See [budgets, recovery and validation](docs/arena-scenery-fill-2026-10-13.md),
including the initial test failures and the scope of subsequent native checks.

- [Saved map comparison site](site/dist/index.html): existing wider-area views
  plus matched views of the three new previews, with earlier snapshots retained.
- [Site source and release export](site/README.md).
- [Repository contents and local dependencies](REPOSITORY.md).
- [Northstar harness](test-harness/README.md) and [R5R harness](r5-harness/README.md).
- [Native minimap conversion](docs/arena-minimaps-2026-10-13.md).
- [Next conversion candidates: Overflow, Party Crasher and Firing Range](docs/candidates/assessment-2026-10-13.md).
- [Northstar banners and Apex displays](docs/banner-display-textures-2026-10-12.md).

Clean downloads: `output/PhaseRunner-1.6.0-Northstar.zip` and
`output/ArenaComposite-0.10.0-Northstar.zip`. Previous 1.5.0 / 0.9.0 ZIPs,
runtime snapshots and installed copies remain available for rollback.
The comparison site is local and has not been deployed.

The investigation history below records earlier previews and their limitations;
those version-specific notes do not describe the current installed builds.

---

# Apex to Titanfall 2: Phase Runner investigation

Latest development build: **0.1.36**. The 0.1.35 portal experiment is withdrawn after the user reported sky culling and hall of mirrors. The exact 0.1.34 single-cell/portal records are restored, with conservative sky and tunnel visibility bounds. Compatible render-batch records drop from 4,561 to 337, and duplicate vertex data drops by 8,707,864 bytes while every rendered triangle retains its exact corner attributes and material binding. Seven focused regressions and all 927 fresh native collision checks pass. The map loaded in 21.51 seconds. Client rendering and frame rate still need verification; no FPS improvement is claimed. Lighting, PBR textures, collision and both walkways retain the user-confirmed 0.1.34 data. See `VISIBILITY.md` and the packaged validation reports. The full 0.1.34 rollback archive is retained. `cmd phase_runner_where` displays and logs coordinates.

Version **0.1.25** adds original convex physics and native sweep bevels to 575 placements: 17 crates, 314 ring sections and 244 hollow pipe elbows. Removing 5,037 world brushes wholly enclosed by existing rock solids reclaims capacity while preserving the existing solid union. The single-cell visibility tree has a conservative maximum pending-node count of 256 rather than 2,048. This diagnostic did not resolve the user's camera-angle disappearing objects; queue involvement is not established.



Status: a Titanfall 2 geometry preview has been compiled and packaged as `PhaseRunner.Preview` for Northstar. **The complete playable Phase Runner port remains unfinished.**



## Northstar development preview



The mod is in `northstar/PhaseRunner.Preview` and installed at `D:\Games\Titanfall2\R2Northstar\mods\PhaseRunner.Preview`.



Version 0.1.17 corrects the visibility regression exposed by comparison with native Homestead and Colony. All 7,037 internal branches in those maps store contiguous subtree reference ranges, including the starting reference on branches with no direct objects. The preview incorrectly wrote zero to every internal branch start. Twenty-six offsets are corrected; the complete BSP comparison verifies only 44 changed bytes, all within these entries. Geometry, material assignments, lighting, collision and the STBSP remain byte-identical. All 37 tests passed, including native tree traversal, whole-branch versus leaf mesh submission and rejection of the old zero-offset pattern. `output/phase-runner/native-visibility-range-audit.json` records both reference maps. The original 0.1.16 archive is retained as the rollback copy, and the installed BSP patch is SHA256 verified. Client pop-in still requires visual confirmation. The 0.1.17 dedicated server loaded in 48.15 seconds with 24/24 sampled collision hits; that check does not exercise GPU visibility.



Version 0.1.16 corrects both tunnel surfaces using the original Season 3 v54 compiled mesh material slots and skin table. Previous SMD labels repeated the wrong metal material across several sections. The repair replaces 100,996 old tunnel triangles matched exactly by position, normal and UV, retains all other triangles, and omits 2,736 unsupported AO/decal overlay triangles from the opaque pass. It also restores 321 newly recovered moss/snow terrain placements with validated original skins and transforms (657,408 triangles). The final map has 5,348,467 triangles in 719 meshes, with all visibility references, bounds and new winding verified. Collision buffers remain unchanged. The final BSP is 1,363,991,836 bytes; the native RPak contains 348 materials/1,002 assets with resolved dependencies, and the STBSP catalog contains 177 material GUIDs. All 35 unit checks passed. Portal pop-in, terrain overlap and GPU appearance still require client verification. Apex layered materials, native prop collision, baked lighting and spatial texture streaming remain unfinished. The SMD re-export crashed; only its complete validated moss mesh was used, alongside the prior complete tunnel exports. Installed 0.1.15 is backed up under `output/installed-backups/PhaseRunner.Preview-0.1.15`. The 0.1.16 dedicated server loaded in 44.82 seconds and passed 24/24 sampled collision probes; that check does not verify GPU pop-in.



Version 0.1.15 restores 1,990 additional placements across the arena: 1,799 structures/details and 191 rocks from 130 model types. The pass adds 2,699,483 render triangles (ten degenerate source triangles are discarded) and preserves source transforms, completing the recovered textured structural selection before prioritizing larger rocks within the 2.7-million-triangle budget. Forty-six placements lack required textures and are omitted; 733 further placements exceed the render budget. Foliage, decals, unrecovered meshes, exact material slots and native prop collision remain unfinished. The map now contains 4,693,795 triangles in 648 meshes. A native spatial visibility tree with 63 nodes reaches every mesh; each parent/object bound is verified, and the old map's 5,983,116 vertices were separately checked against mesh bounds. Portal pop-in with both distance and camera angle remains a client verification item. Compaction preserves all active non-game lumps byte-for-byte and relocates only absolute game-lump directory addresses, reducing the final BSP to 1,178,694,876 bytes. The custom RPak has 342 materials/984 assets with resolved dependencies. The updated STBSP contains 174 native/custom material GUIDs and 1,600 empty resident-texture columns; spatial mip streaming is still unfinished. All 30 checks passed. The dedicated server loaded in 57.62 seconds with 24/24 sampled collision hits. Client visibility and GPU performance remain unverified for the expanded scene.



Version 0.1.14 fixes the SMD importer reading only the first triangle section. Legion writes separate triangle sections for submeshes; all complete sections are now read. This build appends only omitted sections to 1,416 previously restored placements, adding 466,991 triangles in 61 meshes while preserving original geometry buffers and physics. Truncated Marvin exports are excluded and unknown material slots retain an explicit first-skin approximation. Two regression checks cover repeated sections, incremental restoration and truncated later sections. All 27 checks passed. The dedicated server loaded in 25.00 seconds with 24/24 sampled collision hits. The Live Fire Deck reference was extracted with CRC verification: 3,000 world meshes, 2,088 static props and 256 world lights, with substantial baked lightmap/CSM data. That reference is recorded in livefire-reference-audit.json; its spatial lighting cannot simply be copied to the Apex map. Missing scenery and collision remain unfinished.



Version 0.1.13 adds 626 source prop placements from 58 model types within 4,000 horizontal units of (-2213,3026,-1091). Structures are prioritized before rock details within a 500,000-triangle budget. Architectural details used that budget before any rocks could be added. This includes recovered railings, stairs, wall panels, pipes and equipment omitted by the earlier general-prop budget. Exact transforms are retained and no duplicate previously restored placement is added. Foliage, decals, unavailable meshes and untextured blue barrels remain excluded. Material bindings still approximate missing SMD slots; native prop collision, full landscape coverage and ground marks remain unresolved. The native RPak has 272 materials/786 assets with verified dependencies. All 25 checks passed. The dedicated server loaded in 27.57 seconds and hit 24/24 sampled collision probes. The final map has 1,527,321 triangles in 274 meshes, including 77 new detail meshes. Client appearance needs verification.



Version 0.1.12 restores 188 construction/crane support placements from nine model types (6,171 triangles), keeping source transforms. It removes the obsolete native sky camera and Titanfall vista spawn while preserving the Apex sky dome. Added render geometry passes bounds, winding and visibility checks; collision is unchanged. Four new recovered materials bring the RPak to 234 materials/675 assets. The STBSP catalog is regenerated for this build; actual spatial mip streaming remains unfinished. User coordinates beneath floating areas are (-3250,-3479,-1115) and (-2213,3026,-1091). These changes need client verification; ground marks remain unresolved. Snow albedo is fully opaque and lacks the reported shapes, so they are not painted into that texture. Doors are left as requested.



Version 0.1.11 replaces nine unrelated prototype lights with the recovered Phase Runner sun and sky ambient light, translating their origins and matching the level's sun direction. Static shadow geometry and original baked illumination remain unfinished; the existing temporary native lightmaps are retained. Only lighting records and the empty CSM root change; render geometry, materials and collision are unchanged. A native v8.0 `mp_phase_runner_preview.stbsp` sidecar is packaged in the mod's `mod/maps` folder. Its 118 material GUIDs resolve to the mounted native/custom RPaks, and all 1,600 empty grid columns round-trip through the native-format parser. These empty columns describe resident textures: spatial mip coverage and starpak-backed streaming are not implemented. The 0.1.11 client log confirms LoadStreamBsp opened the sidecar without a reported format error; the current build still needs a client check. All 25 checks passed.



Version 0.1.10 restores 316 Phase Runner ring-frame, ring-panel and tunnel placements from seven model types that were previously excluded with the `levels_terrain` folder. These add 83,572 triangles in ten meshes, retaining the 0.1.9 terrain UV correction and 0.1.8 flicker fix. Every added triangle has validated native winding, vertex/index bounds and visibility references; prior geometry buffers and collision are preserved. All new SMD surface bindings are unavailable, so their first QC skin material is an explicit approximation using already recovered textures. Native prop collision is not added. The map now contains 1,021,150 triangles in 192 meshes. All 22 checks passed; client appearance remains to be verified. The user's 0.1.9 screenshots confirm dirt and lavender texture detail, while white terrain remains very bright and some structures were missing.



Version 0.1.9 restores the recovered source UV transforms on 22,533 triangles across five terrain/base materials (67,599 vertices). The world-coordinate moss UVs now repeat once per 1,024 units rather than once per unit; dirt and metal-to-dirt base UVs repeat once per 256 units. The transform is applied before restoring the OBJ importer's V flip. Only the albedo UV fields of these vertices change; every other vertex field and BSP lump is preserved, including indices, geometry, collision, the sky and the 0.1.8 overlay omission. All 22 checks passed. Multi-layer terrain blending, detail textures and final lighting remain unfinished; client appearance needs another visual check.



Version 0.1.8 addressed reported ground z fighting. It omits 44,249 source-transparent terrain/grime/track overlay triangles that the current opaque shader approximation cannot render correctly. It also removes 60 identical prop triangles, matching position, normal, UV, color, lightmap UV and winding. The result has 937,578 triangles in 182 meshes. All vertex/material buffers and collision lumps are unchanged, and every retained mesh reference and visibility bound was checked. The dedicated server loaded in 29.36 seconds with 24/24 collision probe hits; all 18 existing checks passed. The user confirmed flickering has stopped. The latest screenshot shows restored props and sky, while large white/purple ground patches remain. Some original terrain detail is temporarily missing until native blend materials are implemented. The recovered moss/snow terrain material includes separate albedo/albedo2 and layerBlend images, whereas the preview material currently binds only one albedo layer; full terrain blending remains unfinished.



Version 0.1.7 recovered Apex textures for 79 of 85 world materials, covering 225,303 of 227,920 original world triangles before the overlay omission. Their original face assignments were checked against every compiled triangle. The user confirmed the world textures and sky dome render in 0.1.6, and many restored props/models render in 0.1.7. Native Titanfall 2 shaders approximate the original Apex shaders; layered blends, translucency and final lighting are not faithfully reproduced yet.



The geometry pass restores 1,368 structural props from 83 recovered models at their original Source-style position, pitch/yaw/roll, scale and skin selection. These add 749,999 triangles as 98 world meshes; the complete preview has 981,887 triangles. Selection prioritizes the inspection spawn under a 750,000-triangle budget. 2,359 available structural prop placements remain outside this pass, along with foliage, rocks/terrain and unavailable model sources. Original collision data is unchanged: these are render meshes, not converted native prop physics. The model exports lost per-surface assignments on 707,221 triangles; those use the first original QC skin material as an explicit approximation. Texture images were found for 745,655 restored triangles. Geometry validation checks every restored triangle's indices, bounds, native winding and visibility references. The local server loaded in 27.88 seconds, passed 24/24 collision probes and 18 checks. Client prop appearance still requires visual verification.



`tools/mdlshit` is available at revision `18fe99af370b35ace20c3deeea955caf9c789bb9`, with its source and GPL license retained. It converts compiled Source v49 models to TF2 v53; the extracted SMD/QC meshes first need a compatible Source compiler. Its converter also contains a v52 path, while v48 is unimplemented. No native model conversion with this tool has been claimed.



Version 0.1.6 replaces the six unsuccessful sky portal quads with a 3,968-triangle dome carrying the recovered Phase Runner sky image. Sphere-map UV projection is approximate; the original vista model remains unconverted. Every dome triangle has verified native inward winding and valid UVs, and all collision/entity lumps remain unchanged. It loaded on the local dedicated server in 25.16 seconds with 24/24 collision probe hits. Client sky rendering is still unverified. Missing static props, exterior collision and source backdrop placement remain unresolved.



The 0.1.4 build contains 48,403 support surfaces in the arena region and 15,597 wall surfaces prioritised around the inspection spawn (up from 3,878 walls). Distant backdrop floors are excluded to keep target collision indices within their native limits. Static props, special collision leaves, some walls and original contents flags remain unfinished.



Lighting now samples a lit native floor instead of an empty atlas pixel. Sky mesh metadata matches the target layout; visibility/world bounds include the sky camera and model. The native `grave_se.mdl` vista is placed at the camera, and its local MDL is staged because a native RPak alias does not mount the source map's model VPK. These MDLs were extracted with CRC validation from this installation's Coliseum VPK. The native RPak alias supplies their GPU assets. The dedicated engine test loads without a script error and passes 24 collision checks: 12 supports and 12 walls. Occupancy flags distinguish traces beginning inside a new wall from absent collision. The next manual check must establish ground lighting, sky rendering and wall behavior.

The supplied `Send-AIHarnessCommand.ps1` belongs to the PS4 Northstar project. Its `docs/AI-HARNESS.md` requires PS4 runtime natives (`NSAIHarness*`); the Windows 1.31.13 launcher lacks them. `AI.Harness` is disabled in the Windows installation because it caused a UI compilation error. The previous enabled-mod settings are backed up in `logs/enabledmods-before-harness-test.json`.



- `mp_phase_runner_preview.bsp` is a genuine compiled rBSP v37 file, not an Apex file with its version changed. It contains 227,932 render triangles (including six sky quads) and expanded approximate collision. Tool surfaces are excluded from rendering. The map is translated by (-26000, -19000, 0), without resizing.

- The compiler is MRVN-Radiant with a local OBJ-to-world-mesh extension and a compiler-only build configuration. Its source and licenses are retained under `tools/mrvn-radiant`; local changes are preserved in `output/phase-runner/mrvn-compiler.patch`.

- Northstar detects the loose BSP in `mod/maps`. `paks/rpak.json` aliases preview map assets to installed native Coliseum packages and loads `phase_runner_world.rpak` afterward. The custom v7 RPak includes 294 recovered texture assets and 158 native v12 materials, including color passes. All external material dependencies are present in the native common/Coliseum packages. Static prop models remain unconverted.

- Earlier startup tests loaded the map and hit all 12 sample collision probes. That evidence covered only sampled surfaces and did not establish walking collision. The manual screenshot is the visual evidence for version 0.1.2. Automated desktop capture remains unavailable because the helper fails to initialize.

- Fourteen tests cover preprocessing, convex planes, native render layouts and winding, GPU/visibility ranges, collision bounds and references, grid order, and the sky camera entity. Results are recorded in `logs/northstar-0.1.4-tests.log`.

- Legion+ recovered diffuse images with the newly available high-resolution streaming archives. RePak built the compatible material package using native Coliseum world shader parameter buffers. Version 0.1.5 loaded on the dedicated server in 29.13 seconds, passed all 24 sampled collision probes and the existing 14 checks. The server does not verify GPU rendering. Evidence is in `logs/preview-0.1.5-final.log` and the mod's `runtime-validation.json`.



This is an inspection preview: missing props, six world materials, faithful Apex shaders, a working sky, complete collision, collision flag translation, verified gameplay spawns, lighting, and gameplay integration remain required. Use `map mp_phase_runner_preview` in Northstar's console. Inspection may require `sv_cheats 1` and `noclip`; normal walking is not supported across the map.



Build and package it from this directory:



```powershell

python build_preview_source.py output/phase-runner/mp_rr_arena_phase_runner.obj output/phase-runner/collision/world-collision-regular.obj output/phase-runner/preview-source --collision-limit 1024

tools/mrvn-radiant/install/Release/remap.exe -game titanfall2 -fs_basepath output/phase-runner/preview-source output/phase-runner/preview-source/mp_phase_runner_preview.map

python repair_preview_render.py output/phase-runner/preview-source/mp_phase_runner_preview.bsp inputs/titanfall2-coliseum/maps/mp_coliseum.bsp output/phase-runner/preview-render/mp_phase_runner_preview.bsp

python merge_collision.py output/phase-runner/collision/world-collision-regular.obj output/phase-runner/collision/world-collision-merged.obj

python expand_preview_collision.py output/phase-runner/preview-render/mp_phase_runner_preview.bsp output/phase-runner/collision/world-collision-merged.obj output/phase-runner/preview-collision/mp_phase_runner_preview.bsp

python -m unittest test_expanded_collision test_northstar_build test_binary_tools -v

python package_northstar.py output/phase-runner/preview-collision/mp_phase_runner_preview.bsp output/phase-runner/preview-collision/source-build.json northstar/PhaseRunner.Preview

```



`phase_runner_local_test` defaults to 0. The test mode disables server reporting after startup scripts and runs collision trace probes. It enables offline server authentication only when the listener `ip` is explicitly `127.0.0.1`. This is a local development setting, not a gameplay feature.



## Installed asset recovery



Source installation: `D:\Games\R5Reloaded\R5R Library\LIVE`. The source installation remains unchanged. Four standard streaming packages were copied into the workspace; the optional packages are absent from the installed source.



- Recovered 173,727 regular world collision polygons in `output/phase-runner/collision/world-collision-regular.obj`. All polygons pass parent BVH bounds checks. Correct decoding requires the world model's first-vertex offset of 1. The diagnostic export omits 6,931 prop leaf references and eight special collision leaves; it is not complete collision.

- RSX 2.3.0 inventories the package but its tested export commands produced no usable asset files. Legion+ 1.9.2 exported source meshes and textures, but crashed on some package exports. Partial output was audited rather than treated as a complete extraction.

- The map, common SDK, common multiplayer, and main common package exports provide valid nonempty meshes for 217 of 271 required prop paths. The remaining 54 paths are listed in `output/phase-runner/export-validation.json`. Validation checks triangle syntax; it does not prove visual fidelity or complete submesh coverage.

- `prepare_model_sources.py` stages those 217 models in `output/phase-runner/prepared-models`, repairing 217 unambiguous QC mesh references with zero unresolved studio references. Original exports are retained. Material bindings, target model compilation, and prop collision remain unresolved.

- Four binary regression tests pass, including a synthetic collision case that catches an incorrect first-vertex offset.



Repeat preparation using the current export audit (audit raw export folders separately if adding more assets, to avoid counting prepared copies):



```powershell

python prepare_model_sources.py output/phase-runner/export-validation.json output/phase-runner/geometry-summary.json output/phase-runner/prepared-models

python -m unittest test_binary_tools -v

```



## Further investigation while game assets install



- Downloaded and inspected the r5sdk engine/collision definitions, the abandoned C++ BSP viewer, and the original snake-biscuits converter. Built the original converter successfully with CMake/Clang. It rejects the Apex input without creating a target BSP.

- Installed local copies of RSX 2.3.0 and RePak 1.4.0 release tools. Legion+ was subsequently added as an extraction fallback. No valid Titanfall 2 asset package has been built yet.

- Extracted 75 map-related files from the existing native Coliseum VPK, and 32 files from Phase Runner's server VPK. Every extracted file passed its archive CRC. All 20 server BSP lump files match the client copies byte for byte.

- Added `audit_compatibility.py`, which compares the actual map structures against Coliseum. It identifies 29 candidate matching record layouts, 20 same-name lumps requiring conversion or further schema inspection, and 12 repurposed slots. Equal layouts are not proof of semantic compatibility.

- Validated 27,343 BVH nodes: no inverted active-child axis bounds and no out-of-range node/leaf/mask references. Map bounds are grouped as four minima followed by four maxima per axis, rather than the interleaved view in bsp_tool's current BVH class. Child types occupy low nibbles; correct child ordering also matters. These checks validate file structure, not in-engine collision behavior.

- RSX source contains decoding code for type-3 compound collision leaves and regular/packed triangles, quads, and type-8 leaves. It does not resolve static prop leaves without the model assets. Its model decoder's packed coordinate handling should be independently checked before adapting it to map data.

- Added `decompress_rpak.py` for Zstandard-compressed v8 packages, using Python 3.14's standard-library decoder and the SDK's documented header normalization. RSX cannot directly read the launcher package's ZSTD compression.

- Found a second RSX obstacle in this custom package: incorrect segment allocation sizes. The optional `--normalize-segments` preprocessing recalculates those sizes from the page alignment tables on a separate workspace copy. Payload bytes and page offsets are preserved; original downloads stay untouched.

- After preprocessing, RSX inventories all 3,226 assets: 266 models, 1,033 materials, 1,323 textures, 312 shaders, 289 shader sets, and three other assets. This is an asset inventory, not a successful full model export; installed streaming files enabled the later partial Legion+ recovery described above.

- Four regression tests pass, covering lossless decompression, preservation of original inputs, allocation padding correction, invalid alignment rejection, actual map consistency, and collision report validation.



Reports: `output/phase-runner/compatibility.json`, `output/phase-runner/asset-status.json`, and `output/phase-runner/rpak-assets.csv`.



The shared packages referenced by Phase Runner are `pc_all.starpak`, `pc_all(02).starpak`, `pc_all(03).starpak`, `pc_sdk.starpak`, and their four `.opt.starpak` counterparts, under the R5Reloaded `paks/Win64` directory. Optional streaming files may only be needed for higher quality assets; that has not yet been tested.



Repeat the asset preprocessing and inventory:



```powershell

python decompress_rpak.py inputs/r5/paks/Win64/mp_rr_arena_phase_runner.rpak inputs/rsx-compatible/mp_rr_arena_phase_runner.rpak --normalize-segments

tools/rsx/rsx_nogui.exe -nogui -nocachedb --list output/phase-runner/rpak-assets.csv --listformat csv inputs/rsx-compatible/mp_rr_arena_phase_runner.rpak

python audit_compatibility.py inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp inputs/titanfall2-coliseum/maps/mp_coliseum.bsp --output output/phase-runner/compatibility.json

python -m unittest test_binary_tools -v

```



Target installation: `D:\Games\Titanfall2`, with Northstar present. The new `PhaseRunner.Preview` mod directory has been added under `R2Northstar/mods`.



## Verified inputs and outputs



- Downloaded 12 Phase Runner files directly from the public live-channel manifest used by the R5Reloaded launcher. All SHA256 checksums match `inputs/phase-runner-manifest.json`.

- Extracted 76 client archive files, checking every file's CRC32. The bundled r5vpk LZHAM DLL supplies decompression; bsp_tool supplies the directory parser.

- The map is rBSP version 47, revision 30. Its 2,064-byte main BSP stores headers; actual data resides in companion `.bsp_lump` files.

- All external lumps parse with no bsp_tool loading errors. The main-file loader misinterprets some zero-offset external lumps as internal data; geometry export explicitly uses the parsed external data.

- Recovered 195 brush models, 2,436 meshes, and 228,204 render triangles into `output/phase-runner/mp_rr_arena_phase_runner.obj`.

- Recovered material names and 271 static prop model paths in `output/phase-runner/geometry-summary.json`. The map places 16,862 static props. Their meshes and textures are not included in the OBJ.

- Inventory validation finds no missing or out-of-range lump data.



## Why this is not yet a port



Titanfall 2 expects rBSP version 37. Apex replaces Titanfall 2's collision grid and triangle collision structures with BVH nodes and leaf data; changing the version does not convert these structures.



Phase Runner uses regular triangles/quads, static prop leaves, special collision, and compound collision leaves labeled UNKNOWN_3 in bsp_tool. The diagnostic decoder now handles regular polygons and compound leaves with map-specific bounds and vertex offsets. Special collision and static prop collision remain unresolved. Collision recovery must account for every used type, then build valid target collision structures. Rendering triangles are not a validated replacement for the collision mesh.



Both linked bsp_regen projects target Titanfall 1 inputs. The RoyalBlue1 source explicitly rejects other BSP versions. Neither supplies an Apex-to-Titanfall-2 conversion path. The original converter also excludes the asset conversion needed for a complete map.



Remaining work includes:



1. Recover authoritative Apex world and prop collision, including unsupported leaf layouts.

2. Write the Titanfall 2 collision grid, primitives, triangle headers/nodes/bevels, and model references.

3. Convert render lump layouts, visibility references, lights and probes; validate cross-lump indices.

4. Extract/convert required prop models, materials and textures from RPaks and any shared packages. The per-map RPak download alone does not prove all shared dependencies are available.

5. Replace Apex entities and scripts with Northstar-compatible entities, spawns, and map registration.

6. Package the target assets, then verify loading, rendering, collision, movement, and respawning in Northstar.



## Repeat the completed steps



Run from this project directory with 64-bit Python on Windows:



```powershell

python extract_map.py inputs/r5/vpk/englishclient_mp_rr_arena_phase_runner.bsp.pak000_dir.vpk inputs/extracted-client

python inspect_maps.py inputs/extracted-client --output inputs/phase-runner-inventory.json

python export_geometry.py inputs/extracted-client/maps/mp_rr_arena_phase_runner.bsp output/phase-runner

```



The OBJ exporter retains brush entity transforms and material names. It exports render geometry only. Open the OBJ in Blender or another compatible viewer for inspection.



## Tool revisions



- bsp_tool: `655627ea8704353ac14bd753df8ca05c15838eda`

- RoyalBlue1/bsp_regen: `5b761e6bad2751051218928195c6e54edcd3480a`

- r-ex/r5vpk: `48e64fa220f5ffff9d0a9cce8dffe9048bc82e7e`

- r5sdk: `c49e0d2123bc3ddb53419005ddd7c6ef73925faf`

- rsx source: `6014ca814b945c52b991f2914d7bb665e1588272`

- original bsp_regen: `bdbaec7fbc865e3738267e41903533e4020b5e7c`

- MRVN-Radiant: `8022aefcf9506786fe9edf138dbf48cde0fa82f6`, with local compiler-only and OBJ-import changes



Upstream source and licenses remain in their respective `tools/` directories. Downloaded game assets are local research inputs.





## Northstar preview 0.1.20 — 3 October 2026



Installed under `D:\Games\Titanfall2\R2Northstar\mods\PhaseRunner.Preview`. Restart Northstar and load `map mp_phase_runner_preview`.



The original 7,010,627 render triangles now use 22,171 spatial sections (at most 512 triangles each). The 892 material-sort records and all vertex attributes are shared unchanged; the native visibility tree and actual mesh bounds are rebuilt. A development minidump exposed the engine material-sort loader's fixed bitset when duplicate sort records were created. The corrected build shares the original records and rejects oversized sort tables before packaging.



Native collision is added to 341 rock placements and 676 pipe placements, plus partial surface collision on both portal tubes. 845 placements preserve original IRPS convex pieces. 172 dense rock BVHs use bounded convex approximations. 67 approximations overlapping the portal bounds are withheld to avoid closing those areas. 140 exact duplicate world brushes are removed while preserving every original world solid. Compound grid references allow the added brushes within the native index capacity. Large portal collision and small hollow elbow decorations remain incomplete.



56 checks pass. The final dedicated server loaded in 45.278 seconds, retained 24 existing world probes, passed 24 added point probes, and passed 24 pilot-sized hull contacts with clear starts. All 11 installed package files match their recorded hashes. GPU pop-in and complete player movement remain unverified. The package is `output/PhaseRunner.Preview-0.1.20.zip`; the earlier 0.1.19 archive is retained.



Build stages: `spatial_preview_meshes.py` (bundled NumPy runtime), `prepare_portal_collision.py`, `extend_prop_collision.py`, `package_northstar.py`, and `finalize_textured_preview.py`. Physics decoding follows the pinned RSX IRPS and model BVH layouts. Evidence is in the packaged build/runtime JSON and `logs/unit-0.1.20.log`, `logs/preview-0.1.20-final.log`.



## Northstar preview 0.1.21 - 3 October 2026

**Withdrawn after client feedback:** this build caused hall of mirrors and a rendering crash during grappling. Its server and file checks did not cover the missing native index padding described below.

Four native TF2 outdoor cells replace the single-cell prototype. Eight directed open connections and sixteen exterior sky portals are generated independently of Apex visibility. A roots-first AABB forest follows native Homestead/Colony. Geometry crossing partitions is referenced in both cells. No opaque occlusion masks are added. All 22,171 meshes remain reachable through 23,947 references. This conservative layout still needs a GPU check.

22,088 spatial mesh sections now declare their actual local vertex ranges. Comparison against every mesh in Homestead and Colony confirms the encoding: minimum local vertex followed by maximum-minus-minimum. The 892 shared material sorts and all rendered triangles and attributes are retained.

Original IRPS physics adds 165 railing placements and 67 other structural placements. Each tube gains 64 additional walkable surface prisms. Exactly 424 brush slots are reclaimed from the previous world collision by merging touching/overlapping boxes with identical cross sections (346 entries), and removing other solids whose complete bounds lie inside a solid box (78 entries). No gap is bridged and the previous solid union is preserved within native float precision. Brush capacity still limits complete wall, tube and prop coverage.

All active BSP material names and dimensions resolve to packaged material headers. The central ring materials have recovered texture handles. This does not prove GPU rendering or identify the reported invisible props without location information. The RPak, STBSP and lighting are unchanged. Original layered shaders, final lighting and spatial streaming remain incomplete.

64 automated checks pass. The final dedicated server loaded in 27.804 seconds, passed 72/72 point traces and 48/48 pilot hull contacts with clear starts. These probes cover selected contacts, not complete movement. Runtime evidence is in the packaged runtime-validation.json and logs/preview-0.1.21-final.log; unit evidence is logs/unit-0.1.21.log.

Build stages: extend_structure_collision.py, native_preview_cells.py, audit_preview_material_bindings.py, package_northstar.py and finalize_textured_preview.py. The earlier 0.1.20 artifacts and archive remain available for regression comparison.


## Northstar preview 0.1.22 - client regression repair

The 0.1.21 client minidump exposes an invalid render index at engine.dll+0xae8d3. Mesh 18176 contains 313 real triangles but its runtime descriptor processes 314. With no stored padding, that additional triangle reads the next mesh's indices (926, 919, 932) against a first vertex of 2028, yielding negative relative indices (-1102, -1109, -1096). The grapple timing does not show that grapple collision itself was the crashing subsystem.

Every odd-sized mesh in native Homestead and Colony stores three copies of the last vertex after its real triangles, without counting this degenerate padding in the source triangle count. The repaired preview follows that pattern for 10,907 odd meshes. All mesh index starts align to six indices, and all pairwise reads remain in the declared vertex range. The original 7,010,627 real triangles, vertex attributes, material sorts and textures are retained.

The experimental four-cell portal graph and narrowed vertex ranges are withdrawn. The repair restores the earlier 0.1.20 visibility and range metadata while keeping the 0.1.21 railing, structure and tube-floor collision. Original layered shaders, remaining pop-in and complete collision are still unfinished.

A native pair-padding validator now prevents the failed 0.1.21 BSP from being repackaged through that path. Six new regression checks include the negative-index reproducer, degenerate padding rejection, every native reference mesh and exact preservation of the repaired geometry/collision. The full 70-check suite passes. Dedicated runtime results are recorded separately; actual client rendering and a player grapple still require user verification.

Build: repair_preview_index_padding.py, package_northstar.py and finalize_textured_preview.py. Crash evidence: logs/client-0.1.21-crash.dmp, logs/client-0.1.21-crash-analysis.txt and logs/client-0.1.21-mesh-state.txt. Verification: logs/unit-0.1.22.log and packaged build-status.json/runtime-validation.json. Earlier archives remain available.
# Preview 0.1.23: collision edge repair

Installed as `PhaseRunner.Preview`; restart Northstar and load `map mp_phase_runner_preview`.

The previous collision consisted mostly of face planes, without the extra edge planes present in native Homestead brushes. Player-sized hull sweeps can therefore report contacts beside angled geometry. This build adds 750,803 native discard-marked edge planes to 58,518 existing brushes, retaining their original origins, bounds, face planes, side properties and texture vectors. Complex colliders that cannot be safely reconstructed remain unchanged. Missing prop/tube collision and coarse rock approximations are still unfinished.

Draw sections now declare exact local vertex spans while retaining the native odd-triangle padding. Apex arena start barrier visuals (108 triangles) are removed; their openings are visible without introducing door scripts. Nearby collision is not removed by a bounds guess. Uniform calibrated illumination replaces the spatial Coliseum lightmap images; this is temporary preview lighting, not a final directional bake. The map contains no Coliseum shadow meshes or menu entities. Its cell lookup assigns the same cell everywhere, so player out-of-bounds unloading has not been established as the cause of remaining pop-in.

Evidence is stored in `logs/unit-0.1.23.log`, `logs/surface-unit-0.1.23.log`, `logs/preview-0.1.23-final.log`, and the package's `runtime-validation.json`. The collision repair also includes eight engine clearance checks at positions incorrectly occupied by the earlier face-only hull expansion. GPU appearance, the reported ramp material/PBR issue, stray character shadows and complete player movement still need client verification.

## Northstar preview 0.1.30 - 4 October 2026

The user confirmed 0.1.29 renders all recovered props without pop-in. Its draw-budget repair is retained: the native world renderer has a 3,145,728-index capacity, and the former seven-million-triangle preview exceeded it. Both large tunnels now use unsimplified source LOD0 geometry; portal frames use unsimplified LOD1. Other restored props keep the confirmed settings.

Original world surface-property labels identify invisible pipe clip/end caps. The repair cuts 200 tool-material collision triangles only within oriented portal apertures, retaining their exterior portions. All 26 portal frames use exact full-detail visible metal triangles for collision instead of broader IRPS pieces; energy disks remain nonsolid. Original world/model physics records remain stored unchanged, with only those replaced shapes omitted from the active collision grid.

Two new 80-unit-wide metal walkways follow the pipe ring routes. Floor panels and native collision use exactly matching geometry. Their ramps clear smaller overlapping rings and decorative pipe fixtures and stay within a 35-degree gradient. These are new Titanfall traversal adaptations, rather than recovered Apex floors. Complete original tunnel meshes and physics remain present. The final build has 873,018 rendered triangles and uses 2,622,720 indices, leaving 16.63% capacity headroom.

All 18 focused regression checks pass. A fresh localhost dedicated test passes all 927 existing contact/clearance checks, plus both directions across 1,449 walkway segments and 1,449 supporting floor contacts. New detail, walkway appearance, off-center movement and grappling still require client verification. Evidence is in `logs/tunnel-0.1.30-validation.log`, `logs/tunnel-detail-unit.log`, `logs/tunnel-collision-unit.log`, `logs/tunnel-walkway-unit.log`, and the installed `runtime-validation.json`.

Build stages: `build_budget_preview.py` with `tunnel_detail=True`, `decode_collision.py` with `label_surfaces=True`, `audit_tunnel_surface_materials.py`, `repair_tunnel_passages.py`, `build_tunnel_walkways.py`, `package_northstar.py`, and `finalize_tunnel_release.py`. The working 0.1.29 archive is retained. Restart Northstar and load `map mp_phase_runner_preview`.

## Northstar preview 0.1.33 - lighting environment repair

Client feedback on the first static-light bake showed black surroundings, a
bright rectangle near the player, and pilot/Titan menu shadows. The decorative
sky dome was incorrectly included as an opaque ray blocker. The corrected bake
excludes its 3,968 triangles and restores sun/sky visibility to real map surfaces;
687,100 real surface samples regain sunlight. The sky artwork receives separate
constant illumination without sun-table entries.

Native Homestead, Colony and Coliseum menu/lighting entities were inspected.
The map now follows Coliseum's indexed gameplay/menu environments, remote menu
anchors and inline menu lighting volume. Exact native static shadow geometry
includes 869,050 real caster triangles in 107 meshes, with the sky excluded, so
the dynamic sun shadows can agree with the corrected static bake.

All 0.1.32 render geometry, recovered PBR materials, visibility, lightmap UVs,
collision, resident STBSP and both tunnel walkways are preserved. Seven focused
ray/shadow/preservation tests pass. A fresh isolated native server loads in
30.048 seconds and passes all 927 contact/clearance checks with no script errors.
Client lighting, menu shadows and performance remain unverified. Direct sun and
sampled sky lighting still lack indirect bounce, alpha-tested foliage shadows,
emissive baking and new reflection probes. See `LIGHTING.md` and the installed
runtime evidence for scope and native-format details.

Build: `prepare_environment_bake.py`, `bake_phase_lighting.cpp` with the optional
caster mask, `repair_environment_lighting.py`, `test_environment_lighting.py`,
`package_northstar.py`, `Run-LightingValidation.ps1`, and
`finalize_environment_release.py`. Evidence: `logs/environment-lighting-unit.log`,
`logs/environment-0.1.33-validation.log`, and `logs/environment-ground-lighting.json`.
The 0.1.30 and 0.1.32 rollback archives remain available.

## Northstar preview 0.1.34 - interior lighting and texture optimization

The user confirmed 0.1.33 outdoor lighting looks good. This follow-up adds 30
static native PBR point lights: 12 at recovered building fixture positions and
18 spaced along the two tunnel walkways. Local visibility is ray-baked against
the same static scene, covering 80,319 surface samples, and routed through the
native four-slot lightmap table. Original outdoor sun visibility and sky direction
data, geometry, visibility trees, collider records and walkways are unchanged.

Exact native shadow caster geometry is regrouped from 107 batches to 27, reducing
draw calls without dropping triangles. Exact-byte texture deduplication removes
136 repeated channels. All 567 remaining textures have complete resident mip
chains. Albedo and rock/terrain normal top levels remain byte-identical; other
auxiliary channels are capped at 1024. The texture RPak falls from about 886 MB
to 565 MB. Material names, shaders, Uber data and the STBSP catalog are retained.
This is not starpak-backed spatial streaming. See `INTERIOR_LIGHTING.md` for
native routing, optimization tradeoffs and the official mip-generation tool.

Seven focused ray/light-table/geometry/texture regression tests pass. A fresh
isolated native server loads in 30.938 seconds with no script errors and passes
all 927 contact/clearance checks. Interior brightness, actual point-light GPU
binding, PBR highlights, performance and improvement to the reported popping
still require client inspection. The popping's exact cause has not been proved.
The user-confirmed 0.1.33 lighting archive is retained for rollback.

Build tools: `optimize_preview_textures.py`, `prepare_interior_lights.py`,
`bake_interior_lighting.cpp`, `apply_interior_lighting.py`,
`test_interior_lighting.py`, `package_northstar.py`, `Run-LightingValidation.ps1`
and `finalize_interior_release.py`. Evidence is in `logs/interior-lighting-unit.log`,
`logs/interior-0.1.34-validation.log` and packaged runtime/optimization reports.

## Northstar preview 0.1.35 - native spatial visibility (withdrawn)

**Withdrawn after client testing:** the user reported sky culling and hall of
mirrors. The CPU regressions and dedicated load below did not validate client
rendering. Version 0.1.36 removes this portal graph and restores the confirmed
0.1.34 cell/portal records. The following notes are historical evidence.

The user confirmed 0.1.34 light levels and reported complete tunnel disappearance,
including walkways, with intermittent outdoor walls, fences and small rocks.
This candidate replaces its constant single-cell lookup with sixteen native cells
and 48 reciprocal directed open portals. Nearby references include the playable
camera portion of their owning cell, avoiding projected-silhouette rejection for
local geometry at particular view angles. No opaque doorway/tunnel occluder or
Apex visibility graph is added. Geometry crossing boundaries stays referenced in
both cells. Every one of the 4,561 draw meshes remains reachable through 7,435
references; the AABB forest needs at most 144 pending nodes.

Draw geometry, real mesh bounds, native index-pair padding, materials, lightmaps,
all lights, shadow geometry, collision records and both walkways are unchanged.
Only native visibility data and appended visibility planes change, with original
collision plane bytes retained. The renderer keeps 16.54% index-budget headroom.
The 0.1.34 RPak and resident-texture STBSP are hash-identical. Visibility cells do
not add texture streaming or prove a frame-rate improvement.

Seven regressions pass, including every tunnel-route eye position, horizontal
and vertical view support, independent mesh membership, far backdrop, portal
winding/reciprocity, boundary lookup, draw limits and whole-lump preservation.
A fresh localhost native server loads in 30.672 seconds, with all 927 existing
contact/clearance checks passing and no script errors. Client rendering remains
unverified. Preserve the complete 0.1.34 archive for rollback and test both pipes
plus outside walls/fences/rocks after restarting Northstar.

Build: `rebuild_local_visibility.py`, `test_local_visibility.py`,
`package_northstar.py`, `Run-LightingValidation.ps1` and
`finalize_local_visibility_release.py`. Detailed tradeoffs are in `VISIBILITY.md`;
evidence is in `logs/local-visibility-unit.log`,
`logs/local-visibility-0.1.35-validation.log` and packaged validation reports.

## Northstar preview 0.1.36 - portal-free render optimization

The sky culling and hall of mirrors reported in 0.1.35 caused that build to be
withdrawn. This release restores all 0.1.34 cell, portal and occlusion records
exactly. There are no new connected portals. All 4,561 meshes are referenced
once by a 255-node spatial tree. Sky object bounds contain the supported camera
domain; 384-unit local padding and route guards protect nearby tunnel geometry.
The real geometric bounds stay unchanged, and far objects remain local.

Compatible material-sort records drop from 4,561 to 337. Bit-identical vertices
are welded within each mesh, reducing vertex data from 115,238,376 to
106,530,512 bytes. Every mesh retains a contiguous vertex block and a CPU
clipping span no larger than before. All 873,018 triangles preserve exact
positions, normals, tangents, UVs, color, lighting, material bindings and winding.
The native paired-index padding retains 16.54% world draw-budget headroom.
These are measured data reductions; GPU draw-call count and FPS are unmeasured.

All other BSP payloads, including physics, full position/normal buffers,
lightmaps, interior lights and shadow geometry, are preserved. PBR textures,
resident-texture STBSP and both tunnel walkways retain the 0.1.34 data.
Seven focused regressions pass, including independent comparison of every
rendered triangle corner and every untouched lump. A fresh native server loads
in 21.513 seconds and passes all 927 collision checks without script errors.
Client sky, tunnels, outdoor popping and performance still need verification.

Build: `optimize_portalfree_render.py`, `test_portalfree_optimization.py`,
`package_northstar.py`, `Run-LightingValidation.ps1` and
`finalize_portalfree_release.py`. Evidence is in
`logs/portalfree-optimization-unit.log`,
`logs/portalfree-0.1.36-validation.log`, `VISIBILITY.md` and the packaged reports.
