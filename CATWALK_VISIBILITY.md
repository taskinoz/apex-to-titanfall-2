# Phase Runner visibility — 0.1.37

The rejected 0.1.35 connected-portal experiment remains removed. The
cell, portal and occlusion records are the exact 0.1.34/0.1.36 records.
The decorative sky still covers the full supported camera domain.

In 0.1.36, nearby meshes received guards for the tunnel route they
intersected. The user reports objects on the far side can still disappear
while looking across the map from inside either pipe. Version 0.1.37 gives
every visibility object a bound containing the union of both conservative
tunnel camera envelopes. Each envelope contains standing player eyes
throughout its route; tree parents are rebuilt from the enlarged bounds.
Every mesh retains an exact bound for its real geometry. This addresses
the distant-object case without adding portals or hiding the sky.

All 4,586 meshes are referenced once. Compatible vertex/material batches
from 0.1.36 are retained, and unrelated rendered triangle corner data,
material bindings and lightmaps remain exact. Both old paths are replaced
by lit catwalks. Native paired-index padding uses 2,652,150 of 3,145,728
indices, leaving 15.69% headroom. No unrelated surface detail is removed.

Nine regressions check native ranges, winding, mesh references, real bounds,
all tunnel camera positions and view angles, preserved portal records and
untouched BSP payloads. Native dedicated-server loading succeeds. Client
rendering and frame rate need an in-game check: conservative guards can
increase draw work inside and between the tunnel routes. Full texture
mips remain resident, and the renamed STBSP retains its existing content.
