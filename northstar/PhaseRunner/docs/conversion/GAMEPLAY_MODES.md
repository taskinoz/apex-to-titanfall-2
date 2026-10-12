# Phase Runner gameplay layout — 1.1.0

IMC (team 2) starts in the west building; Militia (team 3) starts in the east building. Both face toward the arena. Native modes may swap bases at halftime. The client connection callback preserves existing team assignments and spectators; its fallback assigns the smaller team instead of forcing everyone to IMC.

The entity lump adds 92 records: 24 pilot starts (12 per building), 42 pilot respawns, 12 outdoor Titan respawns, 6 Titan starts (3 per side), 2 flag bases, 3 hardpoint markers and 3 capture volumes. Regular respawns are neutral and use Northstar's native frontline, enemy sightline and cooldown ratings. Building starts, Titan starts and flags carry explicit team numbers. Native CTF additionally restricts respawns to the friendly flag side. FFA can use the distributed neutral points.

| Mode | Console identifier | Map configuration |
|---|---|---|
| Attrition | `aitdm` | Pilot/Titan starts and respawns. AI navigation is still missing. |
| Titan/pilot Team Deathmatch | `tdm` | Shared native spawn pool and opposing building starts. |
| Pilot Skirmish | `ps` | Same pilot layout; native mode disables Titans. |
| Capture the Flag | `ctf` | Flag in each building, native flag pickup/return/scoring logic. |
| Amped Hardpoint | `cp` | A west forecourt, B central roadway, C east forecourt; native capture/amp/scoring triggers. |
| Fastball | `fastball` | Opposing outdoor Buddy Titan throw locations and three native hacking/respawn panels. |
| Last Titan Standing | `lts` | Three large-hull starts per side, outside the buildings. |
| Titan Brawl | `ttdm` | Outdoor Titan spawn pool. |
| Marked for Death | `mfd` | Shared pilot/Titan layout; native player target selection. |
| Free for All | `ffa` | Distributed neutral spawn pool. |

Select a mode in a private match, or set `mp_gamemode <identifier>` before `map mp_phase_runner`. This does not add Frontier Defense waves, Bounty Hunt banks/camps, AI navigation, custom Apex rules or new mode implementations.

## Objective placement and authoring

CTF uses `info_spawnpoint_flag` entities with `teamnumber` 2 and 3. CP uses `info_hardpoint` with groups A/B/C and the native mobile-hardpoint model. Each marker's `triggerTarget` resolves to one `trigger_capture_point`. Capture volumes serialize six local axial planes in `*trigger_brush_0_plane_0` through `_5`, with matching `*trigger_bounds_mins/maxs`. Both teams and players are accepted, phase-shifted players excluded. Capture boxes are 640 x 640 x 224 units around their markers; no collision wall is introduced by a trigger.

Fastball uses the existing global Northstar hooks `FastballAddBuddySpawnForLevel` and `FastballAddPanelSpawnsForLevel`. Panel hooks receive alternating origin/angle vectors. The native throw intro is retained for Fastball; other modes retain the map's normal no-dropship intro. A TDM spawn-mode override lets the custom mode use the native checkbox filters without passing an unknown mode into `GameModeRemove`.

Coordinates and exact target names are in [gameplay-layout.json](../../gameplay-layout.json). `build_phase_runner_modes.py` derives floor candidates from triangle intersections, then uses native game probes to refine the physical positions. The serialized BSP entity edit preserves every existing non-entity header and byte of the original BSP body. It appends the new entity text at 16-byte alignment and changes only the entity lump descriptor. Rendering, collision, lighting, visibility and texture data are unchanged. Seven original entities plus 92 added records give 99 serialized entities, distinct from additional runtime mode entities.

The native loader grounds spawn markers after parsing. If an outdoor Titan marker then clips uneven terrain, the map callback tests a complete 200 x 200 x 400 hull eight units higher and requires a floor within 32 units before using that clearance. It never disables collision or accepts a failed hull test.

## Verification and limits

The gameplay regression suite checks the entire preserved BSP body, base separation and pilot spacing, unique target names, flag teams, capture marker/trigger links, convex trigger planes, objective/respawn overlap and harness input validation. The owned native client checks all 86 spawn/flag markers for hull clearance and floor support, mode activation, native team start selection, CTF flag creation, capture/amp progress for A/B/C and Fastball panel creation. See `gameplay-runtime.json` in the release for the actual mode results and limits. This is single-client functional validation; multiplayer spawn balance, a full CTF match, live Fastball hacking/team respawns and all Titan drop trajectories require human matches.

Attrition's native script only starts its AI waves when a valid AIN revision and nonempty node graph exist. Phase Runner still lacks that navigation graph. Adding human/Titan spawn markers cannot supply grunt/spectre pathfinding, dropship/droppod routes or safe NPC deployment.

During an automated switch out of LTS, the stock Titan-selection menu asserted while deregistering its back button. The harness now launches a fresh process for switches out of Titan-only modes and archives that process's log. The earlier failure is retained as test evidence; no stock Northstar gameplay/UI code is patched. The harness remains a separate opt-in testing mod and is not shipped in the map release.

The 1.0.0 ZIP and install backup remain available for rollback. The static placement/entity source inventories in this technical handoff retain their explicitly versioned 1.0.0 provenance; the 1.1.0 gameplay layout is an authored Titanfall adaptation, not additional recovered Apex source entities.
