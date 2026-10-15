# Party Crasher 0.6.0

Restores Apex two-layer blending with Titanfall native blend shader: moss and snow on rocks, dirt on rubble and stained concrete now blend as in Apex. Removes the opaque caustic light layer and the dark layer over the marble orbs. Stops drawing 133 meshes that no reachable position can see, and uses that budget to restore the window walls, the red screen towers that carry the banners, the Mirage race-track seating set and 14 rocks around reported gaps; these restored props carry their source collision. Uses 97.97% of native world index capacity. Glass columns, foliage, cafe furniture and animated advertisements remain omitted. AI navigation and Titan modes are not supplied. Restart between previews.

## How

- Native blending: the Titanfall wld bm shader (Coliseum concrete_plates_plain_wet_bm) evaluates the same equation as Apex, w = saturate(ramp*mask - ramp + (ramp+1)*vertexAlpha). Blend inputs are written into vertex alpha: source vertex alpha, or the source z-up ramp from the normal for moss and snow rock materials (apply_layer_blends.py).
- Hidden geometry: analyse_visibility.py floods walkable surfaces from the spawns (400-unit climbs, any drop, out-of-bounds volumes included within 600 units of in-bounds ground), casts 4,000 rays from each of 7,770 viewpoints with see-through materials passed through, then re-tests every candidate triangle with exact lines of sight to nearby viewpoints. 133 meshes (42,250 triangles) were never visible; they still cast sun shadows. A first pass used mis-oriented normals and untranslated trigger volumes and would have culled 189 visible meshes; it was rejected before release. A 40-view capture comparison of this build against the pre-cull build shows only the intended overlay removals and the restored props.
- Lightmap tiles: every native triangle owns one 4x4 tile. append_free_charts.py places new props in tiles released by retired triangles on any page.
- Overlays: every caustic_water_01 and waterfall_interior_02 triangle has another surface within 3 units, so removing them opens no holes.

The independent round audit passed 2,239 checks. Native tests verified 7 new collider contacts, clear supported team spawns, all 69 safety triggers, postmatch return, stock Coliseum loading and Party Crasher reloading.

Rollback snapshots are kept on the build drive under `party-crasher/before-layer-blend/`, `before-retire/` and `before-0.6.0/`.
