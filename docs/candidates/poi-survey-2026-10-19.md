# Battle royale areas as arena candidates

Bounded survey of four areas Apex itself used as Arenas maps, by
`survey_poi_candidates.py`. Data: [poi-survey-2026-10-19.json](poi-survey-2026-10-19.json).

## Method

- **Area points.** Centres and extents come from R5Reloaded's own mode scripts: the CTF ring, flag and spawn points (Artillery, Golden Gardens) and the Flowstate deathmatch spawns (Thermal Station, Dome).
- **Play box.** The hull of those points plus 2,000 units horizontally.
- **Backdrop box.** Plus 6,000 units. This is what a player sees past the boundary, which must be cut or replaced.
- **World geometry.** Counted by triangle centroid from the source BSP.
- **Props.** Costed at LOD min(3, last) from a models-only Legion export of each map pack.
- **Totals.** Shares of Titanfall's 3,145,728-index world limit. Earlier ports start at 95%.
- **Not included.** Collision, materials, lighting and entity budgets are not counted.

## Results (play box)

| Area | Map | World | Props | Total @LOD3 | Total without foliage | Backdrop total |
|---|---|---:|---:|---:|---:|---:|
| Thermal Station | World's Edge | 5.4% | 5,251 | 59.4% | **47.7%** | 237% |
| Golden Gardens | Olympus | 9.4% | 14,599 | 170.3% | **55.9%** | 507% |
| The Dome | World's Edge | 8.0% | 8,637 | 96.8% | **80.4%** | 178% |
| Artillery | Kings Canyon | 7.8% | 8,926 | 103.6% | **99.5%** | 197% |

Notes on the table:
- "Foliage" excludes grass, flowers, plants, moss, bushes, ferns and ivy.
- The earlier ports cut background foliage the same way.
- Golden Gardens is mostly flower beds and grass: 12,000 of its placements.

## Reading

- **Thermal Station** is the clear first candidate. It has the cheapest world, under half the budget without foliage, and the fewest props. Its lava ring is the same emissive-lava problem already solved for Overflow.
- **Golden Gardens** fits once its dense flower and grass placements are thinned. That is a visual trade-off for a map defined by its gardens.
- **The Dome** fits, with less margin.
- **Artillery** sits at the limit even without foliage. Its cost is structural: signs, wall lights, vents and IMC wall sections. It would need LOD downgrades or a tighter boundary.
- **Backdrop.** Every area's surroundings cost two to five times the limit. All four need the backdrop cut to a boundary with a cheap distant shell, as Phase Runner does, rather than imported.

Reference captures from R5Reloaded: `artillery/`, `thermal-station/`, `dome/` and `golden-gardens/` (overview and ground views). The Artillery ground camera landed inside geometry.
