# Thunderdome 0.2.0 — collision and original PBR materials

The 0.1.1 release missed collision on 225 drawn solid props and skipped 14 bridge
components because their source solid mode was `SOLID_BSP` (1). Other props used
full-detail colliders against coarse render meshes. The repair replaces active
prop collision with 807,437 verified visible faces for 5,318 physical placements.
Nonphysical foliage and backdrop remain nonphysical. Existing world collision,
rendering, lighting, safety volumes and gameplay scripts are preserved.

23 material entries covering 76,843 triangles now use original Apex colour,
normal, gloss and specular maps from the shared retail packs. Ten numeric
material names were resolved by exact source GUID. 74 unique resident textures
are added; original materials outside the repair and existing textures compare
identically. The shared UI atlas and load ordering are unchanged.

## Validation

- Isolated Northstar 1.31.14; mounted payload hashes checked.
- All 88 live spawns clear and supported in both PS and FFA; both team starts,
  weapon fire, postmatch lobby, stock Coliseum and Thunderdome reload pass.
- All 14 bridge samples hit collision. Of 200 matched contact rays, any hit
  improves from 188 to 200; contacts within eight units improve from 119 to 138.
  Start-solid results reduce from eight to one. Overlapping surfaces can stop a
  ray before its intended face: these counts do not certify all movement.
- Eight existing collision/material regression tests pass. Binary checks verify
  unchanged render/lightmap/entity data and relocated game-lump pointers.
- Native matched screenshots: [centre](centre.png), [west](west-start.png),
  [overview](overview-south.png), [user view](user-view.png).

## Remaining work and failed experiments

Eleven fallback entries remain, including layered ground/trim materials,
translucent coverage, decals, exhaust/objective emission, `_default`, and a
zero-triangle sky alias. Retail DXIL shaders lack RDEF reflection data; the
existing SM5 reader cannot recover their paint/emission constants. Neutral
tints remain rather than guessed values. Omitted scenery, ground/backdrop gaps,
AI navigation and source gameplay behavior remain incomplete. Geometry stays
at 2,974,398 / 3,145,728 padded world indices (94.55%); no scenery is added.

An extra CTF trial found missing flag objectives and later stalled with a server
index `3` error. It is not supported or certified. Fresh PS/FFA acceptance passed
after restarting the isolated game. No multiplayer/performance certification is
claimed.

## Reproduce and rollback

`repair_thunderdome.py` provides staging, shared-material/shader export,
collision construction, PBR conversion, offline verification, native probes,
acceptance and player packaging. The staging action verifies the locked 0.1.1
archive. Source geometry must match actual native faces before collision can
activate; writes detach hardlinks. Keep `APEX_PORT_WORK` pointing at the current
arena work root and the isolated `R2Anniversary14` harness running for native
checks. Binary inputs are local, not downloaded automatically.

The immutable published 0.1.1 archive is retained, along with an extracted
baseline in `output/thunderdome-repair-2026-10-29/baseline/`. The 0.2.0 ZIP is a
new local player download; this repair does not modify published release assets
or the Thunderstore catalog. Native evidence and exact runtime hashes are in
[validation.json](validation.json); collision ownership and deferred materials
are in the accompanying repair ledgers.
