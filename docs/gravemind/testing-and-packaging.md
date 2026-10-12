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
