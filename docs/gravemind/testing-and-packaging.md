---
id: gm_01m4nfwwnxq30rgpr6w7490ka2
title: Native Northstar map testing and clean releases
description: Isolated native harness, screenshots, collision and reload validation, clean packages and rollback
tags:
  - titanfall-2
  - apex-legends
  - map-conversion
  - testing
  - harness
  - northstar
  - packaging
project: apex-to-titanfall-2
status: verified
created: 2026-10-11T12:44:41.021Z
updated: 2026-10-28T06:32:25.554Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 7
---
# Native Northstar map testing and clean releases

The project has an opt-in Squirrel/Python harness for launch, map load, camera
positioning, collision queries, screenshots and lifecycle checks. It is a testing
mod, not part of the released map and not a DLL plugin.

## Harness architecture

The controller listens on loopback `127.0.0.1:39131`; UI, client and server script
contexts poll it independently through Northstar HTTP with `-allowlocalhttp`.
Per-session bearer authentication protects the local queue. Commands are delivered
and acknowledged by the appropriate context; expired queued commands are cancelled.
No harness credentials or raw session files belong in knowledge-base entries.

A separate `R2MapHarness` profile stages current packages, core Northstar mods
and the harness. Normal `R2Northstar` remains separate. Replace owned staging
directories rather than merging: stale BSPs previously shadowed the new package.
Only stop the game process owned by the controller.

Readiness needs fresh UI/client/server heartbeats at the requested level and a
new generation ID after load. `load` does not restage modified runtime bytes;
stop/relaunch after a package change. A successful command can otherwise act on
a lobby reached after match end, so capture and trace metadata must verify map.

## Repeatable checks

Camera origins are eye positions, player origins are feet, and angles are native
pitch/yaw/roll degrees. Camera mode hides HUD/weapon. Freezing input does not stop
gravity; it is not a guarantee the player remains at the requested coordinates.

Routes record map, mode, labeled eye origins, angles, FOV and settling time. Native
screenshots are awaited as new files, dimension-checked and converted to previews.
Adjacent metadata includes active map, camera, time and SHA-256. Do not substitute
an unrelated desktop image when capture fails. Visual review remains necessary.

Useful sequences include cold launch, both team starts, ground/up/down views,
interior camera sweeps, selected line traces, full pilot/Titan hull probes,
menu-stage transitions, forced postmatch, stock-map load and converted-map reload.
Line contacts do not prove a full route is traversable. Start-solid and missing
ground support must be explicit failures. Export logs with credentials redacted.

The owned launch also depends on a working EA/Origin session. A verified
“Lost connection to Origin” error blocked one screenshot run; reconnecting EA
allowed the final reload checks to complete. Distinguish authentication/environment
failures from malformed maps instead of repeatedly changing geometry.

Switching out of a Titan-only mode previously triggered a stock Titan-selection
UI assertion. The harness uses a fresh process for such transitions and retains
the failed run as evidence; it does not patch stock gameplay/UI to hide it.

## Structural checks before launch

Validate finite coordinates, version/stride, all references/ranges, absolute
game-lump relocation, material dependencies and slots, opaque/alpha partitions,
reachable mesh references, native index padding, collision contents/ownership/grid,
signed bounding extents, chart overlap/page binding, light/probe mappings, safety
triggers and spawn marker links. Keep old byte/face comparisons for targeted
repairs where full rebuilding is unnecessary.

## Packaging and rollback

A clean player ZIP contains the runtime Northstar directory (`mod.json`, `mod/`,
`paks/`), short install README and optional actual game screenshot. Development
scripts, input archives, ledgers, test logs and credentials remain outside it.
Server and clients need matching versions; disable old copies and restart.

Hash every source runtime file and verify archive membership and extracted bytes.
Stage and hash installation before replacing the owned mod; retain the previous
version for rollback. Separate map packages must not overwrite each other.
Snapshot edits atomically; hardlinked backups require detach-before-write or an
in-place write can silently alter the backup.

Drop-Off 0.6.0's clean ZIP has 22 members: twenty runtime files, README and native
screenshot. Its installed 0.5.0 was retained. Final single-client validation is
documented separately from binary checks; multiplayer performance and balance
remain unestablished.

## Sources

