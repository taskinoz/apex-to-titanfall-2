# Approved additional conversions — initial previews

The user approved Overflow, Party Crasher and the Firing Range, in that order.
Olympus was asked about as a feasibility question; a full Olympus conversion
has not been started. The installed Olympus source has 2,544,201 base world
triangles and 7,640,388 padded indices, about 2.43 times the current per-view
world index capacity before props. Selected areas are plausible with the existing
approach. A full map needs independently validated selective visibility/LOD,
coordinate/collision handling and true streaming rather than the resident
texture catalogue used by the smaller ports. This is an engineering inference,
not a guarantee that a full port will succeed.

The new work is isolated under `APEX_PORT_WORK`; on the development host it is
`D:/Games/ApexToTitanfallWork/new-arena-ports`. The normal Phase Runner 1.6.0 and
Drop-Off 0.10.0 packages and installed copies remain unchanged. New candidates
are not player releases until the native validation gates pass.

Current scene recovery:

| Candidate | Target map | Recovered static placements | Padded indices | Capacity |
|---|---|---:|---:|---:|
| Overflow | `mp_overflow` | 2,459 | 2,764,284 | 87.87% |
| Party Crasher | `mp_party_crasher` | 1,855 | 2,763,972 | 87.86% |
| Firing Range | `mp_apex_firing_range` | 4,153 | 2,715,756 | 86.33% |

These are initial conservative scenes, with structure/roof/cover/attachment
priority and separate collision ownership. Many source decorations and dense
foliage are omitted. Geometry is baked into native world meshes and does not
add a dynamic entity per recovered prop. Gameplay volumes do add entities and
are counted separately. Full AI/navigation and universal mode compatibility
are not established.

The source map packages exported 247, 519 and 173 models respectively. Existing
shared exports are also considered. Source transforms, authored LODs and source
PBR channels are retained where recovered. Native cutout shaders and their pass
dependencies are embedded for foliage. Missing required secondary channels use
explicit neutral values, never another source object's texture atlas.
Source emission is frozen into artwork. Overflow's two lava layers and blend
mask are baked into a static approximation with constant radiance charts;
animated flow and full original shader behaviour are not reproduced.

The three sources now have native geometry/collision, resident material RPaks,
native STBSP catalogues, source sun ray bakes, local lights, character probes,
loading artwork and localized map-name tokens. Overflow and Party Crasher have
original overview artwork at corrected native scale. The Firing Range source
has no overview; its generated height-sorted geometry plan is approximate.

Authored `*coll0`, `*coll1`, ... safety volumes use the existing signed trigger
decoder and native plane adapter. Overflow retains 66 out-of-bounds volumes and
58 hurt volumes; Party Crasher retains 67 and two; Firing Range retains one hurt
volume. Resolved source rope endpoints are handled by the existing native rope
adapter. Target fall protection is also provided. Hazard behaviour still needs
native checks rather than an assumption based on entity presence.

Four support regressions pass: external entity text overrides binary BSP
headers; existing embedded native entities still read; a configured sun changes
probe occlusion; and sparse caches retain offsets without allocating unused
extents. The old CRT truncation call materialized zeros and filled C: during
initial staging. The replacement uses native sparse `SetEndOfFile`; an actual
20.2 GB optional stream occupies about 675 MB for the referenced map blocks.
Only failed newly generated caches were removed. Originals and release backups
were preserved.

Native initial-preview gates cover both pilot modes (`ps`, `ffa`), every live
pilot spawn's floor/support and clearance, team selection in `ps`, two sampled
floor contacts and six viewing-angle captures per map, forced Postmatch return
to the lobby, and a stock Coliseum/preview reload. Overflow and Party Crasher
also share an isolated process. Matched final captures bind the mounted BSP
hash to the build: three views for each arena and two useful training-area
views for the Firing Range. Detailed receipts are in each map's `port-0.1.0`
directory. These are single-client checks, not full traversal, hazard testing,
multiplayer performance or AI certification.

The provisional `mp_firing_range` name loaded but later encountered an earn-meter
network-variable error. The distinct `mp_apex_firing_range` candidate passes the
subsequent mode and reload tests; this observation does not establish the engine
error's cause. A separate test mistake forced team 3 into FFA and broke the stock
FFA scoreboard. The harness now preserves FFA's own teams and tests two-team
selection and Postmatch separately in `ps`. Failed runs were retained locally,
and the clean final receipts replace neither failure with a claimed pass.

A longer shared Overflow/Party Crasher session subsequently crashed during a
Party Crasher FFA-to-PS change. The log first reports a native playlist type
error in `Code_GetCurrentPlaylistVarOrUseValue`, then a server access violation.
This is a failed stress/reload check, not a confirmed cause or proof of a map
geometry fault. Clean, individually scoped checks do not erase this result.
The previews remain experimental; avoid repeated mode cycling in one process
and restart between new preview maps. Full release readiness is false.

The native binary gate has 16 distinct check categories per preview, including
index padding, collision references, probe/lightmap strides, material dependency
closure and static-batch headroom. Static runs are 233, 323 and 161 respectively,
below the 512-run preview policy and the measured 2,048-run native capacity.
Four conversion support regressions pass. New mod folders and clean player ZIPs
are initial previews, not full releases. Installed Phase Runner and Drop-Off are
unchanged; the five-mod bundle has not been validated, so enable one new preview
at a time. Safety volume entity presence does not prove every hazard's behavior.

The reusable steps are `new_arena_ports.py`, `prepare_new_arena_scene.py`,
`build_new_arena_ports.py`, `finish_new_arena_materials.py`,
`light_new_arena_ports.py`, `add_new_arena_gameplay.py`,
`package_new_arena_ports.py`, `build_new_arena_minimaps.py` and
`verify_new_arena_runtime.py`, `verify_new_port_gameplay.py` and
`finalize_new_arena_previews.py`. ZSTD extraction uses the local Python 3.14 runtime;
scene, lighting, tests and harness work use the bundled Python 3.12 runtime that
matches `tools/lighting-python`. Set `APEX_PORT_WORK` consistently for every
stage. Changing scene selection invalidates collision ownership caches.
