# Thunderdome 0.4.2 for Northstar

Close Titanfall 2. Move the old map folder to a backup outside `mods/`, then
extract `ArenaThunderdome` into `Titanfall2/R2Northstar/mods/`. Replace the old folder
rather than merging; obsolete atlas files must be removed. Enable it in
Northstar's mod menu and restart. Disable any older copy of the same map.
Every player needs the same mod version.

The loading artwork and minimap come from the shared `ApexMaps.UI` companion,
a separate download (`ApexMaps.UI-<version>-Northstar.zip`). Install it once
for all five Apex maps and keep the newest version; map archives do not
include it, so installing a map never replaces your companion.

Launch from the console:

```text
map mp_thunderdome
```

Standalone: the map now ships as its own level pack instead of mounting on the stock Coliseum level pack, so it loads only its own assets and no longer loads the packs of every other installed Apex port (with eight ports installed that ran the game out of memory). Includes 0.4.1, rebuilt from the November 2026 Apex update: the solar water heaters and stasis lights use Apex's new, more detailed models, and the screen tower, liquid tank, roof tanks, lockers and alien trees take their updated textures. Includes 0.4.0's prop sun shadows, reflection cubemaps and welded sun-shadow geometry. Tested on Northstar 1.31.14 in single-client PS/FFA: all 96 spawns clear and supported, both teams, weapon fire, postmatch lobby and stock/map reload; this is not multiplayer certification. Requires ApexMaps.UI 0.3.0.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
