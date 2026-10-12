# Northstar banners and Apex display colour

Drop-Off's `thunderdome_flex_screens_plastic_01_opaque` now uses a Northstar
banner. The original atlas region was U 0.529007..0.972563 and V
0.001622..1.998145. Mapping this region to 0..1 restores a complete graphic on
both sides of the existing panels. It changes 396 vertex UV records covering
132 triangles. There is no new banner geometry in Phase Runner: its source
banner bodies are not present in the current render selection.

The source exports contain coloured emissive channels that the original
four-channel material pass omitted. This pass combines their RGB with the
source albedo in linear space at weight 0.75, then encodes the result as BC7
sRGB with a full mip chain. For `tv_imc_screen_graphs_01`, the source emitted
image replaces the nearly white albedo mask, which otherwise clips the graph
colours to white; the source alpha is retained. It retains each native material's normal, gloss,
specular, opaque render state, shader and uber buffer. These are frozen source
display appearances, **not a port of Apex animated emissive shaders**. They do
not cast new light into the environment. Exposure, world lights, character
probes and every lightmap byte remain unchanged.

The source places animated faces in front of its static green panels. Their
fallback UVs collapse to a narrow atlas column, obscuring the artwork with
stripes. Removing those faces exposed rear electronics and failed the visual
check. The final pass retains every original face and uses a wider console
atlas: three repeats of the old console texture and a fourth region containing
the source green display artwork. Existing console U coordinates become
`(u+1)/4`; V and its wrapping remain unchanged. The 24 front triangles per map
are identified by collapsed UVs, size and proximity (within 3.1 units) to static
panel corners, then mapped to the green region using those source UVs.

Auxiliary normal, gloss and specular atlases repeat the original top-level
compressed blocks exactly four times, with complete regenerated mip chains.
The source console body therefore retains its original appearance and PBR
sampling. No new geometry, material sorts, lightmap charts or visibility data
are required. Drop-Off changes 12,960 console UV records plus 396 banner UVs;
Phase Runner changes 10,264 console UV records. The wider atlas is 4096x1024.

| Map | Source materials |
| --- | --- |
| Drop-Off | `echo_big_screen_animation_01`, `caustic_big_screen_01_blue`, `composite_big_screen_01`, `composite_blue_light_02` |
| Phase Runner | `echo_big_screen_animation_01`, `caustic_big_screen_01_blue`, `tv_imc_screen_graphs_01`, `stasis_light_01_blue` |

The source DDS files are read from local Legion exports. They remain excluded
from Git; per-channel SHA-256 values are recorded in the local build receipts.
Only the new banner artwork is added to the source repository. Source game
assets retain their original ownership.

## Binary validation

`verify_banner_display_textures.py` compares every BSP lump with a complete
preserved stable-package backup. Allowed changes are TEXDATA/string tables,
material sorts, banner/console UVs and GAME_LUMP pointer relocation. It verifies that
the relocation leaves the game-lump payload identical and that every
vertex field is identical except the declared albedo UVs. Every index,
triangle, position, normal, mesh buffer, PVS/visibility record, world light,
probe and lightmap pixel is preserved. STBSP
streaming columns are identical; only the resident material catalogue grows.
Material dependencies resolve against the new pack and existing native packs.

| Map | Extra resident RPak bytes | Padded indices | Static batches |
| --- | ---: | ---: | ---: |
| Drop-Off | 16,794,162 | 2,830,530 / 3,145,728 | 353 |
| Phase Runner | 14,345,159 | 2,924,184 / 3,145,728 | 479 |

Both index budgets and batch counts remain identical to their stable builds.
The additional resident texture memory is modest; this is not a streaming or
performance optimization.

## Reproduction

Start with the verified Drop-Off 0.7.0 and Phase Runner 1.3.0 packages.
With the documented local toolchain and source exports restored, run
`restore_banner_display_textures.py drop-off`, then the same command with
`phase-runner`, then run `atlas_source_display_faces.py` for each map, followed by
`verify_banner_display_textures.py`. These are one-shot
operations. Completed receipts reject reapplication. An interrupted staging
pass may resume only if every package file still matches its preserved backup.
Backups are under `output/banner-display-repair/backups/`.

The focused comparison routes select existing hash-verified R5R captures and
capture the updated Titanfall build at the same coordinates and camera angles.
Native client appearance and reload validation are recorded separately after
the game run; binary checks alone do not establish the final appearance.

## Current validation status

Both binary validations pass, as do the 8 Northstar and 23 R5R harness checks.
Eight final native views (five Drop-Off, three Phase Runner) are paired with
hash-verified R5R reference captures. The Phase Runner building views show the
complete green displays; Drop-Off shows upright Northstar banners. Drop-Off →
Phase Runner → Drop-Off reloads succeed in one process with no script errors.
Native captures and same-process reload evidence are checked by
`verify_banner_display_runtime.py` before `finalize_banner_display_release.py`
can create the player releases. Previous release ZIPs and complete installed
mods are retained for rollback. The final texture pass preserves the original
lighting and all original faces; the unsuccessful overlay-removal and lighting
experiments remain only in private build output.
