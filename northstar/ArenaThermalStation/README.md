# Thermal Station 0.2.0 for Northstar

Close Titanfall 2. Move the old map folder to a backup outside `mods/`, then
extract `ArenaThermalStation` into `Titanfall2/R2Northstar/mods/`. Replace the old folder
rather than merging; obsolete atlas files must be removed. Enable it in
Northstar's mod menu and restart. Disable any older copy of the same map.
Every player needs the same mod version.

The loading artwork and minimap come from the shared `ApexMaps.UI` companion,
a separate download (`ApexMaps.UI-<version>-Northstar.zip`). Install it once
for all five Apex maps and keep the newest version; map archives do not
include it, so installing a map never replaces your companion.

Launch from the console:

```text
map mp_thermal_station
```

Adds the 4,628 Apex placements the world budget had left out as native props, among them 4,013 grass, plant and tree pieces, with their shadows baked into the lighting; 615 solid props collide with their drawn shape, 456 cast real-time sun shadows and 607 small ones fade with distance. Reflection cubemaps captured in game give metal, glass and wet surfaces something to reflect, and the sun-shadow geometry is welded, so the map file is about 25 MB smaller. Tested on Northstar 1.31.14 in single-client PS/FFA: all 4 spawns clear and supported, both teams, weapon fire, postmatch lobby and stock/map reload; this is not multiplayer certification. Requires ApexMaps.UI 0.2.1.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
