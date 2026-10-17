# Current-build image refresh — 18 October 2026

The default comparison galleries and all five map cards now use a new
`2026-10-18-release-refresh` snapshot. Earlier snapshots remain available.

| Map | Native build | Matched views |
| --- | --- | ---: |
| Drop-Off | 0.10.1 | 12 |
| Phase Runner | 1.7.2 | 11 |
| Overflow | 0.4.1 | 8 |
| Party Crasher | 0.6.4 | 15 |
| Firing Range | 0.5.1 | 7 |

Every Titanfall image was recaptured from the current mod. Matching Apex
references retain their original images, hashes and capture dates; the new
Party Crasher Northstar-screen viewpoint has a fresh matching R5R capture.
Party Crasher's current gallery combines the previously separate arena,
street, boundary and rooftop views, then adds the billboard view.

The harness verified the mounted BSP, STBSP and RPak hashes, active map, camera
position, angles, live test player and paired image dimensions. Each map ran in
a separate owned Northstar process. Native survey logs were clean. The first
Drop-Off view was retaken after its opening mode announcement cleared.

These are diagnostic camera surveys. Native boundary and hurt triggers were
removed only in the owned runtime to permit exterior viewpoints; the map files
and installed player mods were unchanged. The new accepted R5R screen capture
kept its safety triggers intact. An earlier discarded R5R attempt showed that
destroying a trigger still referenced by a source script can raise an invalid
`ContainsPoint` error. The accepted image comes from a fresh source launch.
The photographs do not establish multiplayer performance, collision coverage
or game-mode stability.

`refresh_site_captures.py` prepares the routes, captures the current builds and
exports the static site. `verify_site_refresh.py` checks the public image hashes
and dimensions, current build/pose metadata, private-data exclusions and the
embedded portable catalogue. Public verification results are retained beside
this document. Full private capture states and mount hashes stay under
`output/site-refresh-2026-10-18/` and do not enter the website.