`test-harness/README.md`, `test-harness/harness.py`, `test-harness/test_harness.py`,
`Run-MapHarness.ps1`, `verify_composite_local_runtime.py`,
`package_player_mods.py`, `install_arena_repair_releases.py`, and map validation
receipts. The HTTP API reference used by the harness is
https://docs.northstar.tf/Modding/reference/northstar/httprequests/.

## Five-map UI atlas hotfix and expanded comparisons — 14 October 2026

The current hotfix versions are Phase Runner 1.6.1, Drop-Off 0.10.1, Firing Range/Party Crasher/Overflow 0.3.1, with shared ApexMaps.UI 0.1.0. A five-map owned installation reproduced the native dialog `Tried to load more than 20 assets of type "UI image atlas".` Isolated-map passes did not detect this shared pool failure. Native Engine Error dialogs can leave the process alive without a Northstar crash-log entry; the harness now checks only its owned game's Engine Error window and redacts its token before reporting the diagnostic.

The accepted fix consolidates fifteen loading/lobby image aliases and five minimaps into one UI atlas, rather than relying on map filters to unload separate atlases. The individual loading packs keep their native material states, texture bindings and uberbuffers but no longer own uimg assets. Standalone minimap RPaks leave the runtime packages. Every clean map ZIP includes the same three-file ApexMaps.UI companion. Replace the old map folder rather than merging, move backups outside mods, update every installed conversion, and enable the shared companion once. Obsolete atlas files must not remain in the live mod folder.

The final single-client process loaded all five maps, captured 25 area views, returned through postmatch to mp_lobby, loaded stock mp_coliseum and reloaded Firing Range with no script errors or native crash entries. A separate cold launch directly into mp_lobby also passed with all five maps and the companion installed. These checks do not establish multiplayer load, AI or stable frame rates. The previous repeated-mode-change/loadout failures remain separate and unresolved.

Three expanded routes add five locations each to Firing Range, Party Crasher and Overflow: 23 matched R5R/Northstar pairs in total, including the eight earlier viewpoints. Active maps, camera positions, equal resolution and capture hashes are checked. Site snapshot 2026-10-14-ui-atlas-survey retains earlier snapshots unchanged. New views expose omitted Party Crasher banners/character advertisements and hologram differences, plus incomplete water/lava/atmospheric parity; they are recorded observations, not claims that this UI fix repaired those features.

Evidence in the private conversion repo: docs/candidates/ui-atlas-lifetime-2026-10-14.md, docs/conversion/ui-atlas-lifetime-validation.json, shared-map-ui.json, build_shared_map_ui.py, map_pack_lifetime.py, capture_combined_map_regression.py, verify_combined_ui_lifecycle.py, publish_ui_atlas_surveys.py and site/ui-atlas-survey-findings.json.

## Toolchain pitfalls found in the Firing Range 0.4.0 build — 15 October 2026

- **Game-lump offsets during compaction.** Lump 0x23's directory stores *absolute file offsets*. Older `compact_preview_bsp.compact` relocated them only when copying the lump from the source file. A caller that passed all 128 lumps as replacements (as the Firing Range surface patch does) got the payload written verbatim at a new offset, leaving `prps` pointing at stale data. This was caught before shipping, and installed builds were checked and are fine. The compactor now relocates in both paths and refuses edited game-lump replacements. Check: every game-lump entry `[ptr, ptr+len)` must lie inside the lump.
- **RePak texture order.** If a material appears in `build.json` before its textures, RePak auto-adds the textures with streaming *enabled*. Without a starpak, it fails with "Attempted to write mandatory streaming asset without a stream file handle". Declare every `txtr` before any `matl`.
- **Light-baker DLLs.** The retained MinGW bakers (`tools/bake_interior_lighting.exe` etc.) are dynamically linked. Launched from Git Bash, they pick up Git's `mingw64/bin/libstdc++-6.dll` and exit with 0xC0000139. `recover_composite_details.append` now puts `C:/ProgramData/mingw64/mingw64/bin` first on PATH for them. The newer `bake_arena_*.exe` tools are static.
- **Route ordering.** The first shot of a Northstar route can land on the pre-match spawn/loadout overlay. Put a non-critical view first or retake it.
- **Collision for restored props.** For props omitted from the source, a "world/source-owned" collision label is a default. Verify restored visible surfaces with native vertical traces. Firing Range's restored stairs had no collider until their source IRPS mesh was appended.

## Five-map site image refresh — 18 October 2026

