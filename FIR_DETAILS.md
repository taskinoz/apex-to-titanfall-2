# Phase Runner 0.1.46 — twenty full-sized fir trees

The acacias added in 0.1.45 were small authored plants, approximately 107 units
tall before placement. They were correctly decoded, but unsuitable for the
requested tree pass. This version replaces those twenty additions with twenty
original `tree_fir_large_arenas_01` placements. Their rendered heights range
from 814 to 1,486 units, with substantial needle canopies.

Positions, rotations, scales and green or snowy skins come from the source map.
Each tree uses the fixed authored LOD 2 mesh: 62 trunk triangles and 952 canopy
triangles. The twenty trees add 20,280 triangles over the working 0.1.44 scene.
One candidate intersecting an existing rock is excluded. Existing ceiling vents
and unrelated props are unchanged; the previously proposed vent additions
remain omitted.

Needles use native Titanfall world cutout materials, two-sided leaf cards and
local shader/depth dependencies. Recovered opacity masks are combined with the
source albedo alpha. Texture mipmaps preserve cutout coverage to reduce needle
loss at a distance. Bark uses recovered PBR channels; absent leaf gloss/specular
channels receive a flat gloss or neutral dielectric fallback. All added textures
are resident.

Trees receive baked sun and sky lighting while existing lightmaps and character
lighting remain intact. Original IRPS trunk/root collision is restored, with no
solid canopy boxes. Visibility, catwalks, loading screen, translations, and prior
art repairs are preserved. No connected portals or distance-based tree LOD
switching are introduced.

The world draw audit reports 972,628 triangles, 2,924,184 padded indices out of
3,145,728 (92.96%), and 479 static batches. The release remains below the 95%
index and fewer-than-512 batch policy.

Eleven regression checks cover preservation of existing geometry, physics,
materials and lightmaps; source placement and UV recovery; full-sized canopies;
native cutout shader dependencies; alpha mip coverage; visibility; streaming
metadata; and rendering capacity. Client map/lobby/map loading and 40 new trunk
traces must pass before installation.

Limitations: no wind animation, and no opacity-aware static canopy shadow bake.
Trunks cast shadows; leaf-card rectangles are excluded from the offline shadow
bake. Automated client loading and collision checks do not verify appearance.

Build evidence is in `trees.json` and `runtime-validation.json` in the package.
The full prior 0.1.45 package is backed up under
`output/installed-backups/PhaseRunner.Preview-0.1.45-before-firs`.
