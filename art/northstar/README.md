# Northstar banner artwork

Party Crasher also has a landscape screen design:
`party-crasher-northstar-screen-v1.png`. Its generation prompt and integration
notes are in `party-crasher-screen-v1.md`.

`northstar-banner-v1.png` is the project banner texture. It was made with the
built-in imagegen tool using the official Northstar launcher icon as a visual
reference. It is an opaque, flat graphic, not a screenshot of either game.

Reference: [R2Northstar/NorthstarLauncher `ns_icon.ico`](https://github.com/R2Northstar/NorthstarLauncher/blob/f698c8a90b9d3d6d1740eda57101db7011d051d2/primedev/primelauncher/ns_icon.ico).
The reference is covered by the upstream MIT license, reproduced in
`NORTHSTAR-LICENSE.txt`. This project is a community map conversion and does
not imply Northstar or Respawn endorsement.

Generation prompt: “Production flat texture for a vertical industrial arena
banner in Titanfall 2. Official Northstar emblem reference; preserve the white
titan silhouette and purple/navy hexagonal badge. One front-facing 1:2 banner,
edge-to-edge, no scene, mounting hardware, folds, perspective or baked lighting.
Large emblem, exact bold white text NORTHSTAR, navy background with purple and
cyan industrial geometric accents, restrained chevrons and subtle fabric grain.
Generous safe margins, no additional text, opaque background.”

The material builder compresses it to BC7 sRGB with a full mip chain. The
existing banner geometry and collision are preserved; its atlas UVs are
remapped to display one complete graphic per face.
