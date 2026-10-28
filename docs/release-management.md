# Release packages and local cleanup

Player downloads belong in GitHub Releases, not Git history or Git LFS. Each map
is an independent Northstar ZIP. Install the newest `ApexMaps.UI` companion once
alongside whichever maps are wanted. Replace old mod directories rather than
merging them, and keep backups outside the game's active `mods` directory.

## Original-five anniversary RC1

The [anniversary RC1](https://github.com/taskinoz/apex-to-titanfall-2/releases/tag/anniversary-2026-rc1)
focuses on Phase Runner, Drop-Off, Firing Range, Party Crasher and Overflow, with
ApexMaps.UI 0.2.1. Its distinct `Anniversary2026-RC1` ZIP names contain the same
accepted runtime bytes, refreshed installation notes and the existing real
game screenshots. Mod versions remain unchanged. The six ZIPs, checksums and
runtime manifest live in `output/releases/anniversary-2026-rc1/`.

[The validation report](anniversary-2026.md) records the Northstar 1.31.14
single-client checks, known limits and compiler assessment. The source helpers
stage/hash the accepted beta, audit the exact staged maps, exercise native
loads/modes, require manual screenshot review, package clean player files and
export a public receipt without private harness metadata. Existing destinations
are verified rather than silently overwritten. The October beta and historical
draft remain unchanged because older recovery chains reference those bytes.

## October 2026 beta

The [October 2026 beta](https://github.com/taskinoz/apex-to-titanfall-2/releases/tag/maps-beta-2026-10-25)
contains the existing accepted distributions, without rebuilding or changing
their version numbers:

| Download | Version |
| --- | --- |
| Phase Runner | 1.7.2 |
| Drop-Off | 0.10.1 |
| Firing Range | 0.5.1 |
| Party Crasher | 0.6.4 |
| Overflow | 0.4.1 |
| Thermal Station | 0.1.2 |
| Thunderdome | 0.1.1 |
| ApexMaps.UI | 0.2.1 |

These are previews. Existing gameplay, rendering and stability limitations are
listed in the release notes and each package README. Packaging verification does
not establish new multiplayer, performance or gameplay results.

The clean local download set is `output/releases/maps-beta-2026-10-25/`: eight
ZIPs, checksums, a manifest and short installation instructions. ZIPs are
hardlinked to their compatible top-level output paths, so this directory does
not allocate a second copy of the large downloads. It is an immutable snapshot
of the published beta. Future builds should get a new version and use atomic
replacement, never edit a published ZIP in place.

`SHA256SUMS.txt` and `release-manifest.json` accompany the release. The latter
records package sizes, SHA-256 hashes, mod identities, membership checks and
differences from the current generated working files. Shared UI regeneration
has changed some working loading packs since the older map ZIPs were made.
The accepted player ZIPs still match their recorded distribution receipts;
this cleanup preserves those exact bytes instead of silently repackaging them
under an existing version.

## Historical downloads

Superseded ZIPs are kept in the **draft** GitHub release tagged
`build-archive-2026-10-25`, separate from current player downloads. Repository
maintainers can find it in the Releases page while signed in. It includes
`archive-manifest.json`, with the original filenames, storage group, sizes and
SHA-256 hashes. Some originals are stored as complete ZIPs; others use smaller
Zstandard differential backups. `archival-objects.json` records the exact backup
objects and reference chains. Every differential backup was decoded and checked
against the original ZIP's SHA-256 before upload. This archive is for recovery,
not a supported download set.

The inventory excludes bundles containing runtime logs, session state or
credential-like text. Excluded files stay local and are recorded in the private
inventory. They are consolidated under
`output/release-cleanup-2026-10-25/retained-private/`. Do not publish a historical
development archive merely because its filename resembles a player package.

To restore an archived ZIP, download the restore helper from the draft release.
It requires an authenticated GitHub CLI and an installed Zstandard CLI:

```powershell
gh release download build-archive-2026-10-25 `
  --repo taskinoz/apex-to-titanfall-2 `
  --pattern 'restore_release_archive.py' `
  --dir 'CHOSEN-TOOLS-DIRECTORY'

python 'CHOSEN-TOOLS-DIRECTORY/restore_release_archive.py' `
  'EXACT-ORIGINAL-ARCHIVE-FILENAME.zip' `
  --destination 'CHOSEN-RESTORE-DIRECTORY' `
  --local-current 'output'
```

The optional `--local-current` avoids downloading an existing current ZIP; it is
still hash-checked. Otherwise the helper fetches the exact required base from the
beta. It resolves reference chains, verifies downloaded objects and reconstructed
ZIPs, and removes temporary intermediates inside its own checked workspace. Only
the requested original ZIP remains. Existing destination files are preserved.
Use `--zstd PATH` if the compression tool is not on PATH. Downloading an old archive
is not a recommendation to run it; earlier builds include known defects.

The beta and historical draft form one backup set. Preserve referenced beta
ZIPs and intermediate archive objects; removing either can break an older
version's restoration chain. A later cleanup must rebase and verify those
dependencies before pruning them.

## Cleanup tool

`manage_release_archives.py` implements this dated migration. Its fixed storage
roots and tags are intentional. Review them before adapting it for another
migration; do not simply rerun inventory after the historical ZIPs are removed.
The original inventory and upload/retirement receipts remain in
`output/release-cleanup-2026-10-25/` (ignored by Git).

1. `inventory` checks archive paths, member names and private state; current ZIPs
   are fully read and compared with both working files and accepted distribution
   receipts. Checkpoints permit a read-only historical scan to resume.
2. `prepare` creates separate draft releases and exact manifests.
3. `upload --scope current` uploads the eight current packages, compares
   GitHub's server-computed SHA-256 and size with each local file, then publishes
   the beta. Existing assets with conflicting bytes are refused.
4. `archive_release_history.py` creates differential backups where they are
   smaller and fully reads their decoded streams to verify exact original ZIP
   reconstruction. Complete ZIPs are used where a delta would not help. It
   uploads and verifies all objects, manifests and the restore helper, leaving
   the history release as a draft. Interrupted uploads can resume without
   overwriting assets. Uploaded temporary delta files can be removed with
   `archive_release_history.py --prune-uploaded` after checking their remote hash.
5. `retire` is a dry run. `retire --apply` removes only individually inventoried,
   unchanged historical ZIPs with matching remote state, size and SHA-256.
   Differential retirement also requires a complete remote backup manifest,
   exact reconstruction proofs and every reference object. The entire dependency
   set is checked before the first original ZIP is removed.
   Current ZIPs, runtime mods, build trees, source inputs and excluded bundles
   are preserved. Matching checksum sidecars are retired with their ZIPs.
6. `private-history` consolidates excluded bundles locally without uploading
   them. It moves only explicitly inventoried files within the same storage
   volume and records their retained hashes and paths.
7. `organize-current` exposes the clean local beta directory with same-volume
   hardlinks after checking its files against the published hashes.

Retirement checks the resolved absolute parent of every file against the two
explicit distribution directories, including the existing output junction.
There is no recursive directory deletion. A durable per-file journal precedes
deletion, followed by a completed receipt; a restart can recover an interruption
between those writes and distinguish it from an unexpected absence.
Disposable-file tests exercise traversal rejection, missing/incorrect
remote proof, changed local files, dry runs, current-package preservation,
resumption, interrupted deletion, malformed checksum sidecars, incomplete
differential archives, failed-upload recovery and actual two-delta restoration
where each restored ZIP is larger than its reference.

The installed Zstandard CLI takes a bare `-M` number as bytes. Passing `-M4096`
did not provide a 4 GiB allowance and rejected a historical ZIP larger than its
reference. The checker and restore helper now use an explicit `--long=31`
decoder window; both the growing-file fixture and the real 776 MiB historical
ZIP restore to their original SHA-256. The upstream
[patching guide](https://github.com/facebook/zstd/wiki/Zstandard-as-a-patching-engine)
and [CLI manual](https://github.com/facebook/zstd/blob/v1.5.7/programs/zstd.1.md)
describe the reference-file and decoder-window options.

Keep the retirement receipt and original inventory. The receipt records logical
bytes retired and the change in free space on the storage volume; those may
differ because some older generated files were already hardlinked.
