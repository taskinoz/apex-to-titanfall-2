# Phase Runner tunnel catwalks — 0.1.37

Both original traversable paths become industrial grating decks with metal
frames, cross supports, yellow posts and two-height railings. The walking
surface retains the exact old route coordinates and elevations. The deck
is 80 units wide; rails are 22 and 42 units above it. Posts are at most
96 units apart, and the first/last 64 units remain open for entry and exit.

The old paths' 5,796 triangles are replaced by 14,744 catwalk triangles.
Each new collision triangle exactly matches a rendered triangle. The 61
old path collision headers are removed from the active grid; all unrelated
collider records and active ownership remain intact. Original buildings,
pipes, rocks, props, sky and materials retain their existing data.

The decks use recovered grating and metal PBR materials. One additional
1,024-square native lightmap page is baked against the full existing scene
using the existing sun/sky and 30 local lights. The previous two lightmap
pages and existing light records remain byte-identical. New shadow faces
replace the original paths' shadow faces.

Fresh native checks pass: 102 floor contacts, 204 player-sized railing
contacts, 1,449 short route sweeps in both directions using 18-unit step
clearance, and 1,449 floor contacts along those sweeps. The existing 927
world collision checks also pass. Nine independent regressions verify
geometry, untouched assets, collision, visibility, lightmaps, map-name
resources and the complete old-build backup. In-game appearance still
needs a client check.

The full 0.1.36 mod, including the original paths, is retained under
`output/installed-backups/PhaseRunner.Preview-0.1.36-before-catwalks` and in
`output/PhaseRunner.Preview-0.1.36.zip`.
