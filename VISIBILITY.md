# Phase Runner visibility — 0.1.40

The 0.1.39 camera guards remain intact. The next client report establishes that
catwalks, railings and crates are invisible at every angle despite collision.
Read-only engine inspection now identifies the independent 2,048 draw-batch
limit. The old mesh order has 3,777 material/channel runs. Version 0.1.40 groups
the same records into 454 runs and remaps visibility IDs to keep each reference
attached to its original geometry. See WORLD_BATCH_ORDER.md for native evidence,
preservation checks and the remaining client-verification limitation.

The earlier camera-guard repair is documented below for provenance.

The rejected 0.1.35 connected-portal experiment remains removed. The
cell, portal and occlusion records are the exact 0.1.34/0.1.36 records.
The decorative sky still covers the full supported camera domain.

The user confirms character lighting, loading artwork and map names work in
0.1.38, but reports missing tunnels, small rocks, vegetation and crates. Their
triangles are still present. Version 0.1.38 added only character probe data;
its render and visibility payloads are byte-identical to 0.1.37. The latest
client log has no missing-material or index-overflow diagnostic. The precise
running-client failure has not been conclusively measured.

Version 0.1.37 guarded the union of both tunnel envelopes, which does not
protect all outdoor and airborne camera positions. Version 0.1.39 changes
only CELL_AABB_NODES and OBJ_REF_BOUNDS to cover the supported camera domain:
X/Y [-12288,12288], Z [-4096,4096], plus each object's actual geometry. A
shallow root and 18 leaves retain the exact reference order, with at most
255 references per leaf. Every mesh retains its exact geometric MESH_BOUNDS.

Read-only disassembly of client.dll+0x2e9983 shows that a camera inside its
guard bypasses projected silhouette clipping. Independent tests check this
condition and view-plane support for 38 camera positions and 56 orientations
per position, including reported stairs, rocks, crates and pipe locations.
Native pending-node/count limits and complete reference ownership are checked.

All 4,586 meshes are referenced once. Compatible vertex/material batches
from 0.1.36 are retained, and unrelated rendered triangle corner data,
material bindings and lightmaps remain exact. Both old paths are replaced
by lit catwalks. Native paired-index padding uses 2,652,150 of 3,145,728
indices, leaving 15.69% headroom. No unrelated surface detail is removed.

Five regressions check native ranges, reference ownership, playable camera
positions and view angles, every untouched BSP payload and preserved assets.
Character lighting, collision, catwalks/rails, lights, lightmaps, PBR materials,
sky, loading artwork, translations and STBSP remain exact from 0.1.38.
Client rendering and frame rate need an in-game check: these conservative
guards reduce access-path selectivity inside the supported camera area.
CPU bounds tests alone cannot prove the running client's final GPU draws.
The full 0.1.38 backup/archive and older 0.1.36 paths are preserved.
