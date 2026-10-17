# ArenaOverflow 0.4.1

Fixes z-fighting and flat textures from Apex overlays that were drawn as solid surfaces on top of the surface below: stencil lettering (REFINERY, the capsules) and arrow signs are now proper decals, the flat brown dirt sheet over the asphalt is removed, and the lava no longer flickers between its glow and a grey duplicate. The invisible barrier in the ceiling opening is an Apex player clip and is kept. Known issue (also in 0.4.0): about one load in five can crash Northstar at spawn; restart and load again.

## Previous release notes

# Overflow 0.4.0

Restores Apex two-layer blending with Titanfall's native blend shader: stains, dirt and wear on concrete, painted metal and rock now blend as in Apex instead of showing one layer. 51 pipes, rocks and wall plates drawn at coarse detail now collide with the shape you see, and 53 props whose Apex collision was still in the map (tech panels, server racks, ceiling servers, warning lights, vents) are drawn instead of being invisible objects. Known issue (also in 0.3.1): about one load in five can crash Northstar at spawn; restart and load again. Animated advertisements, AI navigation and Titan modes remain absent.

## How

- `apply_layer_blends.py`: 18 Apex bm materials rebound to Titanfall's native wld bm shader with source vertex alpha / z-up blend input (all 18 matched their source alpha).

- `match_collision_to_render.py`: 51 coarse-LOD placements over 15% collision/render mismatch collide with their drawn triangles; no spawn moved.

- `recover_invisible_props.py`: 53 omitted props near reachable ground whose own surface lay on undrawn world collision are drawn from their source VG; no collision added.

Invisible reachable collision: 3.7% before, 2.8% after.

Validation: 1,544 binary checks; collision grid = 0.3.1 active set minus replaced colliders plus new headers; 31/31 drawn-surface contacts (9 samples stopped on an unrelated pre-existing clip above the pipes); spawns, both teams, postmatch lobby, stock and map reload. Two of many harness sessions crashed on a second map load at spawn; repeated fresh-session and reload tests of this build and of 0.3.1 show the same intermittent Northstar instability, not a new fault.

Rollback: `overflow/before-layer-blend/`, `before-collision-match/`, `before-invisible-props/` on the build drive.

## Previous release notes

# ArenaOverflow 0.3.1 UI atlas hotfix

The five maps share one UI atlas through ApexMaps.UI. Enable the included companion. World materials, geometry and collision are unchanged. See the repository's UI atlas validation receipt for final combined-install checks.

## Previous release notes

# Overflow 0.3.0 — Northstar preview

Extract `ArenaOverflow` into `Titanfall2/R2Northstar/mods/`, enable it and restart.
Every player needs the same version. Launch with `mp_gamemode ps` followed by
`map mp_overflow` (or choose `ffa` for Free For All).

Early native preview for Pilots vs Pilots and Free For All. Recovers 2,459 baked source placements and uses 87.87% of this engine's measured per-view world index capacity. Restores 259 omitted source lights through static diffuse surface and character lighting; the 56 native RTL slots remain unchanged. Restores source fog, reflected source colour constants and native HDR emission from Apex texture masks. Vertex palette/layer data is retained but its unverified RGB interpretation is disabled. Animated advertisement frames and Apex volumetric scattering remain incomplete.

Native checks cover both pilot modes, supported/clear spawns, both team start
selections in PS, viewing angles near those starts, postmatch return to lobby,
and a stock-map reload. Tests used one local client; multiplayer performance
and balance are not established. Scenery is baked into native world meshes.
A longer shared Overflow/Party Crasher session crashed during repeated mode
changes. The cause is unresolved. Restart between new preview maps and avoid
repeated mode cycling in the same process.

This is less complete than Phase Runner and Drop-Off. Decorations, dense
foliage, distant scenery and some materials are missing. Authored lower LODs,
1024-pixel texture caps, approximate sky mapping, coarse direct lightmaps and
point approximations of spot lights reduce fidelity. Some native HDR emission
and water scrolling are recovered; animated advertisements, volumetric effects
and other specialized source shaders remain incomplete. Apex interactions, weapon stations,
training dummies, AI navigation, Titan modes, CTF/Hardpoint/Fastball objectives,
intro and evac are not supplied. Source safety volumes are retained, but each
hazard has not been physically exercised. The Firing Range minimap is generated;
the arena minimaps use original overview artwork. Enable only the preview map
you are testing to limit resident texture packs; all five ports together have
not been validated. Original game assets remain their creators' work.

Detailed counts and every omitted source placement are recorded in the repo's
`docs/candidates/overflow/port-0.3.0/`.
