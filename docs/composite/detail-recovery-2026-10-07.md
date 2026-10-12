# Drop-Off 0.4.0 — source props and zipline supports

Recovered 95 placements, increasing the port from 4,123 to 4,218 static objects.
Both source zipline pairs retain their endpoints and now have all four arms and
four supporting posts at their original source transforms. The four arms use
the earlier single-material SMD/QC export; the other additions use compiled VG
author LODs. No placements or old geometry were removed to make this space.

## Added content

| Model | Placements |
| --- | ---: |
| `zipline_arm` | 4 |
| `security_fence_post` | 28 |
| `box_med_cardboard_01` | 4 |
| `plastic_pallet_01` | 7 |
| `olympus_docks_gate_sign_01` | 4 |
| `wire_ground_coils_02` | 3 |
| `beacon_wire_ground_coils_02` | 13 |
| `sign_plate_c` | 20 |
| `office_keyboard_plastic` | 4 |
| `traffic_barrel_01` | 4 |
| `traffic_tube_01` | 3 |
| `traffic_cone_01` | 1 |

Every added material has source albedo available. New source albedo, normal,
gloss and specular channels are bound where exported. All textures remain
resident with the existing 1024-pixel cap; the RPak grows by about 13 MB.
The zipline-arm albedo is very dark in the source export (mean RGB about
24/20/18), explaining its dark metal appearance in native captures.

## Budget and rendering

Added 35,986 triangles. Serialized draw occupancy is 935,974 triangles, including
108 disabled start-cover slots. Native padded index use is 2,811,912 of 3,145,728
(89.4% occupied; 10.6% free). There are 333 static material-batch runs, below the
512-run project policy and the audited 2,048 native capacity. Dynamic lighting
can split batches, so these are capacity checks rather than a frame-time claim.
Only about 6,400 more triangles fit before this build's conservative 90% index
policy. Larger recovery should reduce existing geometry or use a tested native
static-model path; simply filling the hard limit risks renewed missing visuals.

## Collision and lighting

Recovered IRPS/BVH polygon surfaces are transformed with each added prop.
The arm export has no compiled collider, so it uses its exact source mesh
triangles as surface collision. This is a documented approximation and does
not introduce box-shaped obstacles. All old collision headers, triangles and
nodes retain their bytes and offsets; only additional streams and the spatial
grid change. One support trace begins inside nearby existing wall collision;
other support checks begin clear and register collision.

New 4x4 triangle charts use unused tiles in the fourth existing lightmap page.
They are ray-baked against the old scene and new objects, omitting temporary
spawn barriers as casters. Every previously used lightmap tile and all character
probes remain byte-identical. New opaque geometry enters the native shadow
mesh stream; the existing baked scene does not gain new static contact shadows
until a future full rebake.

## Verification and remaining work

All 23 regression checks passed, including exact source attachment transforms,
old collision/draw stream preservation, original lightmap tile preservation,
native buffer capacity, material dependencies and source safety entities.
Native close views cover both ends of both ropes plus the court and interior.
Runtime receipts and reload/end-state results are in
`output/composite/detail-recovery/runtime.json`.

The complete omission inventory still lists 2,098 local budget omissions,
147 placements without recovered assets, 1,884 remote/menu/backdrop placements,
one deliberately removed detached shield and eight filtered decorative objects.
The `signage_building_02` source decal remains unrecovered (564 triangles);
`empty_model` accounts for one other fallback triangle. Three catalogue fallback
names have zero rendered triangles. No unrelated atlas is substituted.

Reproduction: `recover_composite_details.py plan`, then `materials`, then
`append`; the materials step takes a mandatory snapshot and detaches files
before tools overwrite them. Restore the snapshot before reapplying. The native
verification script is `verify_composite_details_runtime.py`. Scene and physics
caches record additions for future conversion tools. 0.3.0 remains packaged
separately and installed runtime files are backed up before replacement.
