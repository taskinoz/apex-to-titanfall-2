# Additional arena conversion stages

The [October 13 port report](../candidates/approved-port-work-2026-10-13.md)
documents Overflow, Party Crasher and the original Firing Range. Helpers
parameterize source map, target map, material namespace, coordinate offset and
conversion bounds. Firing Range uses an outer v47 BSP with a later static-prop
record layout; dispatch the `sprp` reader from its game-lump version rather than
assuming the outer BSP version determines it. Entity partition text requires
the external `.0000.bsp_lump` when present.

Extraction uses ZSTD-capable Python 3.14, while geometry and lighting use Python
3.12 matching the installed extension modules. Set `APEX_PORT_WORK` consistently
and retain original input bytes. Referenced starpak blocks are staged at original
offsets in sparse files; Windows `SetEndOfFile` avoids materializing unused zeros.
This extraction cache is separate from native texture streaming. Current preview
RPaks use resident mip chains capped at 1024 pixels.

`prepare_new_arena_scene.py` selects structure/roof/floor/cover first and retains
source skins, transforms, UVs and RGB, using authored LODs. Tool/atmosphere-only
placements have a separate unsupported status. `build_new_arena_ports.py`
reuses checked native container and collision primitives. Collision caches bind
to selected placements; remove owned geometry/physics/bake caches when input
assets, region policy or format decoding changes. An initial world cache can
contain an existing surface bias; do not treat it as immutable raw source data.
`finish_new_arena_materials.py` embeds native cutout shader/pass dependencies and
freezes source emission. `light_new_arena_ports.py` supplies the actual source
sun to separate native bakers and uses per-chart padding, keeping the menu
outside the photographic sky. Lighting and sky mapping remain approximate.

The stage order is assets, scene, collision/material staging, material repairs,
native BSP/STBSP build, environment/probe bake, source safety volumes, native
presentation, minimap and candidate packaging. Provisional source spawns require
native floor/hull probes, a BSP entity rewrite, restaging and a fresh game load.
Then perform binary, capture and gameplay validation before finalizing.

`verify_new_arena_binary.py` checks 16 distinct categories per build. Native
`verify_new_arena_runtime.py` captures matched views and verifies the mounted
BSP hash. `verify_new_port_gameplay.py` checks pilot spawns, team selection, floor
contacts, viewing angles, Postmatch and a stock-map reload. FFA must retain its
own teams; forcing IMC/Militia teams into FFA can break the stock scoreboard.
A longer shared session encountered a native playlist-type/reload crash whose
cause remains unresolved. Clean single-map runs do not establish full release
readiness. `finalize_new_arena_previews.py` enforces exact-build gates, writes
complete placement ledgers and produces clean initial-preview player ZIPs.

These stages are reference implementations rather than a universal converter.
Full Olympus exceeds the current all-visible per-view index budget before props.
Validate a selected area and selective visibility/LOD first. This is not a
universal whole-map file-size limit or proof a full port is impossible.
