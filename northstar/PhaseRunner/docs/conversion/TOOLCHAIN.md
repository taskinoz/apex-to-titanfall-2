# Toolchain and rebuild requirements

The release archive is ready to install. The developer archive contains reference source, documentation and inventories. It is not a self-contained universal converter: the historical build stages require extracted game assets, material projects and retained intermediate map releases.

## Environment

The prototype runs on Windows with PowerShell, Python, NumPy, Pillow, SciPy and xatlas. Parser source and its license are included under `tools/bsp_tool`; other tools must be obtained separately. [toolchain-versions.json](toolchain-versions.json) records installed library versions and local repository commits. [source-and-tool-checksums.json](source-and-tool-checksums.json) identifies source BSP chunks, entity partitions, compiler/RePak/baker binaries. [source-archive-manifest.json](source-archive-manifest.json) records original archive checksums. Engine hashes and scoped limits are in [engine-limits.json](engine-limits.json).

The Python files normally resolve project-relative paths but historical stages sometimes use absolute game locations. Review those before running on another machine. `Run-MapHarness.ps1` selects the bundled local Python if available, falling back to `python`. `harness.py start --game <path> --package <path>` selects another install. Do not copy harness `output/session.json` or raw profiles between users; they carry session credentials.

## Compiler and asset tools

- MRVN Radiant's compiler is useful without the interactive editor. The local CMake cache uses `BUILD_RADIANT=OFF`, `BUILD_PLUGINS=OFF`; apply [mrvn-compiler.patch](mrvn-compiler.patch) to the recorded commit. The patch changes build configuration and the map writer used here. It is not a complete editor implementation.
- RePak constructs native material and presentation RPaks. Match the recorded binary and inspect its project configuration. Native shader dependencies and GUID closure are part of each material project; a different RePak version may need adapters.
- Legion and compiled VG/RMDL readers recover source models and material channels. The direct static decoder does not implement arbitrary animated/skinned models.
- The retained C++ light bakers generate world/local/character data. Their binary checksums and source are supplied; recreate their build environment separately. The packed record header passes a C++17 syntax/size check using LLVM clang++.
- BSP Toolkit's retained parser version supports the tested map formats; native STBSP writer corrections are implemented explicitly in this project rather than assuming the upstream writer round-trips correctly.

## Current release reproduction

1. Preserve the stable `northstar/PhaseRunner.ArtSupportsLoadingRelease` 0.1.44 baseline and the `northstar/PhaseRunner.Preview` 0.1.46 reference; the release script reads their geometry, tree placement and material reports.
2. Supply original source placement metadata, exported RMDL/VG/PHY files, native common/Coliseum packs and the staged material projects at the paths expected by the builders.
3. Run `audit_tree_grounding.py` against the 0.1.46 reference to produce the measured correction report, then `build_phase_runner_release.py` to rebuild corrected fir geometry, collision, visibility and lighting into `northstar/PhaseRunner`.
4. Run `test_phase_runner_release.py`. Launch the isolated harness explicitly with that package, capture the native route and validate same-map and stock-map return behavior. The current finalizer uses recorded evidence paths for this release; parameterize these in a future build system.
5. Run `document_conversion_release.py`, `validate_conversion_docs.py`, then the finalizer after updating validated evidence paths. The finalizer preserves the previous installed mod, verifies archive membership and hashes, and checks installed file hashes.

These steps depend on retained intermediate files not included in the developer archive. Recovering a fresh source map requires implementing the staged architecture in the main guide; replaying the latest wrapper alone will not perform that conversion.

## Packaging and permissions

The installable ZIP contains converted map assets and custom RPaks. The source ZIP excludes original game archives, logs/session credentials and third party tool executables. It includes the parser license and compiler patch. Upstream licenses and game-asset redistribution permissions must be reviewed for any public distribution; this local packaging operation does not establish those permissions.

The normal installed folder retains the historical `PhaseRunner.Preview` directory name for compatibility, but its `mod.json` identifies `PhaseRunner` version `1.0.0`. The ZIP uses the clean `PhaseRunner` directory. Install only one copy. The canonical 0.1.46 development reference remains unchanged so current builders do not apply tree deltas twice.