`refresh_site_captures.py` refreshes every distinct published camera against the current accepted mod, with one cold owned Northstar session per map. Snapshot `2026-10-18-release-refresh` contains 53 matched views: Drop-Off 0.10.1 (12), Phase Runner 1.7.2 (11), Overflow 0.4.1 (8), Party Crasher 0.6.4 (15), and Firing Range 0.5.1 (7). Party Crasher combines the prior arena/street and roof/edge surveys and adds the Northstar billboard. Shared ApexMaps.UI is 0.1.1.

All 53 native images were recaptured. Existing hash-verified matching Apex images retain their original capture dates; the new screen camera has a fresh R5R reference. Do not relabel reused source photos as newly captured. Mounted BSP/STBSP/RPak hashes, active map, actual camera pose, living camera player and paired image dimensions are verified. Native photography removes boundary/hurt triggers only in the owned runtime for exterior views, never from map files. These are visual surveys, not fresh gameplay or multiplayer certification. Wait for the game-mode introduction before the first photograph; menu closing alone does not clear its banner.

A discarded new-source attempt encountered an invalid `ContainsPoint` error after destroying source safety entities. A fresh R5R launch with those entities intact captured the screen successfully. Runtime trigger destruction is not safe for every source map script lifecycle.

`verify_site_refresh.py` checks all 362 exported image hashes/dimensions, the 53 current native camera records, absence of private metadata, equality of embedded HTML/catalogue data, and byte-for-byte logical equality of all 26 historical snapshot records. Old snapshots remain available while the five map cards and defaults select the new snapshot. Evidence: `docs/site-image-refresh-2026-10-18.md` and the adjacent JSON validation receipts; reusable routes are `r5-harness/routes/*-release-survey.json`.

## Release consolidation — 25 October 2026

