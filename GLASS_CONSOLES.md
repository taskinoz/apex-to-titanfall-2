# Phase Runner 0.1.42: truck and console glass

The truck windows and the computer consoles in both side buildings now use
Titanfall 2's transparent world-material pass. This restores 394 existing
surfaces' material bindings: 82 truck window faces, 72 cracked bridge-glass
faces and 240 dark console-glass faces. The console glass previously sampled
the console body atlas, causing the misplaced panel details in the screenshots.

The material uses Homestead's original world-glass shader bytecode and input
flags, with the recovered Apex albedo, normal, gloss, specular and opacity
textures. Truck glass has a 0.35 opacity multiplier. Console materials use
0.60 and 0.42. Glass is visible from both sides and tests against the existing
depth buffer without writing depth. Native opaque and transparent mesh ranges
are separated, preserving the working draw-batch ordering and full camera
domain. All 15 new texture assets remain resident.

No positions, UVs, tangents, normals, lightmaps, player probes or collision
data changed. The 394 glass faces are removed from opaque live shadow casters.
The existing baked lighting remains intact. The Apex blended dark glass uses
its recovered primary layer; this does not reproduce its full two-layer shader.

Six exact preservation, material, shader, visibility, budget and shadow tests
pass, alongside three installed-engine capacity tests. The isolated native
server loaded the candidate and passed all 4,134 traversal and collision checks.
Client GPU appearance and performance still need an in-game check.

Restart Northstar and load `map mp_phase_runner`. Check the truck near Nessie,
then the consoles near -6080 -1530 -838 and 6284 -1417 -838.

Prior full snapshot:
`output/installed-backups/PhaseRunner.Preview-0.1.41-before-glass-console`

Prior archive: `output/PhaseRunner.Preview-0.1.41.zip`.
All older snapshots remain available.
