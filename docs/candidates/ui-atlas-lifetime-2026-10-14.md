# Combined-install UI atlas failure and repair

The reported combination of Phase Runner, Drop-Off and either new preview
failed even though each new preview had passed isolated checks. A separate
owned R2AtlasHarness installation containing all five current ports reproduced
the native dialog: `Tried to load more than 20 assets of type "UI image atlas".`
This is a shared native asset pool, independent of world triangle capacity.
The dialog was read only from the process launched by the test controller.
No executable, native UI code or engine limit is patched.

## Lifetime contract

The accepted layout has one `ApexMaps.UI` companion, loaded after `common.rpak`,
containing one `uimg` and one resident texture. Its twenty image lookups are
fifteen loading/lobby aliases and five minimaps. The atlas is 8192×4608; the
five original 2560×1440 loading images and 1024×1024 minimaps retain their sizes
and are packed into separate rectangles. BC7 sRGB recompression is a format
adaptation, not lossless original DDS block preservation.

The individual presentation packs keep their original native materials,
bindings and uberbuffers, but contain no `uimg`. Standalone minimap RPaks are
removed from runtime packages and retained in build backups. Native
`<map>_loadscreen.rpak` aliases remain. World and incremental material packs
retain `mp_coliseum.rpak` Postload ordering. Each clean map ZIP includes the
same three-file UI companion; install and enable it once beside the map mods.

Restricting minimaps alone still exceeded the atlas pool with five installed
maps. Removing a presentation Postload without an explicit filter also loaded
unwanted presentations in the installed launcher; omission is not a safe filter.
Exact filters for every world pack passed loading but visual review showed
pink fallback materials. That candidate is rejected: world shaders require the
original native base-pack ordering. Its captures and logs are retained separately.
UI-only regex filtering also still loaded unwanted presentations through the
shared dependency path in the installed launcher. The precise launcher cause
has not been isolated; do not claim regex filtering alone fixes this version.
Consolidation bounds the custom atlas cost to one regardless of those paths.
World residency is still shared across
the installed conversions and is not a new spatial texture-streaming backend.

`build_shared_map_ui.py` compiles the companion and atlas-free presentations
after all map staging. It checks unchanged native loading material states and
buffers. `map_pack_lifetime.py` audits the contract, and player packaging rejects
a separate atlas or a changed dependency order before writing a ZIP.
The harness accepts repeated `--extra-package` arguments and clears all reserved
extra package slots on relaunch. It never cleans the normal player profile.

## Validation and comparison scope

The live test installs all five maps, switches among them, checks native
screenshots for actual materials and minimaps, returns to multiplayer lobby,
loads a stock map and reloads a converted map. Completed final evidence is
recorded in `docs/conversion/ui-atlas-lifetime-validation.json`; failed candidates
are not counted as passes. This remains a single-client test and does not
certify multiplayer load or AI navigation.

The expanded source/native routes add five locations each to Firing Range,
Party Crasher and Overflow. New comparison snapshots must use accepted native
captures and actual R5R images at equal poses/FOV/resolution. Earlier snapshots
are immutable. Geometry, collision, world material pack bytes and lighting stay
intact. Presentation pack layout and UI texture packing change. The known earlier repeated-mode-change/loadout
failures remain separate from this reproducible UI pool failure.