The [October beta](https://github.com/taskinoz/apex-to-titanfall-2/releases/tag/maps-beta-2026-10-25) publishes the existing accepted ZIPs for Phase Runner 1.7.2, Drop-Off 0.10.1, Firing Range 0.5.1, Party Crasher 0.6.4, Overflow 0.4.1, Thermal Station 0.1.2 and Thunderdome 0.1.1, with separate ApexMaps.UI 0.2.1. All eight match their accepted distribution receipts and GitHub's server-computed SHA-256. Regenerated working loading packs differ from some older ZIPs; the cleanup preserves accepted distribution bytes rather than rebuilding under an existing version. No fresh native gameplay certification is implied.

The clean local set is `output/releases/maps-beta-2026-10-25/`. Same-volume hardlinks preserve compatible top-level output paths without allocating another copy. Published ZIPs are immutable; future builders must replace files atomically and use new versions instead of writing through hardlinks.

A separate authenticated draft, tag `build-archive-2026-10-25`, backs up 94 historical ZIPs: 44.0124 GiB of originals represented by 22.0880 GiB of complete ZIPs and Zstandard differential objects. Every delta was decoded and checked against the original ZIP SHA-256 before upload; all 94 remote objects and three metadata/helper assets passed server-hash verification. Eight log-bearing or oversized-report bundles needing review remain local in `output/release-cleanup-2026-10-25/retained-private/`. Do not publish development bundles solely on their filenames.

`archival-objects.json` records original hashes, object hashes and reference chains; `archive-manifest.json` preserves original filenames and sizes. `restore_release_archive.py` uses authenticated GitHub CLI and installed Zstandard, checks all downloaded and reconstructed bytes, keeps temporary storage bounded by removing intermediates, and preserves existing destinations. A real GitHub restore of Drop-Off 0.8.0 through 0.9.0 and the local current 0.10.1 anchor matched its original SHA-256. Preserve both release tags and all referenced objects; a later cleanup must rebase and verify dependencies before pruning them.

`manage_release_archives.py` restricts retirement to inventoried ZIPs in two explicit resolved distribution directories. It checks the entire remote dependency graph, then hashes each unchanged original immediately before individual deletion. A flushed per-file journal precedes removal, followed by a receipt. Current ZIPs, runtime mods, source assets, build trees and excluded history are protected. No recursive directory deletion is used for release cleanup. Migration receipts stay in ignored `output/release-cleanup-2026-10-25/`; do not overwrite a completed migration's inventory.

Fifteen disposable-file tests cover changed/missing proof, path traversal, interruption recovery, malformed checksum sidecars, incomplete uploads and actual two-delta restoration with targets larger than their references. A decoder bug initially used a bare `-M4096` as though it were MiB; the CLI interprets that number as bytes. The helpers now use `--long=31`, verified on the growing-file fixture and the real 776 MiB archive. Failed uploads may leave `starter` assets: only still-incomplete, digest-less objects owned by that upload are removed before retry; completed backups are preserved. Cancel queued futures on a failure so a thread-pool shutdown does not silently continue an entire batch.

Evidence and recovery instructions: `docs/release-management.md`, `manage_release_archives.py`, `archive_release_history.py`, `restore_release_archive.py`, and the private upload, recovery and retirement receipts. Binary distributions remain in GitHub Releases, outside source Git history and Git LFS. Upstream reference: [Zstandard patching guide](https://github.com/facebook/zstd/wiki/Zstandard-as-a-patching-engine).

## Anniversary five-map validation — 28 October 2026

The original five accepted runtime versions (Phase Runner 1.7.2, Drop-Off 0.10.1, Firing Range 0.5.1, Party Crasher 0.6.4 and Overflow 0.4.1) were extracted from the immutable October beta ZIPs rather than rebuilt from mutable working directories. Provenance now covers every runtime file, including scripts and translations, and the mounted files matched those archives. ApexMaps.UI remains 0.2.1, with one atlas and support for the two additional maps preserved.

The dedicated anniversary profile used the official Northstar 1.31.14 launcher, DLL and core mods; the normal installation/profile were preserved. A combined all-five-installed session passed PS spawn/hull/support checks, both team start selections, weapon fire, native captures, normal postmatch lobby returns, a stock Coliseum visit and converted-map reload. FFA checks and postmatch returns passed on every map. Phase Runner also passed CTF flag, Hardpoint net-objective and Fastball three-panel setup checks. These are one-client smoke checks, not multiplayer load, scoring, balance, dedicated-server or AI certification.

Overflow completed ten alternating PS/FFA cycles, each with stock-map and Overflow reloads, without logged script errors or native crashes. The first cycle used the existing process; the next nine launched fresh processes. A cycle is recorded only after its reload succeeds. This bounded sample does not establish the root cause of the earlier intermittent 1.31.13 crash. Northstar 1.31.14's upstream FFA RUI stack fix is relevant maintenance, not proof of causality. EA restart and the isolated runtime update happened together during startup recovery; do not credit either alone.

Fresh overviews of all five maps were reviewed with live map/camera metadata, living camera players, intact safety entities and expected geometry/materials/UI. Earlier spawn photos are not the visual acceptance set. No pink shader fallback or whole-map disappearance appeared in the reviewed overviews; source scenery, shader/FX and Apex gameplay omissions remain. Structural audits passed native v37 headers, index-pair padding, reachable visibility bounds, world capacity and RPak ordering. Index use is 97.79%, 97.06%, 97.63%, 96.70% and 94.31% respectively; static batch runs are 495, 379, 198, 468 and 250 against the audited 2,048-run submission limit. Dynamic-light splits and other rendering paths still need headroom.

Forty-one offline tests passed: 21 geometry/capacity/support, four binary adapters, 12 harness and four disposable archive-provenance tests. Python 3.14 is needed for stdlib compression.zstd adapters; the project's compiled geometry dependencies use Python 3.12. Run those groups with their matching interpreters. A further harness regression rejects switching runtimes through an older controller that lacks runtime metadata. The harness now accepts explicit read-only runtime and same-game-directory alternate launcher paths; configuration changes require stopping its controller first. Four provenance tests reject changed downloads, changed staged scripts and archive traversal, and cover translation/script hashing.

The r2-model-compiler v0.5.0 supplied static-box example compiled with zero warnings to a 5,550-byte native MDL. No map model was rebuilt with it. Moving baked scenery to static props still needs native material binding, correct game-lump/visibility namespaces, lighting, collision and native tests. Evidence and packaging tools: docs/anniversary-2026.md, docs/anniversary-2026-validation.json, docs/toolchain/r2-model-compiler-2026-10-28.md, prepare_anniversary_release.py, validate_anniversary_native.py, package_anniversary_rc.py and report_anniversary_release.py. Anniversary packaging retains runtime mod versions, uses distinct RC filenames and excludes harnesses, tools, raw logs and source game archives.
