# Drop-Off 0.3.0: compare with the Apex source

Reference files: `inputs/composite/client/maps/mp_rr_arena_composite.bsp` and its
external lumps, especially `mp_rr_arena_composite_script.ent`. These are local
source records, not an independently launched Apex gameplay comparison.

## Ziplines and restricted areas

The source has exactly two `zipline` / `zipline_end` pairs, linked by GUID:

| Route | Start | End |
| --- | --- | --- |
| West | -390.012, 4178.35, 283.789 | -754.951, 2764.85, 341.27 |
| East | 393.988, 4174.35, 283.789 | 758.429, 2764.76, 341.27 |

These endpoints are retained exactly in native `move_rope` / `keyframe_rope`
entities. Native rope physics approximates the source sag/rest curve.
The two upper-platform ropes in 0.2.0 were authored additions, not recovered
source objects. They are removed, together with the authored openings in the
source out-of-bounds volumes. All 21 source out-of-bounds volumes and five hurt
volumes remain active with their original converted convex shapes.

The user confirmed the north closure at (12,5625,16) and diagonal closure near
(1614,2690,-146) protect rooms that should stay inaccessible. The earlier repair
mistakenly classified them as obsolete forcefields. Restored 12 north boundary
triangles, 24 diagonal boundary triangles including the mirrored side, and 34
source rooftop exclusion triangles. These are the original source faces, not
new guessed boxes. Other collision is retained.

## Spawn covers

The source defines nine `func_brush_arenas_start_zone` models, with six around
the active opposing spawn rooms and three at a remote alternate spawn region.
Their `ar_arena_start_barrier_blue` geometry was rendered as a permanent grid
cover in the port, though the native collision traces across all six active
exits were already clear. There were no exact matching collision triangles in
the converted triangle stream, so no nearby frame, wall or prop collision was
removed speculatively.

Disabled exactly 108 source start-barrier render triangles and the same 108
shadow triangles. Indices become degenerate, preserving mesh ranges and native
pair padding. Render positions, material bindings, lightmap charts, lightmap
pages and character probes stay byte-identical. The previous bake may retain
minor static shadows from the temporary covers; a later full bake should omit
these covers. The renderer-neutral preparation step now excludes them too.

## Binary repair and validation

`repair_composite_source_layout.py` recovers the previously removed 70 source
clip triangles and rebuilds native triangle headers and their spatial grid.
It appends the new collision positions after the existing position buffer,
offsetting header vertex references to preserve all current render indices.
The canonical collision cache is separately updated for a future full build.
Snapshots are retained under `output/repair-backups/20261007-source-layout`.

Regression tests compare zipline endpoints directly against the full source
entity list and verify the exact 108 render/shadow changes, unchanged lightmaps,
collision ranges, source trigger counts, spawn starts and native draw capacity.
Runtime results are in `output/composite/source-layout-runtime.json`.
Clean player distributions still contain only runtime files, a short README
and an actual in-game screenshot. 0.2.0 remains available for rollback.

For future converters: treat conditional entity geometry separately from the
permanent world. A tools clip with no corresponding visible panel can be an
intentional room or roof boundary. Preserve its source provenance and gameplay
purpose before removing it. Do not infer zipline positions from a suspected
access route when source link endpoints are available.

### Native confirmation

All 19 regression checks passed. Native traces cross all six spawn exits
without collision. North and both mirrored diagonal room closures register
collision. Reviewed native captures show the start covers removed and the
map still rendered correctly. Runtime entity counts retain two rope pairs,
21 out-of-bounds volumes and five hurt volumes. A forced native Postmatch
returned to the lobby with the same live process and no logged script errors.
This single end-state test does not establish the cause of the earlier crash.
