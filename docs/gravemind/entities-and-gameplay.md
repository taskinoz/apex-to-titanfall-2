# Map entities, safety volumes and Northstar gameplay adaptation

Read source BSP and external `.ent` partitions, but distinguish source geometry
from behavior. A matching classname or imported brush does not establish that
Apex scripts, conditional states, doors, audio or effects work in Titanfall.

## Conditional geometry and source-linked ropes

Drop-Off had nine `func_brush_arenas_start_zone` models, six around active spawns
and three in a remote alternate area. Treating their start covers as permanent
world geometry covered the doors. Exactly 108 active-cover render/shadow faces
are disabled. Native traces across all six active exits were already clear, so
nearby collision was not removed speculatively.

Source `zipline` and `zipline_end` GUID links define two real rope pairs. Preserve
their endpoints and adapt them to native `move_rope` / `keyframe_rope`; sag is
approximate. Earlier guessed upper-platform routes were removed in 0.3.0.
Drop-Off 0.6.0 retains only these source routes:

| Route | Start XYZ | End XYZ |
| --- | --- | --- |
| West | -390.012, 4178.35, 283.789 | -754.951, 2764.85, 341.27 |
| East | 393.988, 4174.35, 283.789 | 758.429, 2764.76, 341.27 |

Invisible room/roof clips can be intentional even without visible doors. Restore
closure visuals or adapt behavior deliberately; do not infer an opening from an
empty viewport. Drop-Off's eight scripted Apex doors are not implemented.

## Native safety triggers

Source `*coll0`, `*coll1`, ... blobs are decoded in numeric order. The tested
descriptor is 56 bytes with leaf start at offset 28. Leaf header is `<4B4f>`
(vertex/face/triangle/quad counts, XYZ frame and scale). Positions are signed
int16, scaled by `65535 * leaf_scale`, then translated by the frame origin.
Unsigned decoding wrongly displaced fall volumes and could place a kill plane
above the arena. This is not the same coordinate rule as every world BVH leaf.

Rebuild each convex native trigger with local plane keys
`*trigger_brush_B_plane_P` and `*trigger_bounds_mins/maxs`, preserving intended
class, damage and boundary settings. Remove obsolete source collision blobs/model
references and apply the map transform once. Target entities live in the main
lump with empty external-partition tag in these builds.

Phase Runner 1.2.0 converts 82 source out-of-bounds entities and one fall hurt
volume; one wholly remote boundary is omitted. Countdown activation/reset was
verified in the native client. Drop-Off retains 21 source out-of-bounds and five
hurt volumes. The project clips convex pieces to its target coordinate domain;
that is a conversion policy rather than universal native bounds.

## Teams, spawns and objectives

Phase Runner uses IMC team 2 west and Militia team 3 east, preserving existing
assignments/spectators and assigning fallback players to the smaller team.
1.1.0 adds 92 entities: 24 pilot starts, 42 neutral pilot respawns, 12 outdoor
Titan respawns, six Titan starts, two flags, three hardpoints and three captures.
Native respawn ratings retain frontline, enemy sightline and cooldown logic.

CTF uses `info_spawnpoint_flag` with explicit team numbers. Hardpoint uses
`info_hardpoint` linked by `triggerTarget` to `trigger_capture_point`; six local
axial planes define each 640x640x224 capture box. Trigger volumes are not solid
walls. Fastball uses the native Northstar Buddy/panel hooks with alternating
origin/angle vectors; it needs more than ordinary human spawn markers.

| Identifier | Phase Runner adaptation |
| --- | --- |
| `aitdm` | Attrition spawns present; AI navigation still missing |
| `tdm`, `ps`, `ffa` | Native spawn pools/team starts; neutral FFA points |
| `ctf` | Two flag bases and native pickup/return/scoring setup |
| `cp` | Three capture/amp objectives |
| `fastball` | Buddy throw locations and three native panels |
| `lts`, `ttdm`, `mfd` | Titan/team or shared native spawn setup as appropriate |

Observed pilot markers were floor/hull checked; Titan clearance uses a
200x200x400 hull. Single-client objective activation is not proof of complete
multiplayer matches, balance, all trajectories or all mode lifecycle behavior.
An AIN revision and nonempty navigation graph are needed for native Attrition
AI waves. Adding spawn entities cannot supply grunt paths or deployment routes.

Drop-Off targets Skirmish, Pilots vs Pilots and FFA, with 24 team human starts,
24 neutral human respawns, six team Titan starts and six neutral Titan respawns.
It has no CTF/Hardpoint/Fastball setup or AI navigation. Dropship intro/evac are
disabled in both normal map adaptations; Phase Runner Fastball retains its
native throw intro. Do not claim dropship or evac support from team spawns alone.

## Sources

`docs/conversion/GAMEPLAY_MODES.md`, `gameplay-layout.json`,
`build_phase_runner_modes.py`, `decode_source_trigger_volumes.py`,
`docs/arena-repairs-2026-10-06.md`,
`docs/dropoff-source-layout-2026-10-07.md`, and current Drop-Off omission ledger.
