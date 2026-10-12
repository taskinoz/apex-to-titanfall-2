# Repository contents and local data

This repository contains the conversion source, tests, Northstar script/mod
definitions, technical documentation, testing harnesses and the portable map
comparison site. It does not contain a Titanfall 2 or R5R installation, extracted
game assets, compiled map packages, private harness sessions or build backups.
Those files remain in the original workspace and are excluded by `.gitignore`.

The current player packages are Phase Runner 1.3.0 and Drop-Off 0.7.0. Local ZIPs
are in `output/`; they are not Git contents. Opening `site/dist/index.html` needs
no game assets or server. Native screenshot archives are included in the site.

## Restoring the development environment

1. Use your own installed Titanfall 2/Northstar and R5R game files. Configure the
   installation paths described in the two harness guides. Their defaults refer
   to the original development machine.
2. Restore upstream tools under `tools/` using
   [the pinned toolchain manifest](docs/toolchain/upstreams.json). Check out each
   recorded commit. Preserve upstream licenses; they are also recorded alongside
   the manifest. Apply any listed local patch from that tool's checkout.
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
