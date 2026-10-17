# Party Crasher 0.6.4

Adds a new Northstar billboard image to the curved Oasis screen, matching the Drop-Off banner artwork. Geometry, collision, lighting and gameplay are unchanged from 0.6.3.

## Previous release notes

# ArenaPartyCrasher 0.6.3

Fixes the fifth round of reports. The bar counter around the pillar, the glasses on it, and the rubble and rocks beside the pool are drawn where you could bump into them, and the missing tables are back in both upper cafes. Table clutter and the out-of-bounds rooftop AC unit and pipes are removed. The "234" room number no longer blooms, and the pool water is see-through instead of black. Heavy flat-panel props use simplified meshes to pay for this. Foliage, animated advertisements and AI navigation remain absent.

## Previous release notes

# Party Crasher 0.6.2

Fixes invisible objects from missing Apex props: the cafe table set, both search lights, the concrete rubble ramp and a speaker are now drawn, and the second flower planter is back with solid walls. More cafe tables and stools are restored. The fountain foam is faint, as in Apex (Titanfall cannot animate it), and the R5Reloaded placeholder screen shows a north-star emblem. Over-detailed wire bundles, consoles and pillar signs use simplified meshes to pay for this. Foliage, animated advertisements and AI navigation remain absent. Restart between previews.

## How

- Invisible collision at q34-q37 and q39 was world-baked collision of omitted Apex props, found by tracing from each report camera and testing which omitted placement's model bounds contain the hit: table set 8851/6678/6319/6625/13690, search lights 13651/13652, rubble 898/1777/12866 and speaker 9255. They are drawn at source LOD0 with their source collider.

- The q39 planter (11244) has only a small IRPS box as its source collider, so its walls collide with its drawn structural triangles (flower cards excluded).

- Budget: 14 single-LOD props in the arena (hanging wire bundles, ship consoles, pillar signage; menu-stage copies untouched) are meshoptimizer-simplified at 0.5% relative error, freeing 16,900 triangles. Collision is unchanged and the regression views show no visible change.

- q38: `water_foamy_fountain_01` is animated and faint in Apex; its opacity map is scaled by 0.3. q40: the R5Reloaded placeholder panel of `oasis_signs_ad_atlas_01` is repainted with an original north-star emblem.

Validation: 2,356 binary checks; collision grid = previous active set plus new headers; 7/7 report views fully clean; 10 new collider contacts; 19/19 drawn-surface contacts; 40-view regression unchanged except the repainted screen; spawns, postmatch lobby, stock and map reload.

Rollback: `party-crasher/before-0.6.2/` (including `texture-originals/`) on the build drive.
