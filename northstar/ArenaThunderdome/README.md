# Thunderdome 0.3.0 for Northstar

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

Rebuilds the arena scenery as 6,757 native props from the Apex models, with their original materials, foliage and baked shadows; 3,740 solid props (rocks, buildings, crates, the skull) collide with their drawn shape. The skull, holograms and red seams are coloured again. Visibility cells and fade distances for small props reduce what is drawn when looking across the arena, and collision data is welded, so the map is 170 MB smaller. Tested on Northstar 1.31.14 in single-client PS/FFA: all 96 spawns clear/supported, both teams, weapon fire, postmatch lobby and stock/map reload. Glowing surfaces are lit rather than emissive, the animated stadium screens are absent, and AI is incomplete. CTF is unsupported (missing flag objectives); this is not multiplayer certification. Requires ApexMaps.UI 0.2.1.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
