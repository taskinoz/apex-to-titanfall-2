# Drop-Off 0.11.0 for Northstar

Close Titanfall 2. Move the old map folder to a backup outside `mods/`, then
extract `ArenaComposite` into `Titanfall2/R2Northstar/mods/`. Replace the old folder
rather than merging; obsolete atlas files must be removed. Enable it in
Northstar's mod menu and restart. Disable any older copy of the same map.
Every player needs the same mod version.

The loading artwork and minimap come from the shared `ApexMaps.UI` companion,
a separate download (`ApexMaps.UI-<version>-Northstar.zip`). Install it once
for all five Apex maps and keep the newest version; map archives do not
include it, so installing a map never replaces your companion.

Launch from the console:

```text
map mp_arena_composite
```

The sun now comes from Apex's direction: Drop-Off had been lit with Phase Runner's sun, from nearly the opposite side, so its baked sun shadows, sun shading and character lighting are re-baked for Apex's sun. Reflection cubemaps captured in game give metal, glass and wet surfaces something to reflect, and the sun-shadow geometry is welded, so the map file is about 25 MB smaller. Tested on Northstar 1.31.14 in single-client PS/FFA: all 60 spawns clear and supported, both teams, weapon fire, postmatch lobby and stock/map reload; this is not multiplayer certification. Requires ApexMaps.UI 0.2.1.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
