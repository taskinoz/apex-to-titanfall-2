# Party Crasher 0.6.4

Adds a new Northstar billboard image to the curved Oasis screen, matching the Drop-Off banner artwork. Geometry, collision, lighting and gameplay are unchanged from 0.6.3.

The new artwork replaces the existing star placeholder inside the Oasis advertisement atlas. The original PNG and generation prompt are retained under `art/northstar/`. The atlas keeps its existing dimensions, mip chain and sRGB encoding. All 80111 compressed blocks outside the affected panel are byte identical. All 599 material definitions and their shader bindings are unchanged. The exact mounted payload was checked in game, then stock Coliseum and Party Crasher reloaded without logged errors. This is a single-client visual/reload check, not a new multiplayer or performance certification. Rollback assets are retained in `party-crasher/northstar-screen-v1/` on the build drive.
