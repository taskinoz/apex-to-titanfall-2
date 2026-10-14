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
updated: 2026-10-14T02:32:17.084Z
created_by: agent:Codex
updated_by: agent:Claude
revision: 2
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
