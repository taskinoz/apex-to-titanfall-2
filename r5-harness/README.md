# R5Reloaded map harness

Controls the installed R5R SDK locally, loads original Apex maps, places a fixed
camera, takes native game screenshots and compares them with Northstar ports.
No desktop screenshots or synthetic renders are substituted for game captures.

## Quick start

Run from the conversion workspace in PowerShell:

```powershell
./Run-R5Harness.ps1 launch mp_rr_arena_composite
./Run-R5Harness.ps1 status
./Run-R5Harness.ps1 camera 0 2200 900 --angles 22 90 0 --fov 90
./Run-R5Harness.ps1 capture court-overview
./Run-R5Harness.ps1 route r5-harness/routes/drop-off.json
./Run-R5Harness.ps1 load mp_rr_arena_phase_runner
./Run-R5Harness.ps1 route r5-harness/routes/phase-runner.json
./Run-R5Harness.ps1 logs
./Run-R5Harness.ps1 stop
```

The default source is `D:/Games/R5Reloaded/R5R Library/LIVE`; the harness creates
`D:/Games/R5Reloaded/R5R Library/MapHarness`. Override `--source` and `--profile`
on `launch` for another installation. Both must be separate directories. An
existing directory without the ownership marker is never modified. Stop the
owned game before staging changes. `load` reloads a map; `launch` stages scripts.

The helper is compiled through the copied `scripts.rson` and provides functions
in the server/client VMs. The normal installation's scripts and configuration
are not edited. Bulk asset directories use hardlinks on the same volume to
avoid duplicating approximately 63 GB. Treat linked assets as immutable inputs;
the harness unlinks destinations before copying/staging anything. Cross-volume
staging copies the assets and therefore requires the additional disk space.

The SDK's existing mods are copied because the installed scripts/playlists may
depend on them. This is an offline development session using `dev_default`, not
a public server. It listens for control on IPv6 loopback TCP port 37042. The
Northstar harness uses a separate profile and ports.
The copied development playlist has a two-player cap for these local tests,
and the copied console config disables the local network processing time budget.
Phase Runner initially disconnected with a native network overflow under the
stock 120-player development setup; it stayed connected with these settings.
This does not establish which change alone resolves that issue, or an engine
player/map limit. The normal playlist is unchanged.

## Paired comparisons

With R5R running, capture a paired route:

```powershell
./Run-R5Harness.ps1 compare r5-harness/routes/drop-off.json --output r5-harness/output/drop-off-comparison
```

The comparison command loads both maps, captures each route in both engines,
and writes `index.html`, paired PNGs and `comparison.json`. The gallery shows
images side by side and has an adjustable overlay. By default it captures R5R,
stops that owned process, then launches Northstar with both current map packages
if its controller is unavailable. An existing Northstar controller keeps its
configured packages. This avoids keeping both games in memory. `--simultaneous`
keeps R5R running. Both engines must have equal screenshot resolution (the R5R
launch requests 1280 × 720). The normal game installations are preserved.
If capture fails, repeat `compare` with `--resume` and the same output folder.
Each completed source view is saved immediately. Resume checks the route, map,
camera and source PNG hashes before using a saved prefix. For an incomplete
source route, launch the isolated R5R game again first; resume captures its
remaining views. A complete source cache needs no running R5R game and captures
Northstar again. Original capture metadata and images survive a later failure.

Route positions use **Titanfall world coordinates**. `source_offset` maps these
to the Apex world: Phase Runner adds `[26000,19000,0]`; Drop-Off adds `[0,0,0]`.
Angles are `[pitch,yaw,roll]` in degrees. Positions are camera/eye positions,
not player feet. FOV and angles are applied equally to both games. R5R also
moves the server player below the camera so streaming follows the capture
location. Camera routes inspect visuals; they do not prove gameplay collision,
pathfinding or performance. Captures include camera, map, timestamp, VM state,
session generation, dimensions and SHA-256 metadata.

Different materials, tonemapping, weapons and HUDs are expected between engines.
Use the overlays to inspect missing objects and placement, not as pixel-exact
rendering assertions. Texture settling time is configurable per route shot.

## Control and diagnostics

`console "<command>"` submits one native console command; `camera` controls the
client camera; `stop` only terminates the recorded game process if its creation
timestamp still matches. Map readiness requires fresh acknowledgements from
both VMs. Reloads require different VM instances, including same-map reloads.
Commands carry random tickets so unrelated console logs cannot satisfy them.
The controller waits for native full signon before accessing script VMs. Script
acknowledgements can arrive through RCON or the SDK's native `script.log`; some
installed SDK builds do not echo script prints through remote console. Partial
network frames survive polling timeouts, and response sequence numbers are
checked. Camera mode puts the local player in noclip so gravity does not move
the streaming viewpoint away from the fixed capture location.

First-run legal agreements require the user's own decision. The harness does
not accept them automatically. Once accepted, it clears gameplay message/menu
panels before captures. Restore normal movement by reloading the map.
`camera-clear` clears the fixed camera and restores walking without reloading.

The controller implements the installed **R5R v2.6.52** console envelope and
8-byte network header directly. This version has a nested sequence/nonce header
and stores the message in envelope field 4; the older upstream schema stores
it in field 3. The exercised layout is saved in `netcon-v2.6.proto`.
Frames are unencrypted only on loopback; authentication uses
a random session password. The engine loads its own RCON config after command
line options, so the isolated copy of that config retains the harness settings.
`output/session.json` and the isolated RCON config are private runtime state.
Do not distribute them. `logs` exports redacted logs; raw `process.log` is private.

If launch does not become ready, inspect the exported `game.log` for script
compiler, missing pak, playlist and signon errors. The native game must render
successfully to take screenshots. The controller does not force-close unrelated
games or EA sessions. Installed SDK versions with a different netcon protocol
need an adapter; do not assume every R5R release is interchangeable.

Run controller tests:

```powershell
python -m unittest discover -s r5-harness -p test_harness.py -v
```

Protocol background: local pinned `tools/r5sdk/src/resource/protobuf/netcon.proto`
and `src/engine/server/sv_rcon.cpp` (retrieve sparse files with `git show`). The
pinned June 2025 envelope is not wire-compatible with the installed v2.6.52.

## Verified captures

On 12 October 2026, both original maps and their Northstar ports completed three
matched camera views each, producing twelve native 1280 × 720 screenshots.
R5R same-map reload was also exercised with fresh server/client VM instances.
All 22 controller tests passed; the final Northstar log contained no script
errors. Both owned test games were closed afterward.

- [Drop-Off gallery](output/drop-off-comparison/index.html)
- [Phase Runner gallery](output/phase-runner-comparison/index.html)

These galleries remain local ignored outputs. They compare the current map
packages without modifying the release distributions.

The wider 12 October survey adds eight areas per map, producing 12 Drop-Off and
11 Phase Runner pairs. Both native cameras and the Northstar streaming player
positions were verified against the routes. There are 31 passing controller
checks after the camera-follow and partial-source-cache changes. One western
tunnel source view remains black in R5R at both tested heights; it is explicitly
marked as inconclusive. Two raised tunnel rechecks are integrated into the final
survey, while first-pass manifests and original native captures are retained.
See [the reviewed area survey](../docs/area-survey-2026-10-12.md) and choose
**Area survey** in [the portable site](../site/dist/index.html).
