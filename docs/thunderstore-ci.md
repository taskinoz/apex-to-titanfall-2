# Thunderstore publishing

The `Publish Northstar maps to Thunderstore` Actions workflow publishes under
the **taskinoz** team, matching Enhanced Menu Mod. The repository Actions secret
**TS_KEY** holds the Thunderstore service-account token; it is passed only to
the configuration check and publishing steps (the latter as `TCLI_AUTH_TOKEN`). Never put it in source, release assets
or workflow inputs. Existing GitHub secrets cannot be read or copied between repos.

## First upload and manual runs

Open Actions, select the publishing workflow and choose **Run workflow** on
`main`. Select `current` for all seven maps and their UI companion, or a runtime
mod name such as `ArenaOverflow`. Leave **publish** off for downloadable preview
artifacts; enable it to upload to Thunderstore. Selecting any map automatically
includes its required shared UI package. UI publishes first, so dependency
validation can succeed before map uploads.

Published GitHub releases also trigger this workflow. Only packages whose
reviewed catalog entry matches that release tag are selected, plus shared UI.
Unrecognized release tags fail with an instruction to update the catalog.
Publishing does not run on pull requests; those run offline package tests only.
Runs serialize to avoid concurrent version uploads. Failed batches can be rerun:
already-published packages are downloaded and compared before being skipped.
Different content at an existing version fails rather than overwriting it.
The version check bypasses cached API responses so a stale negative lookup does
not attempt to publish an existing version. For a failed upload, set `reuse_run`
to the previous main-branch manual publishing run ID. CI downloads its saved
artifacts, verifies catalog provenance and output hashes, then uploads the
selected packages without recompressing the maps. Only this repository's named
publishing workflow on main is accepted; artifacts expire after seven days.

## Release inputs and package layout

`thunderstore/packages.json` locks the original-five anniversary downloads,
Overflow 0.4.2 hotfix, two additional October beta maps, and ApexMaps.UI 0.2.1
by GitHub release tag, filename, size and SHA-256. CI downloads these assets;
it does not build from the ignored compiled files in `northstar/` or require
game installations, extraction tools, harness mods or Git LFS.

Each output contains root `manifest.json`, `README.md`, `icon.png`, and the exact
accepted runtime files under `mods/taskinoz.<original-mod-name>/`. Package names
are readable names such as `Drop_Off` and `Phase_Runner`; runtime mod identities
remain unchanged. Every map depends on `taskinoz-ApexMaps_UI-0.2.1`. No Northstar
loader is bundled. Remove old manually installed copies before enabling managed
ones. Icons are 256px crops of existing port screenshots; the UI uses the
comparison site's preview. No new artwork or game asset extraction is involved.

The builder verifies source hashes, mod identity/version, required native map
and asset files, safe ZIP paths and a restricted file layout. It verifies every
runtime byte again after packaging. Development reports, harness files and raw
logs are not included. Output receipts record source/output and runtime hashes.
Actions artifacts expire after seven days; GitHub release originals remain.

## Updating a package

1. Build and validate a new native map version using the existing release process.
2. Publish its clean player ZIP as a GitHub release asset and record its SHA-256.
3. Update its catalog entry with the new version, release tag, exact filename,
   byte size and hash. Commit/merge that entry before publishing the release
   event, or run the workflow manually afterward.
4. If UI changes, bump its package/version and update the dependency version in
   `thunderstore_ci.py` and its regression test. Publish UI before dependent maps.

Thunderstore versions are numeric X.Y.Z; beta/RC status is described in README,
not appended to the version. Existing runtime versions are retained for the
first upload. This packaging pipeline does not certify new gameplay behavior.

The uploader is official `tcli` 0.2.4, installed from NuGet with .NET 8 (its
published runtime policy permits major roll-forward). Actions are pinned to
commit IDs. Configuration files are generated without credentials.

References: [Northstar packaging](https://docs.northstar.tf/Modding/guides/publishing/),
[Thunderstore package requirements](https://wiki.thunderstore.io/mods/creating-a-package),
[official CLI](https://github.com/thunderstore-io/thunderstore-cli),
and [the existing menu-mod workflow](https://github.com/taskinoz/Enhanced-Menu-Mod/blob/main/.github/workflows/thunderstore.yml).
