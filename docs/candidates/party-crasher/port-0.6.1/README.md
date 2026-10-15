# Party Crasher 0.6.1

Screen-tower arms and frames now collide with the shape you see instead of invisible full-detail Apex collision. Restores the flower planter that stood as an invisible object, the two reported glass columns (with collision) and three cafe tables with stools. Distant unreachable scenery drops to its lowest authored detail to pay for them; the map still uses 98% of native world index capacity. Foliage, remaining cafe furniture, animated advertisements and AI navigation remain absent. Restart between previews.

## How

- `match_collision_to_render.py`: 19 coarse-LOD placements (screen-tower arms, flexscreen frames) over 15% collision/render mismatch get triangle collision from their drawn triangles; 87 source brushes leave the collision grid.

- `upgrade_placement_lods.py`: 26 placements more than 1,500 units from any reachable point drop to their lowest authored LOD (net -9,100 triangles).

- `recover_party_columns.py`: 8 props in released lightmap tiles, reported positions first. The flower planter `party_crashers_pillar_03` at report q33 had its collision baked into the Apex world collision, so while omitted it was an invisible object; it is now drawn. Glass columns use a meshoptimizer-simplified LOD0 (no lower authored LOD exists).

- Fixed `recover_composite_details.append_collision`: it rebuilt the collision grid over every primitive, re-enabling source colliders that collision matching had disabled. It now keeps disabled primitives out.

Validation: 2,356 binary checks; collision grid = previous active set plus the new headers (none re-enabled); native traces stop on the drawn surface at 19/19 replaced placements; 4 new collider contacts; 2/4 report positions fully clean (the rest hit glass, which the check does not count as drawn); 40-view regression capture identical to 0.6.0 except the restored column; spawns, postmatch lobby, stock and map reload.

Rollback: `party-crasher/before-collision-match/`, `before-lod-upgrade/` and `before-0.6.1/` on the build drive.
