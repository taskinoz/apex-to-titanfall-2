# Phase Runner 0.1.45 — twenty acacia trees

Restores twenty omitted `tree_acacia_small_01` placements around the middle of
the map. The positions, rotations, scales and skins come from the original map.
The trees use authored LOD 1 meshes with 289 triangles each, adding 5,780 world
triangles. Existing objects and materials are preserved. Proposed ceiling vents
are omitted from this pass.

The build retains the working visibility scheme, catwalks, loading screen,
translations, character lighting and previous art fixes. Existing lightmap data
is preserved; new trees receive baked sun/sky lighting. The trunks use the
original embedded BVH physics surfaces, without solid boxes around the canopy.
One candidate that intersects an existing rock is excluded in favour of another
original tree placement.

Leaves use Titanfall's native world cutout shader and its native depth passes,
with recovered albedo alpha multiplied by the recovered opacity mask. All leaf
shader bytecode and pass dependencies are embedded in the tree asset package
under unique identifiers. Leaf cards render from both sides. Bark uses recovered
PBR channels; snow bark uses its primary recovered layer, and missing leaf
specular uses a neutral dielectric value.

The native world draw audit reports 958,128 triangles, 2,880,666 padded indices
out of 3,145,728 (91.57%), and 475 static batches. This remains within the 95%
index and fewer-than-512 static-batch build policy. No connected portals are
introduced.

Nine regression checks cover scene/material/lightmap preservation, source
positions and UVs, exact source trunk physics, native leaf shader bytecode and
dependencies, opacity masks, visibility, render capacity and streaming metadata.
Client map/lobby/map loading and forty new trunk traces must pass before release.

Limitations: the recovered trees use fixed detail and have no wind animation.
Trunks cast world shadows; opaque leaf-card rectangles are excluded from the
offline shadow bake. A full opacity-aware static canopy shadow bake is deferred.
Actual leaf appearance remains subject to in-game visual review.

Build evidence: `trees.json` and `runtime-validation.json` in the package.
The complete working 0.1.44 package is retained under
`output/installed-backups/PhaseRunner.Preview-0.1.44-before-trees`.
