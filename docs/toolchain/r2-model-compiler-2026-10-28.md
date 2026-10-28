# r2-model-compiler assessment for the anniversary release

Reviewed [taskinoz/r2-model-compiler v0.5.0](https://github.com/taskinoz/r2-model-compiler/releases/tag/v0.5.0)
against Gravemind `projects/r2-model-compiler/index.md` revision 21. Later sections
of that article supersede its early implementation status. This compiler now
produces native Titanfall 2 v53 MDLs from QC and SMD/DMX, including static props
and collision; it is no longer just a format investigation.

The official Windows archive SHA-256 is
`348bafa38e645d20d240fc1f4478340781206d6bc5b214f8548a14cba43375ab`.
It remains in ignored local tools storage. The supplied static-box example
compiled successfully: 24 vertices, 12 triangles, one bone, one sequence and
one collision piece, a 5,550-byte MDL with zero warnings. This is a compilation
smoke check, not a new native-game validation of the compiler's full feature set.
Upstream publishes its own broader comparison and regression evidence.

No anniversary map model was rebuilt with it. The original five ports currently
bake recovered scenery into world geometry. Moving selected scenery to native
static props could free world indices, but requires a separate conversion step:
recover each model's transform and vertex attributes, bind compatible native
materials, preserve collisions and LODs, serialize the Titanfall static-prop game
lump correctly, then test visibility, lighting and physical traversal in-game.
A working MDL compiler alone does not complete that process.

The recently documented native static-prop visibility namespace is derived from
`(LEVEL_INFO.firstSkyMeshIndex + 63) & ~63`; do not assume it is simply
`world.meshCount + propIndex`. Verify against the current native reader and
MRVN-Radiant work before implementing this migration. Static prop rendering has
different limits from the world index-copy path. Leave headroom in both paths
and in gameplay entity pools; neither limit is a universal map object count.

The anniversary candidate therefore preserves the accepted geometry and model
layout. Compiler integration is a useful next development branch, with per-model
native material, collision and visibility probes, rather than a prerequisite
for repackaging the currently tested maps.
