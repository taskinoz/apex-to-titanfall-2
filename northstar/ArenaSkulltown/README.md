# Skulltown 0.1.1 for Northstar

Close Titanfall 2. Move the old map folder to a backup outside `mods/`, then
extract `ArenaSkulltown` into `Titanfall2/R2Northstar/mods/`. Replace the old folder
rather than merging; obsolete atlas files must be removed. Enable it in
Northstar's mod menu and restart. Disable any older copy of the same map.
Every player needs the same mod version.

The loading artwork and minimap come from the shared `ApexMaps.UI` companion,
a separate download (`ApexMaps.UI-<version>-Northstar.zip`). Install it once
for all five Apex maps and keep the newest version; map archives do not
include it, so installing a map never replaces your companion.

Launch from the console:

```text
map mp_skulltown
```

Fixes 0.1.0 crashing the game on load when other Apex map ports are installed: Skulltown now mounts its own base pack (mp_coliseum_column), so its 750 MB of map packs load only for Skulltown and loading it no longer loads every other installed port's packs. First release of Skulltown, Apex's team deathmatch Skull Town, converted from the November 2026 Apex update: the town, skull and rib bones, dunes and cliffs, with 16,036 Apex props placed natively (9,774 solid ones collide), baked lighting, 7,276 props casting real-time sun shadows and five reflection cubemaps. Apex's doors, breakable windows and ziplines are not converted (ziplines appear as ropes), and the skyline walls Apex projects around the arena are left open to the sky. Tested on Northstar 1.31.14 in single-client PS/FFA: all 96 spawns clear and supported, both teams, weapon fire, postmatch lobby and stock/map reload; this is not multiplayer certification. Requires ApexMaps.UI 0.3.0.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
