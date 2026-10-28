# Northstar map test harness

Launch a local game, switch maps, reproduce camera views and save screenshots from the game itself. The controller installs `MapTest.Harness` into a separate `R2MapHarness` profile. Your normal `R2Northstar` profile and Phase Runner map build are preserved.

From PowerShell in this project:

```powershell
.\Run-MapHarness.ps1 start
.\Run-MapHarness.ps1 route test-harness/routes/phase-runner.json
.\Run-MapHarness.ps1 stop
```

`start` stages the current map package and launches `mp_phase_runner`. `route` reloads the map and captures six repeatable views. `stop` saves the game log and closes only the game process launched by this controller, then stops the controller.

## Individual checks

```powershell
.\Run-MapHarness.ps1 status
.\Run-MapHarness.ps1 load mp_coliseum
.\Run-MapHarness.ps1 load mp_phase_runner
.\Run-MapHarness.ps1 camera 180 -1200 -1000 --angles -22 90 0 --fov 90
.\Run-MapHarness.ps1 capture center-trees
.\Run-MapHarness.ps1 player 0 -2681.6 -1280 --angles 0 90 0
.\Run-MapHarness.ps1 trace 826.2 34.7 -1150 --end 826.2 34.7 -1400
.\Run-MapHarness.ps1 camera-clear
.\Run-MapHarness.ps1 console "cl_showpos 1"
```

Camera positions are absolute eye positions; player positions are foot positions. Angles are pitch, yaw and roll in degrees. Camera mode moves the protected player 64 units below the camera in noclip, so streaming and PVS follow the inspected area. It checks the native camera position and angles before capture. The weapon is hidden, but some game HUD elements can remain. `camera-clear` restores the player's view and walking controls. Ordinary player placement grants invulnerability and freezes controls by default; add `--unfreeze` to allow movement. Gravity still applies to ordinary placement. `trace` checks brush collision, including this conversion's generated brush colliders; it is not a full movement or dynamic-prop collision test.

`stop-game` closes the owned game while keeping the controller running. `launch mp_phase_runner` starts another game through that controller. Use `load` for an already running game. Stop and start again to stage a changed package.

## Outputs

Each controller session creates `test-harness/output/<timestamp>/`:

- `screenshots/`: original native capture, PNG preview and adjacent JSON containing map, camera position, angles, dimensions, capture time and SHA-256.
- `events.jsonl`: commands and their game acknowledgements.
- `game.log`: latest game log, exported after routes and stops with the harness token redacted.
- `route-result.json`: paths and metadata for a completed route.

Screenshot capture waits for a new native screenshot file and checks its dimensions. It fails if the game produces no image. It does not substitute a desktop screenshot. Readiness requires fresh UI, client and server heartbeats for the requested map; reloads require a new generation ID so an old map cannot satisfy the check.

## Custom routes and installations

Routes use this format; the included Phase Runner route has overview, trees, buildings and tunnel views:

```json
{
  "map": "mp_phase_runner",
  "mode": "tdm",
  "shots": [
    {"name": "overview", "origin": [0, -5000, 1400],
     "angles": [28, 90, 0], "fov": 90, "settle": 3}
  ]
}
```

Alternate installation or package:

```powershell
.\Run-MapHarness.ps1 start --game "D:/Games/Titanfall2" --package "C:/path/to/PhaseRunner.Preview" --map mp_phase_runner --width 1280 --height 720
```

The game directory must contain `NorthstarLauncher.exe` and a working `R2Northstar` installation with the three core Northstar mods. The default Python runtime is the locally bundled Python; the wrapper falls back to `python` on PATH. Pillow is required for PNG conversion. Map names must be raw `mp_...` names available in that installation. A missing map or failed connection results in a timeout/error rather than a successful test.

For a reproducible runtime comparison, `start` also accepts `--runtime` (a
read-only directory containing `Northstar.dll` and the three core mods) and
`--launcher` (an alternate launcher executable directly inside the game
directory). They are copied into/launched with the dedicated test profile;
the normal Northstar installation is preserved. Stop the controller before
changing either selection. Match the launcher and DLL to the same official
release and record their hashes with the test evidence. These options do not
download or update Northstar automatically.

Repeat `--extra-package <directory>` to stage up to eight additional packages.
This tests combined installations, including the native 20-asset UI image atlas
limit. Reserved `MapTest.Extra` through `MapTest.Extra8` folders are replaced on
each owned launch so old maps cannot shadow a new test.
Run `build_shared_map_ui.py` after staging presentation/minimap candidates, then
`map_pack_lifetime.py audit` before packaging. The five maps share the one
`ApexMaps.UI` companion. Standalone minimap atlases and atlases embedded in
presentation packs are rejected. World packs retain their native
`mp_coliseum.rpak` dependency order; loading them before it gives fallback materials.
`capture_combined_map_regression.py <package> --expanded` records the installed
loading contracts and native images with all five maps plus the UI companion present. Capture checks are not a
multiplayer, performance or AI certification.

## How control works

The Python controller listens on `127.0.0.1:39131`. The Northstar Squirrel mod polls it independently from UI, client and server scripts. Commands are authenticated with a random per-session bearer token, delivered once and acknowledged by the appropriate script context. Timed-out queued commands are cancelled. There is no DLL plugin to build.

The harness uses Northstar's [HTTP API](https://docs.northstar.tf/Modding/reference/northstar/httprequests/), enabled with `-allowlocalhttp`, and native game commands/camera entities. The game server binds to localhost and server listing is disabled. The session files contain the local control token: keep `output/` private and uncommitted. The HTTP API permits game console commands, not operating-system shell commands.

For programmatic use, import `Controller` from `harness.py`; its `load`, `camera`, `capture`, `command`, `wait_map` and `export_logs` methods are the same operations used by the CLI. This is a capture and diagnostic harness; screenshots still need visual review to establish whether materials, lighting or geometry look correct.

Run controller checks:

```powershell
python -m unittest discover -s test-harness -v
```
