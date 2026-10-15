# Firing Range 0.5.1

Rocks now collide with the shape you see: 329 rocks drawn at coarse detail had full-detail Apex collision, which left invisible rock to bump into and visible rock to fall into. Their collision is now the drawn shape, and spawns that stood on the old shape were moved onto the visible ground. Invisible player clips left around the missing shooting-range targets are removed. Invisible collision across the playable area drops from about 16% to under 3% of collision surface. Includes 0.5.0 blending and rock detail. Weapon stations, targets, foliage and AI navigation remain absent. Restart between previews.

## How

- `audit_collision_visibility.py` samples the active native collision (brushes and triangle headers) of the playable area against the drawn surfaces. Before: 15.7% of collision surface had no drawn surface within 24 units. After: 2.8%.

- `match_collision_to_render.py` recovers each placement's own collider from the deterministic build order and measures both directions. Coarse-LOD placements over 15% mismatch have their source collider removed from the collision grid (data stays serialized) and get triangle collision made from the exact drawn triangles. Spawn markers not standing on a drawn surface are moved onto the highest drawn surface below them.

- `remove_target_clips.py` removes clip-only collision within 250 units of shooting-range target markers that has no drawn surface nearby; Apex scripts spawn the targets there, this port does not.

Validation: 147 binary checks; native traces stop on the drawn rock at 38/40 sampled rocks; 11/12 reported positions fully clean (the rest have one edge ray); all spawns clear and supported, landing-pad contacts, postmatch lobby, stock and map reload.

Rollback: `firing-range/before-collision-match/` and `before-target-clips/` on the build drive.
