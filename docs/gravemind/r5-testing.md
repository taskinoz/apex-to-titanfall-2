# R5Reloaded source-map testing and paired Northstar captures

Evidence scope: installed R5R `v2.6.52`, October 12, 2026. These findings come
from the native game, local SDK source, controller tests and captured images.
They do not establish compatibility with every R5R release.

## Controller and installation

The project now has `r5-harness/harness.py`, `protocol.py`, a small Squirrel
helper, JSON routes and `Run-R5Harness.ps1`. It launches the installed executable
directly, loads maps, controls a fixed camera and requests the game's native
`screenshot` command. TGA captures are converted to PNG without changing their
pixels. Metadata records map, origin, angles, requested FOV, dimensions, VM
state, generation, capture time and SHA-256.

The test installation is a separate owned directory. Large immutable asset
directories are hardlinked on the same volume; scripts, configs, executables
and mutable files are independent copies. Staging refuses an unowned directory
and unlinks a destination before replacing it, avoiding writes through an asset
hardlink. The copied base compile list includes the helper. Existing SDK mods
are copied because the installed scripts/playlists depend on their assets.
This isolates installation edits, not the entire Windows user account.

The offline development playlist is `dev_default`. Use `cl_setname MapHarness`
when bypassing the SDK launcher; an empty offline name is rejected during
signon. The engine executes its own RCON configuration after command-line
options, so that copied configuration must retain the harness settings. Wait
for `SIGNONSTATE_FULL` before accessing map script VMs.
Phase Runner first disconnected with `#DISCONNECT_NETCHAN_OVERFLOW` immediately
after full signon under the inherited 120-player development setup. A copied
two-player playlist and `net_processTimeBudget 0` kept the native session alive.
Both settings changed together; this is not an isolated causal test, and the
two-player configuration is a harness setting rather than an engine/map limit.

## Installed console protocol

The installed v2.6.52 envelope differs from the June 2025 upstream SDK schema.
The observed layout is saved as `r5-harness/netcon-v2.6.proto`. Its descriptive
field names are local documentation of the exercised wire contract.

The frame header is two network-order 32-bit integers: magic `0x6e6f4352`, then
protobuf envelope length. The envelope has a nested header in field 1, nonce
bytes in field 2, authentication-tag bytes in field 3 and message bytes in field
4. The nested header has sequence in field 1 and a 64-bit nonce in field 2.
Requests and responses retain the older messageId/messageType/type/message/value
fields 1–5. Sequence starts at one independently in each direction per socket.

Control binds to IPv6 loopback on a separate host port. Frames are unencrypted
only within that local harness; authentication uses a random runtime password.
Passwords and console keys are excluded from exported logs and documentation.
The controller preserves partial frames across socket polling timeouts and
checks incoming sequence order.

Script prints are not consistently echoed over RCON in this installed SDK.
Native `platform/logs/<session>/script.log` is an additional acknowledgement
channel. Every command carries a random ticket. An old log entry cannot satisfy
a new ticket. Server/client VM instance IDs distinguish a completed reload from
stale same-map state. Process stopping checks both liveness and creation time;
a missing creation timestamp cannot authorize termination.

## Camera and comparison semantics

Route coordinates are Titanfall camera/eye positions. For the original Apex
Phase Runner, add `[26000,19000,0]`; Drop-Off uses zero offset. Angles are
`[pitch,yaw,roll]` in degrees. Both engines receive the same angles and FOV and
must produce the same capture resolution. R5R also moves the server player near
the camera and uses noclip, keeping gravity and streaming from pulling its
viewpoint away. Native camera origin/angles can be recorded independently of
the requested values.

First-run agreements require the user's decision. Gameplay message panels are
cleared after that decision. Titanfall's opening countdown can still overlay a
valid camera view; wait for it before taking comparison captures.

Comparison runs are sequential by default to avoid keeping both games in
memory. Source captures are saved before closing the owned R5R process.
`--resume` reuses those source images after checking their route and SHA-256.
The target side uses an already healthy matching map or a fresh owned launch.
Do not force an unnecessary same-map reload after `Northstar.start` has already
loaded the target. During this test, that redundant reload returned to the main
menu; a fresh launch completed the paired route.

The gallery contains side-by-side views, an opacity overlay and capture
metadata. It is evidence for geometry, placement and visual completeness.
Different shaders, lighting, banners, HUDs and tonemapping prevent a pixel-exact
assertion of port correctness. These camera captures do not certify collision,
AI navigation, framerate, networking or game-mode behavior.

Related: [Native Northstar testing](testing-and-packaging.md),
[Case studies](port-case-studies.md), [Visibility and limits](visibility-and-limits.md).
