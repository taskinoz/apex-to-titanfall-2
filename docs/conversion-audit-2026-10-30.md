# Conversion code and process audit — 30 October 2026

Scope: the current-Apex native-prop conversion (Thunderdome) and the tooling around it. Timings are from two full
pipeline runs on this machine (24 and 51 minutes; the second traced visibility rays cold). "Fixed" means changed and re-run during this audit; everything else is a
recommendation.

## Pipeline timings (Thunderdome, `run_prop_pipeline.py`)

| Stage | Time | Main cost |
| --- | ---: | --- |
| props | 5–7 min | Model export/compile and texconv, once per texture, single-file subprocesses |
| rebake | 10–11 min | Three lighting bakes over the full scene with prop casters |
| collision | 45 s | Encoding 59k triangle-collision headers |
| overlays | 15 s | |
| world materials | 1.5–2 min | Repacking the 834 MB world RPak |
| cells | 3 min cached, 33 min tracing | Ray tracing 110k viewpoints × 6,000 rays through 6.1M triangles |
| fades | 25 s | |

Every stage reads and rewrites the 930 MB BSP: about 13 GB of disk traffic per run.

## Fixed during the audit

- **Pipeline in the repo.** `run_prop_pipeline.py` replaces an ad-hoc shell script. It runs the seven stages in
  order, stops on the first failure and records per-stage seconds in `pipeline.json`.
- **Visibility tracing scope.** 72% of the reachable viewpoints were on the stadium ring outside the play bounds.
  Those cameras only ever use the all-visible cell, so they are no longer traced (352k to 110k viewpoints). That
  saved only 2 of 35 minutes: rays from the open ring are cheap. The cost is in the arena, where rays cross dense
  geometry.
- **Material GUID matching.** RSX GUIDs were zero-padded to 16 hex digits, while Cast drops the leading zero.
  `td2_rui_screen_bg` (`0x034717147C928E10`) therefore fell back to neutral grey.
- **Glow materials.** Holograms and Apex-additive materials, including the skull's red seams, used Titanfall
  additive templates that drew nothing at all. They are now lit cutouts: illumination × the section's constant
  vertex tint × mask. A material with two exports now keeps the export that has the mask, and an exact name beats
  a `_uh` variant.
- **Big-prop lighting.** Props with a radius over 512 take their probe and lighting origin from the top of their
  bounds. One probe at the skull's base drew the whole 2,700-unit skull black.
- **Mangled lines.** Two heredoc edits had collapsed line continuations (`build_native_props.py`,
  `analyse_visibility.py`).

## Recommendations, by expected value

1. **Weld collision vertex positions (largest win).** The BSP's position lump is 276 MB: 23.0M positions, of which
   only 3.68M are unique. Render uses 3.0M; the 59,122 triangle-collision headers write three fresh positions per
   triangle. Welding within each 96-triangle group (the 10/7/7-bit index deltas stay local) should save roughly
   200 MB. That means faster map loads, smaller downloads and less pipeline I/O. It needs a native trace check
   afterwards, as in `docs/candidates/static-prop-conversion-2026-10-24.md`.
2. **Cache texture conversion.** The props and world-material stages re-run texconv for every texture on every run.
   Keying converted DDS files by source hash, cap and format would cut most of the props stage. Batching files
   per texconv call avoids roughly 1,000 process start-ups.
3. **Stop rewriting the BSP per stage.** Stages could pass lump replacements in memory, or patch lumps in place
   where sizes allow, as `fade_small_props.py` does, and compact once at the end.
4. **Rebake only what changed.** The rebake bakes the whole scene, then patches only the 4×4 tiles that changed.
   Restricting the bake jobs to tiles within shadow range of new casters would make it proportional to the props.
5. **Cheaper visibility rays.** Tracing is 90% of a cold cells stage. Cast fewer rays per viewpoint (6,000 now)
   and fill in near tiles by dilation. Trace against a simplified occluder set instead of render LOD0: props at their
   collision LOD, and foliage already passes through. Or use the GPU: CUDA 13 is installed.
6. **Vectorise viewpoint sampling.** `analyse_visibility.viewpoints` samples walkable triangles in a Python loop,
   over a million triangles once props are included. The barycentric grid can be generated per edge-length bucket
   with NumPy.
7. **Harness reliability.** This session hit three avoidable failures: a capture before spawn, a screenshot
   timeout while the pipeline loaded the machine, and a start that mounted the default package. A readiness wait on
   "one live player" and a retry on screenshot timeout would remove most reruns.
8. **Test coverage.** The repo has 59 test files but none for the native-prop stages, and CI runs no tests (only
   Pages and Thunderstore workflows). Small fixture tests for `rsx_index` (GUID formatting, mask preference),
   `lighting_point` and the cell BSP `locate()` would have caught today's bugs.
9. **Repository shape.** 421 root-level scripts (42,500 lines); 31 define their own lump reader and 19 shell out to
   texconv. A small `respawn_bsp` package (lumps, compaction, sprp, probes) and one texture module would remove
   most of the duplication. Many one-off `recover_*`/`audit_*` scripts could move to an `archive/` folder.
10. **Uncommitted dependency.** The props build reads Cast exports through Codex's uncommitted `read_cast.py`
   change (`matl` nodes). Committing it, with its test, makes the pushed pipeline reproducible.

## Known limits (not code problems)

- Apex RUI screens (`td2_rui_screen_bg`, `td2_apex_screen_rui`) are drawn by Apex script at run time. The port can
  only show their static backing, and the large post screens have no placement data.
- Titanfall additive materials did not render on these props, so glows are lit, not emissive.
