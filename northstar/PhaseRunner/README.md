# Phase Runner 1.7.1

Fixes the flickering floor in both starting bases (opaque Apex decals drawn on the same plane as the floor; the stripes are now alpha-blended decals and a wrong stand-in sign texture is hidden), restores the metal frames around stacked containers that left visible gaps, and smooths the tunnel catwalks so they no longer dip and meet the floor at both arena ends. Minimaps are no longer washed out (shared ApexMaps.UI 0.1.1). Includes 1.7.0: Apex two-layer blending, Apex-scale ground tiling and collision matched to 210 cliffs and rocks.

## How

- `phase_runner_blend.py` traces each Apex blend material's pixel shader (layer UV source, ramp, vertex-alpha or z-up blend input). Vertex alpha comes from the source BSP vertex colours and prop VG colours matched by position, or from the z-up normal term; materials whose albedo is projected from world position get `uv = (x, -y) . RotScale + Translate` in source coordinates. The surfaces are rebound to native Coliseum wld bm materials in a new `phase_runner_blend.rpak`. Layer 2 is sampled at the mesh UV (Titanfall's shader has one UV): the tiling of world-projected snow/moss layers on rocks is approximate, not their colour.

- Kept single-layer: dam_concrete_02_stained_bm, metal_painted_yellow_02_dirty_bm, asphalt08_cracked_bm (unmatched source alpha or a regression in native captures).

- `phase_runner_collision.py` finds each rock's drawn LOD by vertex matching and replaces the source collider of 210 rocks over 15% mismatch with their drawn triangles. Owners with any disabled primitive (tunnel caps, catwalk clips) are not touched; spawns are not moved.

Invisible reachable collision: 18.2% before, 1.0% after (upper bound: reach ignores out-of-bounds volumes).

Validation: 112 binary checks (only vertex alpha/UV, texture-data strings and appended collision change; render budget unchanged); 84 spawns clear and supported; 40/40 drawn-rock contacts; both teams, postmatch lobby, stock and map reload.

Rollback: `legacy-work/phase-runner/before-1.7.0/` on the build drive.

## Previous release notes

# Phase Runner 1.7.0

Restores Apex two-layer blending with Titanfall's native blend shader: snow caps and moss on rocks, moss lines on the structures and moss/dirt ground now blend as in Apex. Snow and moss ground tile at the Apex scale instead of 3-8x too coarse. 210 boundary cliffs and rocks drawn at coarse detail now collide with the shape you see instead of invisible full-detail rock. Minimap, gameplay, tunnel and catwalk collision exclusions, lighting and scenery are unchanged. AI navigation remains incomplete.

## How

- `phase_runner_blend.py` traces each Apex blend material's pixel shader (layer UV source, ramp, vertex-alpha or z-up blend input). Vertex alpha comes from the source BSP vertex colours and prop VG colours matched by position, or from the z-up normal term; materials whose albedo is projected from world position get `uv = (x, -y) . RotScale + Translate` in source coordinates. The surfaces are rebound to native Coliseum wld bm materials in a new `phase_runner_blend.rpak`. Layer 2 is sampled at the mesh UV (Titanfall's shader has one UV): the tiling of world-projected snow/moss layers on rocks is approximate, not their colour.

- Kept single-layer: dam_concrete_02_stained_bm, metal_painted_yellow_02_dirty_bm, asphalt08_cracked_bm (unmatched source alpha or a regression in native captures).

- `phase_runner_collision.py` finds each rock's drawn LOD by vertex matching and replaces the source collider of 210 rocks over 15% mismatch with their drawn triangles. Owners with any disabled primitive (tunnel caps, catwalk clips) are not touched; spawns are not moved.

Invisible reachable collision: 18.2% before, 1.0% after (upper bound: reach ignores out-of-bounds volumes).

Validation: 126 binary checks (only vertex alpha/UV, texture-data strings and appended collision change; render budget unchanged); 84 spawns clear and supported; 40/40 drawn-rock contacts; both teams, postmatch lobby, stock and map reload.

Rollback: `legacy-work/phase-runner/before-1.7.0/` on the build drive.

## Previous release notes

# PhaseRunner 1.6.1 UI atlas hotfix

The five maps share one UI atlas through ApexMaps.UI. Enable the included companion. World materials, geometry and collision are unchanged. See the repository's UI atlas validation receipt for final combined-install checks.

