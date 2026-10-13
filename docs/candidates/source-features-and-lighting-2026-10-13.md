# Source features and lighting in 0.2.0

This update addresses the missing Firing Range water, supply crates and ziplines,
and missing local illumination in Party Crasher and Overflow. Previous 0.1.0
player ZIPs and comparison snapshots are retained as rollback evidence.

## Firing Range

The source has 14 `zipline` endpoints forming seven linked routes. The original
adapter looked exclusively for `zipline_end` destinations and missed these.
The adapter now resolves either endpoint class by its original link GUID.
Fourteen native rope entities retain the source endpoint coordinates after the
documented map offset. Native endpoint/route counts are checked; full traversal
of every route with player input is not established.

Twenty supply bins are authored `prop_dynamic_lightweight` entities rather than
static-prop records. They are now baked as closed scenery at source transforms.
Weapon-lane bins retain source LOD2; more distant bins use source LOD3. Source
collision is decoded and appended without guessed bounding boxes. All 20 have
native collision contacts. Loot highlighting and Apex loot interaction are
omitted. The update adds 54,287 triangles including water, reaching 2,878,872
padded indices (91.51% of the measured 3,145,728 per-view capacity), with 168
static batch runs. Adding these bins creates no dynamic prop entities.

The ocean is a material section of `canyonlands_hu_se` in the separate 3D sky.
Its VG has valid triangle-list vertices/indices but no strip table. The older
decoder rejected it; the updated decoder validates and reads the direct list.
The water section is reanchored and clipped into a non-solid native backdrop,
with source sky-water textures, adapted colour and sea level -1600 beneath the
training floors. It extends behind the photographic sky sphere so a smaller
square edge is not exposed at the horizon. This is a visual approximation;
the original wave, reflection and water rendering system is not reproduced.
Gameplay collision has no solid ocean platform. Supply bins have a separate
dynamic-source placement ledger.

## Source fixture lighting

The old 56-fixture selection omitted most interior and street lights. Party
Crasher has 865 in-region source lights; Overflow has 315. The existing 56
native RTL fixtures remain, and the other 809 / 259 contribute static diffuse
radiance to source-positioned receiver charts and moving-character SH.

The new baker retains source colours, source spotlight directions/cones,
distance attenuation and source shadow flags. Shadowed fixtures ray-test the
recovered scene. Surface padding stays within each triangle's own chart. Probe
updates affect constant SH terms; native RTL indices and the world-light slot
table are unchanged. Additional fixtures lack independent native specular
slots; these are direct diffuse approximations rather than full Apex lights
or bounced global illumination. No global brightness multiplier substitutes
for the missing fixtures.

The focused regressions decode every vista triangle, reject an out-of-range
index, verify spotlight direction, and exercise more than 63 static fixtures
without overflowing native light slots. Independent native binary checks and
exact-build runtime receipts are recorded in each `port-0.2.0` directory.
Single-client success does not erase the earlier repeated-mode-change crash;
the previews remain experimental and should be restarted between maps.

## Delivery checks

Each exact 0.2.0 payload passes 16 binary checks, fresh-process PS and FFA
spawn/floor checks, a postmatch return to lobby and a stock-map reload. Native
captures have no reported script errors or crash dumps. Six focused Python
regressions pass using the isolated build root. These are one-client checks;
multiplayer load and all seven zipline traversals remain untested.

The saved site adds eight matched views under `2026-10-13-source-features-lighting`.
All 166 published PNGs match their recorded hashes. Earlier preview snapshots,
and the complete Phase Runner / Drop-Off catalogue entries, remain unchanged.
Clean player ZIPs contain the mod runtime, installation notes and one native
screenshot; technical ledgers stay outside the player distributions.
