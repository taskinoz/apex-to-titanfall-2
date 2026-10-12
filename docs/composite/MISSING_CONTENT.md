# Drop-Off 0.6.0 preview omissions

This inventory accounts for all 8,356 source static placements. The
local origin filter contains 6,472; it is a conversion
selection policy, not a statement about Apex's native playable bounds.

| Static placement status | Count |
| --- | ---: |
| Included | 4,264 |
| Native all-visible draw budget | 2,051 |
| Excluded remote origin / menu or backdrop region | 1,884 |
| Asset not recovered | 147 |
| Detached wind shield at reported floating geometry location; removed with collider | 1 |
| Orphan lamp removed with missing wind shield attachment | 1 |
| No rendered sections after atmosphere / glow filters | 8 |

Budget exclusions are recoverable source assets, but adding them indiscriminately
can overflow native all-visible draw submission. Lower author LODs and spatial
visibility would allow further recovery. No placements are silently relabeled
as successfully converted. The CSV lists all exclusions with source positions.

## Collision

14 selected solid placements have no decoded source collision
shape: small cable stoppers, puddle decals and bamboo. `missing-collision.json`
names each source owner. Unsuitable guessed bounding boxes were not added.
World BVH and successfully recovered IRPS/BVH prop shapes are included.

## Materials with fallback

Counts are rendered source triangles; zero-count entries are unused catalogue
names. Missing entries use a plain neutral material, not an unrelated atlas.

| Source material | Triangles |
| --- | ---: |
| `world/dev/dev_gray_512` | 0 |
| `world/metal/metal_painted_white_01` | 0 |
| `world/decal/signage_building_02` | 564 |
| `empty_model` | 1 |
| `composite_sky` | 0 |

## Behaviour and visual approximations

Source scripted dynamic props, eight doors, movers/train nodes, audio,
particles, source UI surfaces and Apex arena gameplay are not reproduced. Inline
brush geometry is fixed; conditional or animated states are not simulated.
No CTF/Hardpoint objectives, Fastball setup or AI navigation is provided.
Intro and evac are disabled. Only the two source zipline pairs are converted to native Titanfall ziplines.
Temporary arena spawn covers are omitted; permanent room and roof clips remain. Source safety
volumes include 21 out-of-bounds areas and five hurt volumes.

The source photographic sky uses an approximate sphere mapping. Primary native
PBR channels and alpha masks are recovered, but vertex colours, layered materials,
animated displays and full source reflections remain incomplete. Texture caps
and lower author LODs visibly reduce detail. Lightmaps are coarse, spot lights
are point approximations and there is no bounced GI. Sixty local source lights
are selected from hundreds rather than preserving every light.
The reported development door cover is removed. The reported roof/window
opening still needs identification; no speculative pane has been added.

The package deliberately uses conservative all-visible cells. This avoids known
angular culling problems but needs performance testing with multiple players and
combat effects. Binary capacity checks do not prove stable frame times.
See `validation.json` for which runtime checks actually ran on this build.
