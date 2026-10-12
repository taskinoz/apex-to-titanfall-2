# Titanfall 2 and Apex map binary formats

Scope: the tested Apex rBSP 47 inputs and Titanfall 2 rBSP 37 target. Serialized
little-endian layouts are not runtime engine structures. Dispatch on the file,
lump and game-lump versions before decoding; preserve unknown fields raw.

## BSP container and entity sources

The observed header is 2,064 bytes: `<4s3I` followed by 128 `<4I` lump descriptors.
Each descriptor holds offset, byte length, lump version and fourCC. Input maps can
have external `.bsp.XXXX.bsp_lump` payloads. Resolve external data before checking
stride and references, and record where each payload came from.

Changing the BSP version number is insufficient. Apex slots 0x12–0x16 carry
world BVH/packed-vertex/heightfield data without direct equivalents in the target
branch. Apex 0x2B/0x2C are not the target texture-string lumps. Matching record
sizes still require semantic and index validation.

Read the main entity lump and all available external entity partitions, including
environment, script, effects, sound and spawn files. Preserve original text,
duplicate keys, source IDs and partition provenance. Static props are principally
in `GAME_LUMP.sprp`, not just an `.ent` model list. Do not assume all placements
moved into an RPak. Geometry, placements and behavior are separate sources.

`GAME_LUMP` embedded payload addresses are absolute file offsets. Repacking the
outer BSP requires relocation of these addresses; copying the old directory
into a compacted container can leave invalid pointers. The project aligns output
lumps to 16 bytes, a writer choice distinct from an engine capacity.

## Observed serialized records

| Record | Size | Important fields or interpretation |
| --- | ---: | --- |
| Lump descriptor | 16 | Four uint32 fields |
| Plane | 16 | Float XYZ normal plus distance |
| Apex BVH node | 64 | `<24h4I>`; axis-grouped bounds |
| Native lit-bump vertex | 44 | Position/normal references, albedo UV, color, lighting fields, packed tangent |
| Native mesh | 28 | Index start, uint16 triangle/local-vertex fields, material-sort reference, flags |
| Native material sort | 12 | Texture/lightmap/cubemap IDs, last local vertex, global vertex base |
| Mesh bounds / object-reference bounds | 32 | Native bounding data |
| Native cell node | 32 | Bounds, uint8 child/direct-reference counts, uint16 ranges |
| Collision grid cell | 4 | uint16 first-geoset/count |
| Collision geoset | 8 | Group/count and primitive-or-range word |
| Packed collision bounds | 16 | Signed16 center and extent triples plus flags |
| Collision brush | 32 | Center/extents, byte cut/bevel counts, ID and plane base |
| Triangle collision header | 44 | `<6h4i4f>` |
| Shadow mesh | 12 | Vertex base, triangle count, opacity/material-sort information |
| Character light probe | 48 | Coefficients, visibility, four light references, reserved data |
| Probe reference / parent | 20 / 28 | Spatial reference and KD access ranges |
| Tested `sprp` version-13 placement | 64 | `<7fH2B2H4f4b4B2H>` |
| STBSP material / column record | 24 / 24 | Name/GUID linkage; payload/coverage/bounds |

These sizes come from `docs/conversion/respawn_conversion_layouts.h` with static
assertions and `binary-layouts.json`. Drop-Off reports game-lump version 50;
do not reinterpret it blindly using Phase Runner's version-13 placement schema.
Retain the appropriate parser and source map's version metadata.

## Compiled model recovery

RMDL/VG/PHY can exist even when QC/SMD exports are absent. The tested VG header
is 160 bytes, magic `0x47567430`, version 1, with eighteen uint64 offset/count
values starting at byte 16. Mesh records are 72 bytes (`<18I`), LOD records eight
bytes (`<2hf`). Vertex flags and stride determine float versus packed positions.
Skinned flags `0x5000` require skeleton processing outside this static decoder.

Retain RMDL skin and submesh material assignments. Resolve OBJ negative indices
against each array length at the face being read, not the completed file.
The extraction pipeline's UV inversion and triangle order `[0,2,1]` must be
applied once, followed by winding, normal and tangent-handedness checks.

For the tested sources, XYZ axes are unchanged. Phase Runner is translated by
subtracting `[26000,19000,0]`; Drop-Off does not use that recentering. Apply a
map's transform once to geometry, collision, lights, bounds, probes and entities.
The project maps parser angle components to native pitch/yaw/roll in the tested
ordering; do not infer an XYZ swap from parser field names or culling symptoms.

## Sources

`docs/conversion/binary-layouts.json`, `docs/composite/binary-layouts.json`,
`docs/conversion/respawn_conversion_layouts.h`, `read_vg_static.py`,
`stage_prop_geometry.py`, `compact_preview_bsp.py`, and both conversion guides.
Use these versioned definitions rather than treating the table as universal.