## Previous release notes

# Phase Runner 1.6.0 for Northstar

Adds 432 original scenery placements. Uses 97.04% of the native world index capacity with no added dynamic entities. Existing minimaps, gameplay, collision exclusions and tunnel visibility are preserved. See SCENERY_FILL.md for measured budgets and validation. AI navigation remains incomplete.

## Previous release notes

# Phase Runner 1.5.0 for Northstar

Adds the original Apex minimap artwork with Titanfall radar scaling and the port coordinate offset. Includes frozen Apex displays, authored gold tunnel paint, source out-of-bounds areas, a fall kill volume, team spawns, CTF, Amped Hardpoint and Fastball. Existing collision, lighting and catwalks are preserved. Terrain layers, Attrition AI/navigation, animated shaders and full multiplayer balance remain incomplete.

The minimap uses the original Apex artwork with corrected native radar scale. See MINIMAPS.md for conversion details and checks.

## Previous release notes

# Phase Runner 1.4.0 for Northstar

Restores frozen Apex screen artwork and display colours alongside the authored gold tunnel paint. Includes source out-of-bounds areas and a fall kill volume, team spawns, CTF, Amped Hardpoint and Fastball. Existing collision, lighting and catwalks are preserved. Terrain layers, Attrition AI/navigation, animated shaders and full multiplayer balance remain incomplete.

The texture pass is checked with matched native screenshots and same-process
map reloads. See BANNER_DISPLAYS.md for the source channels, exact scope and
limitations. Geometry submission budgets, collision, visibility, world lights
and character probes remain unchanged.

## Previous release notes

# Phase Runner 1.3.0 for Northstar
Restores authored RGB paint on 66,208 existing vertices with native
Titanfall colour-aware PBR shaders. Geometry, collision, lighting, visibility
and gameplay retain the prior working build. See VERTEX_PAINT.md and the repo
comparison site for baseline and repaired native views.

The prior release notes below describe the preserved gameplay and earlier
validation; the paint repair is documented above.


Phase Runner now has opposing building bases: IMC west and Militia east. There are 12 pilot starts per team, 42 distributed pilot respawns, 12 outdoor Titan respawns and three Titan starts per side. CTF has flags in both buildings; Amped Hardpoint has A/B/C capture areas; Fastball has native Buddy throw positions and three hacking panels. Shared spawns also serve Pilot Skirmish, Last Titan Standing, Titan Brawl, Marked for Death and FFA.

## Install and play

Close Titanfall 2. Extract the `PhaseRunner` folder into your active Northstar profile's `mods` directory. Replace or disable the earlier PhaseRunner/PhaseRunner.Preview copy so only one version loads. All players joining the match need this map version. Common Northstar/Coliseum assets are required.

Select the mode in a private match, or set `mp_gamemode <mode>` before `map mp_phase_runner`. Identifiers: `aitdm` Attrition, `tdm` TDM, `ps` Pilot Skirmish, `ctf` CTF, `cp` Amped Hardpoint, `fastball`, `lts`, `ttdm` Titan Brawl, `mfd`, `ffa`.

Attrition pilot/Titan spawns are configured, but AI waves still require a valid authored AIN/navigation graph. Frontier Defense waves and Bounty Hunt banks/camps are not included. Multiplayer balance and full Fastball team respawn/CTF matches still need human playtests.

## Validation

Ten modes were checked in the native game. All 86 spawn/flag markers pass standing-hull clearance and floor support checks. Native team start selection was checked in the pilot modes, both CTF flags were created, all three hardpoints captured and began amping for the chosen teams, and all three Fastball panels were present after the throw intro. Five gameplay regression tests and six harness tests passed.

The entire existing BSP body and all non-entity headers are unchanged from 1.0.0. Existing lighting, textures, visibility, collision, recovered props, twenty firs and tunnel catwalks are retained. Only native gameplay entities and map scripts were added. The earlier release ZIP remains available for rollback.

See [gameplay documentation](docs/conversion/GAMEPLAY_MODES.md), gameplay-layout.json, gameplay-runtime.json and gameplay-validation.json. The conversion guide and source omission ledgers retain their versioned provenance; this authored gameplay layer is separate from source asset recovery. The optional harness is not part of the shipping mod, and local-test settings default off.