# Party Crasher 0.5.0

Fills all 33 empty flex-screen frames with their source panels and restores 33 source signs and 12 source banners, including the large Angel City banners over the south market. Uses 97.99% of native world index capacity, with no additional gameplay entities. Screen advertisement content is script-driven in Apex and is not supplied; panels use the static source material. Twelve further banners, dense window modules, roof foliage, animated advertisements and layered terrain materials remain incomplete. AI navigation and Titan modes are not supplied. Restart between previews.

The 0.4.0 scene placed all 33 `survival_modular_flexscreens_frame_01` frames but omitted the `survival_modular_flexscreens_04` panels inside them (4 triangles each), leaving open frames. This round adds them, then small signs, then banners, in priority order until the 98% native world-index ceiling. `timeshift_signage_01` (8 triangles) is left out because its text decal needs a reviewed alpha-overlay material. Skipped banners are listed in `inventory-summary.json`.

The independent audit passed 2,376 checks. Native tests verified 11 new source collider contacts, clear supported team spawns, all 69 safety triggers, postmatch return, stock Coliseum loading and Party Crasher reloading. Four matched R5R/Northstar views were captured from the exact mounted payload. No multiplayer FPS, AI capacity or all-five-map stress certification is implied.

A duplicate-triangle survey found no meaningful budget to reclaim: of 11,093 same-material coincident pairs, 9,885 are intentional two-sided faces, and most of the rest are stacked `echo_big_screen_animation_01` frames. Further large recovery needs the native static-prop path.

Baseline rollback is retained on the build drive under `party-crasher/before-0.5.0/`.

Reproduce with `recover_party_details.py plan`, `materials`, `append`, then `verify_party_structure.verify('0.5.0','detail-recovery',...)`, `recover_party_details.py stage`, the `party-crasher-detail-survey` routes and `verify_party_structure_runtime.py detail-recovery`.
