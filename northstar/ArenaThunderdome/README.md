# Thunderdome 0.2.0 for Northstar

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

Repairs collision on 5,318 visible physical props, including 14 previously skipped bridge components, using their drawn surfaces instead of mismatched source hulls. Restores 23 material entries with original Apex colour, normal, gloss and specular maps. Geometry, lighting, safety volumes and the shared UI atlas are preserved. Tested on Northstar 1.31.14 in single-client PS/FFA: all 88 spawns clear/supported, both teams, weapon fire, postmatch lobby and stock/map reload. Some layered/translucent materials, authored paint/emission constants, omitted scenery and AI remain incomplete. CTF is unsupported (missing flag objectives); this is not multiplayer certification. Requires ApexMaps.UI 0.2.1.

`screenshot.png` is an in-game capture of this port. Original map assets remain
the work of their respective creators.
