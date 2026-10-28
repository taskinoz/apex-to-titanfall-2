# Original five maps — anniversary release candidate

The [anniversary RC1 downloads](https://github.com/taskinoz/apex-to-titanfall-2/releases/tag/anniversary-2026-rc1)
contain the original five maps and shared UI companion. The
[public validation receipt](anniversary-2026-validation.json) records the fresh
single-client checks and exact package/runtime hashes. These remain release
candidates, with the limitations below.

The anniversary set is Phase Runner, Drop-Off, Firing Range, Party Crasher and
Overflow, with the separate ApexMaps.UI companion. Thermal Station and
Thunderdome remain available in the October beta but are outside this release's
five-map validation scope.

| Map | Mod version | Console map | Native world indices | Static batch runs |
| --- | --- | --- | ---: | ---: |
| Phase Runner | 1.7.2 | `mp_phase_runner` | 3,076,086 / 3,145,728 (97.79%) | 495 |
| Drop-Off | 0.10.1 | `mp_arena_composite` | 3,053,136 / 3,145,728 (97.06%) | 379 |
| Firing Range | 0.5.1 | `mp_apex_firing_range` | 3,071,154 / 3,145,728 (97.63%) | 198 |
| Party Crasher | 0.6.4 | `mp_party_crasher` | 3,041,970 / 3,145,728 (96.70%) | 468 |
| Overflow | 0.4.1 | `mp_overflow` | 2,966,730 / 3,145,728 (94.31%) | 250 |

Static batch capacity on the audited native world submission path is 2,048;
dynamic light masks may split batches further. These figures describe world
rendering, not a general object/entity count or a guarantee of AI headroom.
Maps near the index ceiling should not receive more baked scenery without a
new budget audit. Native model rendering has a separate path and constraints.

## Candidate provenance

Runtime bytes are extracted from the immutable, hash-verified
[October beta](https://github.com/taskinoz/apex-to-titanfall-2/releases/tag/maps-beta-2026-10-25),
not regenerated from mutable working build directories. No map geometry,
materials, collision, safety volumes or gameplay scripts change in RC1.
Mod versions therefore remain unchanged. Anniversary ZIP filenames distinguish
the updated packaging/readmes from the older archives.

`prepare_anniversary_release.py stage` checks the accepted archive SHA-256,
extracts safely into ignored `output/anniversary-2026/baseline/`, compares every
runtime file with its archive member and records hashes. `audit` checks native
v37 headers, pairwise index padding, reachable visibility references and bounds,
world capacity, RPak shader ordering and the single shared UI atlas. It does not
replace the earlier detailed collision/lighting checks or prove every area is
physically traversable.

The test profile uses the official
[Northstar 1.31.14](https://github.com/R2Northstar/Northstar/releases/tag/v1.31.14)
launcher, Northstar.dll and core mods, separate from the normal installation.
The downloaded release ZIP SHA-256 is
`1673acd5f0609f46eb66c7cd5761c0044ab78d6f505c6075861dddb12c3c2a1b`.
The alternate launcher SHA-256 is
`8dcb9de2dae0c8c81a1c653db6416656c74fe887153a49c19753891d23a0ae2a`;
the profile DLL SHA-256 is
`86007dd1ddac9103508eeca520e2ab89b16df92780a5f8a67497ccf29567edb9`.
The normal game engine files and normal Northstar profile are preserved.

Northstar 1.31.14 includes an FFA RUI stack-allocation fix. That is relevant
upstream maintenance, not evidence that the previously observed Overflow crash
had the same cause. EA startup/authentication failures are also tracked
separately from map crashes. Restarting EA and updating the isolated runtime
occurred together, so neither alone is credited for resolving the initial
launcher stall.

## Native checks and scope

`validate_anniversary_native.py combined` loads all five installed maps, checks
live native pilot hull clearance and ground support, selects both team starts,
fires the weapon, takes native screenshots, requests postmatch and waits for
the normal return to `mp_lobby`. It then visits stock Coliseum and reloads
Overflow. The first complete combined session passed: 66, 48, 20, 24 and 24
pilot markers respectively, with no invalid markers or logged native/script
errors. This is single-client testing; team selection is not a multiplayer
match and does not establish balance or server load.

`stress --count 10` alternates PS/FFA across ten cycles, each followed by a
stock-map visit and converted-map reload. The first cycle uses the existing
process; the following nine launch fresh owned processes. A cycle is recorded
only after its reload passes. FFA retains its native player teams; forcing an
IMC/Militia team there can break the stock scoreboard. No test safety volumes
are deleted from the map or diagnostic runtime.

`modes` checks FFA on all five and the experimental CTF, Hardpoint and Fastball
setup on Phase Runner. Objective existence and spawn clearance are useful smoke
checks, not complete capture/scoring/round/evac certification. `visual` takes
fresh overview captures with active map and camera metadata for manual review.
Native screenshots come from the game's screenshot command, without a desktop
capture substitute. Raw harness sessions and game logs remain private.

The ten stress cycles completed successfully, as did FFA on all five and Phase
Runner's three objective-mode setup checks and postmatch returns. All five fresh
overview captures were reviewed with living camera players and the expected
map/pose. No pink fallback or whole-map rendering failure appeared in those
views; known source omissions remain. The owned test game/controller were closed
cleanly. The normal launcher and DLL still match their pre-test hashes.

The offline checks passed: 21 capacity/visibility/boundary/support tests, four
binary adapter tests, 12 harness tests and four disposable archive-provenance
tests. Binary adapters require Python 3.14's
`compression.zstd`; geometry checks use the project's Python 3.12 NumPy build.
Running all modules under one interpreter produces dependency errors and is not
a valid test configuration. Restricted temporary-file permission errors are
environment failures, not map failures.

## Installation and remaining limitations

Use Northstar 1.31.14 or newer; 1.31.14 is the tested version. Close the game,
move old map folders/backups outside `mods`, and extract the desired map folders
plus **one ApexMaps.UI 0.2.1** into `Titanfall2/R2Northstar/mods/`. Replace rather
than merge. Enable the mods and restart. Every player and server needs matching
versions. Keeping obsolete per-map UI atlases can recreate the atlas crash.
The shared companion also retains support for Thermal Station and Thunderdome.

The primary release scope is pilot modes PS and FFA. AI navigation, dedicated
servers and multiplayer load remain unverified. Apex-only training/loot systems,
some scenery, animated materials, FX and source shader behavior remain incomplete.
Firing Range is a map adaptation, not a functional Apex training mode. Intro and
evac are not generally enabled across these arena previews. Phase Runner's other
mode markers remain experimental.

Overflow previously crashed intermittently around spawn/load on Northstar
1.31.13. Passing a bounded newer-runtime test sample cannot establish the root
cause or eliminate the possibility of other crashes. RC release notes must keep
that history and distinguish it from the fresh test results.

`package_anniversary_rc.py` requires completed validation receipts, then builds
only runtime files, a short README and optional real game screenshot. It checks
every decompressed member against its expected hash, writes immutable RC ZIPs,
checksums and a manifest under `output/releases/anniversary-2026-rc1/`. Test mods,
compiler binaries, game runtimes, source archives, private logs and development
ledgers are excluded. Existing beta/history assets remain untouched.

## Model compiler follow-up

[The r2-model-compiler assessment](toolchain/r2-model-compiler-2026-10-28.md)
records a successful v0.5.0 example compilation and the remaining material,
collision, lighting and visibility work required to migrate baked scenery to
native static props. No anniversary map is represented as rebuilt with it.
