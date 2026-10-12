# Apex-to-Titanfall collision decoding and ownership

Scope: tested source world BVH, inline STAR and IRPS/embedded-model collision;
target native brush/triangle grid. Heightfields and complete contents equivalence
are not implemented as general conversion backends.

## Decode the source collision frame correctly

An Apex BVH node is `<24h4I>` (64 bytes). Bounds are grouped by axis: four minima
then four maxima for each axis. They are not four interleaved XYZ child boxes.
Child references are derived from words shifted right eight bits; contents and
type bits also occupy those words. Retain source model ranges, packed vertex
scale/offset, and `first_vertex`. The tested world uses `first_vertex=1`; omitting
it caused collision to drift from the visible surfaces.

Observed node kinds: 0 node, 1 empty, 3 compound, 4 regular triangle, 5 packed
triangle, 6 regular quad, 7 packed quad, 8 inline STAR and 9 static-prop reference.
Compound and inline blocks require their own palettes, alignment and frame.
Signed global coordinates and unsigned inline-local coordinates are different
decoders; do not merge them by convenience.

The tested PHY has a 20-byte `<5I>` header and relative-pointer IRPS graph. Root
descriptors contain four int64 relative pointers; group records are 144 bytes,
convex pieces 64. Vertices are float XYZ; face lists use signed-byte indices
terminated by -1. Validate pointers relative to their owning base, bounds and
winding, then triangulate polygon faces. Some tested RMDLs provide an embedded
BVH pointer at offset 532; this is a version-specific fallback.

## Native collision representation

| Lump | Role |
| --- | --- |
| 0x55 / 0x56 | Grid and uint16 first/count cells |
| 0x57 / 0x58 | Geosets and packed bounds |
| 0x59 / 0x5A | Primitive words and bounds |
| 0x5B | Contents palette |
| 0x5C–0x5F | Brushes, plane offsets, side properties and texture vectors |
| 0x42 / 0x44 / 0x45 | Triangle words, packed nodes and 44-byte headers |
| 0x60 / 0x61 | Bevel starts and shared bevel indices |

Primitive words encode kind in the top byte, target index in bits 8–23 and
contents index in the low byte. Kind 0 is brush; `0x40` is triangle header.
Multi-primitive geosets reference a range rather than one primitive. Brushes
have six implicit axial planes plus explicit cuts/bevels; side properties matter.

Triangle headers use `<6h4i4f>` for flags, texture metadata, counts, starts,
origin and scale. Triangle words use a 10-bit base, two seven-bit deltas and
orientation bits. The 96-triangle grouping is a project choice; the helper
supports up to 300. Centers and extents must each fit signed16. Clipping vertex
coordinates to ±32760 does not guarantee representable bounding extents.

## Solidity and ownership

Use brushes for closed convex solids. Concave rocks, tunnels, ring frames and
rails need triangle surfaces or deliberate compound decomposition. A whole-prop
AABB can fill a tunnel and create invisible barriers. Foliage cards should not
become solid automatically. Retain source collision independent of render LOD.

A static prop can already own collision in the source world BVH even if its
separate PHY is missing or its visual is omitted. Check decoded owner IDs and
world bounds before adding another collider. Drop-Off containers 5287 and 5288
were invisible while their higher-detail world collision worked. Restoring their
LOD3 visuals required no collider changes; the visual top differs slightly from
the higher-fidelity collision, a documented LOD approximation.

Distinguish stored from active collision. Phase Runner's baseline stores 7,654
brushes and 25,948 triangle headers, but its active grid contains 7,134 brushes
and 25,866 headers. Disabled caps can remain serialized without being active.
Apply the current tunnel/catwalk/tree overlays to historical ownership ledgers.

## Tunnel barriers and intentional clips

Remove only identified caps intersecting a verified passage. Toolclip/nodraw
surfaces can intentionally close inaccessible rooms or roofs. In Drop-Off, north
and diagonal clips initially removed as obsolete barriers were restored after
comparison with source layout and user confirmation. A visually empty space is
not enough evidence to delete its collider.

Phase Runner needed visible ring-frame collision where an original portal PHY
represented a filled disk. Its adapted catwalk has an 80-unit deck, 71-unit
passage clearance and 42-unit rails with open entries. Native movement-hull
checks cover the route; a downward line trace alone does not prove traversability.

## Sources

`decode_collision.py`, `read_prop_physics.py`, `native_triangle_collision.py`,
`rebuild_complete_collision.py`, `repair_tunnel_passages.py`,
`docs/conversion/tunnel-collision-repair.json`, `docs/conversion/catwalks.json`,
`docs/conversion/collision-ownership-baseline.json`,
`docs/dropoff-source-layout-2026-10-07.md`, and Drop-Off's 0.6.0 repair receipt.
