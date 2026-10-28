# Repository contents and local data

This repository contains the conversion source, tests, Northstar script/mod
definitions, technical documentation, testing harnesses and the portable map
comparison site. It does not contain a Titanfall 2 or R5R installation, extracted
game assets, compiled map packages, private harness sessions or build backups.
Those files remain in the original workspace and are excluded by `.gitignore`.

The original-five release set is Phase Runner 1.7.2, Drop-Off 0.10.1, Firing
Range 0.5.1, Party Crasher 0.6.4 and Overflow 0.4.1, with ApexMaps.UI 0.2.1.
See [the anniversary release report](docs/anniversary-2026.md) for validation
status and scope. Thermal Station and Thunderdome are separate additional ports.
Local ZIPs are in `output/releases/`; they are not Git contents. Opening
`site/dist/index.html` needs no game assets or server. Native screenshot archives
are included in the site. Source scripts and placement ledgers remain in the
repository. The additional-port report describes the
isolated build root and the Python 3.14 extraction / Python 3.12 geometry split.
Their [source-feature and lighting update](docs/candidates/source-features-and-lighting-2026-10-13.md)
records the recovered fixtures, supply bins, native ropes and adapted water.
Earlier preview inventories and screenshot snapshots remain immutable.
The [native water/fog/material report](docs/candidates/native-water-fog-materials-2026-10-14.md)
records source DXBC reflection, colour-space handling, shader contracts and
the rejected candidates encountered during this update.

## Restoring the development environment

1. Use your own installed Titanfall 2/Northstar and R5R game files. Configure the
   installation paths described in the two harness guides. Their defaults refer
   to the original development machine.
2. Restore upstream tools under `tools/` using
   [the pinned toolchain manifest](docs/toolchain/upstreams.json). Check out each
   recorded commit. Preserve upstream licenses; they are also recorded alongside
   the manifest. Apply any listed local patch from that tool's checkout.
   The [r2-model-compiler v0.5.0 assessment](docs/toolchain/r2-model-compiler-2026-10-28.md)
   records a newer optional model-compilation route and its remaining integration
   work; it is not required to install the anniversary maps.
3. Restore Python dependencies, native build tools and your own extracted inputs.
   Existing build scripts and version-specific conversion documents describe
   these inputs. A source-only clone is not a complete one-command map build.
4. Consult [the conversion documentation](docs/conversion/) and current map notes
   before regenerating collision, visibility, materials or lighting.

Do not commit passwords, service tokens, raw game logs or harness session files.
`audit_repository.py` checks the staged Git contents before an upload. Generated
maps and player packages belong in local output or separately reviewed release
attachments, not ordinary Git history.

This project includes third-party tool modifications and documentation of
original game formats. No new license for the project's own source is selected
here. Original game assets and third-party code retain their existing ownership
and licenses.
