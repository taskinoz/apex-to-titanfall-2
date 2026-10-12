# Recoverable additions for the working 0.1.44 build

This is a read-only proposal. No map geometry, assets or installed files were changed.
The installed and workspace BSPs have matching measured renderer budgets.

The current map contains 952,348 world triangles and uses 2,863,326 of 3,145,728
native world indices (91.02%). There are approximately 94,134 triangles of raw
index capacity left before mesh padding. Retaining the existing 5% reserve leaves
approximately 41,705 triangles before padding. Aim for 35,000–40,000 added
triangles and re-audit the finished BSP. Triangle count, material/lightmap batches
and texture memory matter; there is no single remaining object-count allowance.

There are 10,971 omitted arena static placements across 68 model types:
9,557 vegetation and 1,414 other placements. Compiled geometry is present for
10,603 placements across 58 model types. These source meshes can be recovered;
materials, alpha, collision and loading still require staging and validation.

## Suggested next detail batch

| Objects | Placements | Added source triangles | Source detail |
| --- | ---: | ---: | --- |
| Warning/service plates and directional signs | 232 | 4,364 | LOD 0 |
| Ceiling vents | 34 | 3,876 | LOD 0 |
| Antennas | 6 | 1,812 | LOD 0 |
| Wall light fixtures | 6 | 936 | LOD 1 |
| Cable coils and ceiling mounts | 9 | 3,374 | LOD 1 |
| Flex-screen panels, frames and support arms | 60 | 18,072 | Panels LOD 0; frames/arms LOD 1 |
| Forklifts | 2 | 4,098 | LOD 2 |
| **Total** | **349** | **36,532** | |

This would use approximately 94.51% of the native index capacity before new mesh
padding. It references 15 distinct source material names; labelled source albedo
and normal textures are available for each. Some channels need neutral fallback
values or native alpha/emissive handling. Final lightmap layout can multiply draw
batches, so 15 materials does not guarantee 15 additional batches. The current
map has 472 static batches and the conservative build policy keeps that below
512 to allow dynamic-light splitting.

These are authored source placements, not newly invented filler. The candidate
uses fixed source detail levels; it does not require reintroducing portal culling.
Final placement, collision, shading, padded index capacity and client loading
must pass checks before installing this batch.

## Other recoverable choices

These are alternatives to parts of the batch, not a proposal to add everything
below on top of it.

| Objects | Available placements | Measured cost |
| --- | ---: | --- |
| Closed police trucks | 5 | 9,580 triangles total at LOD 2 |
| Power generators | 30 | 14,910 triangles total at LOD 3 |
| Power cells | 52 | 6,864 triangles total at LOD 2; inspect reduced detail first |
| Wall water pipes | 4 | 3,888 triangles total at LOD 1 |
| IMC monitors | 8 | 3,808 triangles total at LOD 0 |
| Columns and scaffolding tarps | 8 | 4,384 triangles total at LOD 0; 1,887 at LOD 1 |
| Static MARVIN models | 2 | 11,568 triangles total at LOD 2 |
| Small rock clusters | 527 | 288–904 triangles per placement at LOD 2, depending on model |
| Trees, moss, grass and flowers | 9,557 | Select small patches; full recovery exceeds the allowance even at the lowest source LODs |

The two lava rock clusters are 288 triangles each at LOD 2. Other cluster types
range from 440 to 904. A selected 10–15 clusters therefore costs approximately
4,400–13,560 triangles, excluding lava and mesh padding. Avoid replacing all
clusters with their coarsest LOD solely to increase the object count.

## Source gaps

Compiled geometry is absent for 368 placements. Eighteen barrels have prepared
QC source and can be investigated separately. The other 350 placements comprise
339 railing trim pieces, five small modular pipe pieces, three wire coils, two
stasis lights and one lobby MARVIN object; neither compiled geometry nor prepared
QC is currently available for those. They need another source extraction or
replacement geometry and cannot yet be costed as recovered meshes.

The audit covers omitted arena static placements. Dynamic entities and 486
placements outside the imported arena are separate inventories.

Machine-readable evidence: `logs/recoverable-prop-budget-0.1.44.json`.
Re-run with `audit_remaining_recovery_budget.py`; it only reads the map/assets
and writes its audit report.

## Tree substitutions

The user prefers trees over lesser details such as ceiling vents. These are
substitutions in the proposed next batch; the 34 omitted vents have not been
installed in 0.1.44, so omitting them does not remove current working geometry.

| Tree type | Unrecovered source placements | Selected detail | Triangles per tree |
| --- | ---: | --- | ---: |
| Small acacia 01 | 53 | LOD 1 | 289 |
| Small acacia 03 | 20 | LOD 1 | 606 |
| Large fir, both variants | 36 | LOD 2 | 1,014 |
| Yellow brush tree | 153 | LOD 1 | 858 |

All these types have compiled static geometry and recovered albedo textures.
The acacia branches and fir leaves also have recovered opacity textures. Proper
native cutout shading must preserve leaf silhouettes and avoid opaque leaf
rectangles. Trunk collision should use authored hulls rather than solid leaf
bounds. These costs refer to fixed source meshes, not runtime distance switching.

The simplest substitution is 20 small acacia 01 trees for all 34 proposed ceiling
vents: 335 new placements and 38,436 triangles for the entire detail batch.
There are authored acacia placements near the center, including source indices
12984–12987. Choose original placements after checking their ground contact.

For a mixed tree pass, omit the 34 vents and six proposed antennas, then add ten
small acacia 01 trees and five firs: 324 new placements and 38,804 triangles in
the complete batch. This fits the triangle estimate while retaining 5% native
index reserve before mesh padding. Final padded indices, lightmap/material
batches, alpha overdraw, texture memory, collision and live client loading still
require verification. Neither option is installed by this audit.
