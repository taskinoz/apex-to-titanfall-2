# Wider arena comparison — 12 October 2026

The current Drop-Off 0.7.0 and Phase Runner 1.3.0 ports were compared against
their original maps in the installed R5R v2.6.52 SDK. This survey expands beyond
the first repair cameras to examine interiors, upper structures, tunnel bends,
terrain and decorative content. Its output is a reviewed visual inventory, not
a new map release.

## Reproduction and evidence

- [Drop-Off route](../r5-harness/routes/drop-off-survey.json): 12 cameras,
  including 8 additional areas.
- [Phase Runner route](../r5-harness/routes/phase-runner-survey.json): 11 cameras,
  including 8 additional areas.
- [Portable comparison site](../site/dist/index.html): select **Area survey**
  and a view; each reviewed view includes **Area notes**.
- [Reviewed observations](../site/survey-findings.json): plain-text notes keyed
  by map and camera.

Positions are camera eyes, with matching angles, field of view and 1280 × 720
native screenshots. Phase Runner source positions add `[26000,19000,0]`;
Drop-Off uses no offset. Both harnesses place the protected noclip player 64
units below the camera so streaming follows the inspected area. Camera routes
use five seconds of settling after placement. These are static views; they do
not establish collision coverage, absence of pop-in during movement, or
multiplayer frame times. HUDs, reflections, exposure and source animation state
can differ.

## Drop-Off findings

| Area | Directly observed difference | Repair priority |
| --- | --- | --- |
| Both control rooms | Hammond wall displays are absent. The west red and east blue wall treatment is not reproduced. | Recover display surfaces and identify the colour source. |
| Lower court and central window | Cargo, stairs, zipline ropes, beams and equipment stations are present. The port is much darker; several source displays correspond to flat blue screens. | Improve local lighting and screen content before adding more cargo. |
| South machinery | The hanging cylinder and structural columns are present. Lit equipment below it lacks source screen detail and red/cyan illumination. | Recover emissive equipment and check nearby light coverage. |
| Court banners and west banner | Mounting frames/support beams are visible. Character artwork is absent; banner surfaces are dark. | Add a suitable display fallback or recover source display content. |
| North closure | The port has a visible cyan grid-textured blocker across a hallway. The source shows hallway panels and a marked object farther inside. | Keep the previously requested room restriction; replace the visible blocker surface. |
| Upper west/east | Walkways, roof domes and tall walls are present. Small roof equipment and warning lights are absent. | Select only high-value fixtures within the existing draw budget. |
| Exterior vista | Source city lights and complex clouds are replaced by a simplified sky. | Treat as a separate backdrop/material task. |

The screenshots establish appearance differences, not their exact underlying
cause. In particular, the red-wall discrepancy cannot yet be attributed solely
to lighting, vertex paint, material tint or source runtime state.

The existing [omission ledger](composite/MISSING_CONTENT.md) already records
unconverted dynamic/UI content, source spotlights approximated as points, 60
selected local lights, and native-budget exclusions. The wider views help rank
those omissions by visibility. They do not demonstrate that all 2,051
budget-excluded placements should be restored.

## Phase Runner findings

| Area | Directly observed difference | Repair priority |
| --- | --- | --- |
| Both buildings | Large monitor frames and console housings are present. The original's green monitor graphics are absent and console appearances still differ. Smaller clutter is missing. | Recover monitor/emissive materials before adding room clutter. |
| Tube mouths | Major tube/support geometry is visible. Port catwalks and railings are intentional additions. Source bright ring lights and red overhead pipe treatment differ. | Restore fixture appearance and identify pipe tint without changing the working catwalks. |
| Eastern tube bend | Raised cameras show the shell, red service pipes and fixtures in both games, plus the port's added catwalk. Source fixtures are brighter. | Improve fixture materials/illumination while preserving the added path. |
| Western tube bend | Port shell, pipes and catwalk are visible; R5R produces a black scene at both tested heights. | Investigate source capture visibility separately; no source/port fidelity conclusion is justified here. |
| Central rocks | Foreground boulders and truck are present. Dense ground plants and green terrain treatment differ; trees are much paler in the port. | Audit foliage materials and terrain layer blending. |
| Truck near Nessie | Truck, container and road are present; surrounding foliage is sparse. The doll is obscured at this camera. | This view does not establish doll detail or support placement. |
| Western stairs | The main step layout is visible in the fixed view. | A separate moving-player angle sweep is needed to test the historic disappearance report. |
| Road/terrain edge | Curb and roadway are present. Leaf litter, dirty blending and painted markings differ markedly. | Recover layered road/terrain detail rather than guessing replacement textures. |
| Whole arena | Tunnels, cranes, roads and central rocks are present. The source has much broader moss/flower coverage and denser vegetation. | Choose small high-value foliage groups within the render budget. |

The historical [omission ledger](../northstar/PhaseRunner/docs/conversion/MISSING_CONTENT.md)
lists 9,537 omitted foliage placements and 527 rock placements inside the arena.
These totals are source placement counts, not a recommendation to restore all
of them. The current validated all-visible renderer uses 2,924,184 of 3,145,728
world indices; Drop-Off uses 2,830,530. Current map payloads were not changed for
this survey. Capacity audits do not measure runtime frame times or guarantee
headroom under combat effects.

## Harness corrections

The first target survey returned to the menu with a native script error in
`PilotHealthRegenThinkMP`: “Called Wait() from script that was not started with
SpinOff()”. Its precise cause is not established. Camera mode previously left
the player at the spawn; it now moves an invulnerable noclip player with the
camera, freezes controls, and validates native position and angles. The repeated
12-view Drop-Off capture completed without a script error. No core game script
was edited.

Completed R5R source views are now saved after each capture. Resume validates
the route, map, camera and PNG hash before reusing a completed prefix. Original
capture metadata is retained across runs. This avoids losing completed evidence
when the native source game closes during a later view.

## Source-format cross-check

The local SDK's 64-byte static-prop record names `diffuseModulation` at byte 52;
the pinned parser labels those four bytes as CPU/GPU levels and names diffuse
modulation at byte 56. This is a version-specific schema discrepancy to audit
for future imports, not a universal assertion about every Apex BSP version.
All 8,356 Drop-Off and 16,862 Phase Runner source records inspected here contain
white RGBA at the SDK offset. That does not explain the red-wall difference.
The audit is saved locally in `output/area-survey/static-prop-tint-audit.json`;
it did not change game data.

## Completed verification

- 23 source/port pairs were hash-checked, decoded at 1280 × 720, and checked
  against native camera position/angles and the Northstar streaming player.
- Two higher tunnel-bend rechecks replace the obstructed first-pass viewpoints.
  Original native images and first-pass manifests remain in local harness output.
- 72 public PNGs across baseline, recovered-paint and area-survey snapshots were
  hash-checked. The public catalogue contains only the exported camera/capture
  fields and reviewed plain-text notes.
- All 31 controller tests passed. The completed Northstar runs ended without
  a script error, and the owned test games were closed.
- Every runtime file was compared with the existing clean player ZIP. Phase
  Runner 1.3.0 and Drop-Off 0.7.0 remain byte-identical to those releases.
- Browser checks covered new view selection, area notes, wipe mode, archived
  snapshots and switching maps. [Viewer preview](../site/area-survey-preview.jpg).

The detailed verification receipt is `output/area-survey/validation.json`.
