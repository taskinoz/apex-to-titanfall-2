# Firing Range 0.5.0

Restores Apex two-layer blending with the native Titanfall blend shader: sand on rock tops and slopes, sandy ground and blended red rock now follow the Apex blend weights. Raises 39 blocky rocks near reported spots to finer authored detail, so they sit closer to their collision, and stops drawing 9 meshes no reachable position can see. Includes the 0.4.0 landing pad and surface repairs. Uses 97.63% of native world index capacity. Many rocks still use coarse detail for budget reasons; foliage, weapon stations, targets and AI navigation remain absent. Restart between previews.

## How

- Native blending: the Titanfall wld bm shader (Coliseum concrete_plates_plain_wet_bm) evaluates the same equation as the Apex blend materials. Blend inputs are written into vertex alpha: source vertex alpha (the bsp_tool `negative_one` field for world geometry), or the source z-up ramp from the normal for the sand-on-rock materials (apply_layer_blends.py). All 12 Firing Range blend materials converted.
- Hidden geometry: analyse_visibility.py found 9 meshes (2,812 triangles) with no line of sight from any reachable position; they keep casting sun shadows.
- Rock detail: upgrade_placement_lods.py retires old-LOD triangles by exact position and appends the finer authored LOD into released lightmap tiles. 39 rocks nearest the reported views moved up one level; 14 rocks more than 1,500 units from any reachable point moved to their lowest level to pay for it. Collision is unchanged.

The independent round audit passed 868 checks. Native tests verified 20 landing-pad surface contacts, clear supported team spawns, unchanged safety triggers and ropes, postmatch return, stock Coliseum loading and Firing Range reloading.

Rollback snapshots are kept on the build drive under `firing-range/before-layer-blend/`, `before-retire/` and `before-lod-upgrade/`.
