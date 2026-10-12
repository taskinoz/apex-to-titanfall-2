# Phase Runner 0.1.44: client loading repair

Version 0.1.43 hung during client asset loading despite passing dedicated-server
collision checks. The hang was reproduced in an isolated client. Version 0.1.42
loaded successfully there; pairing its BSP and streaming sidecar with the new
0.1.43 asset package still hung, isolating the regression to the asset package.

The new road-marking material referenced a shader in a sibling custom RPak.
Version 0.1.44 embeds that shader and its vertex/pixel programs inside the same
RPak, using unique asset identifiers. The native shader bytecode, input flags,
texture bindings, opacity, depth bias and material constants are unchanged.
This removes the cross-package dependency. The repaired client reaches gameplay.

All 0.1.43 geometry, physics, lightmaps and other asset packages are preserved
byte-for-byte. This retains the 22 restored freight/fence supports, full-detail
pipe pieces and transparent road markings. Existing visibility and catwalks
are preserved. The prior 0.1.42 build is retained as the full fallback snapshot.

Four new shader/preservation tests pass. The original seven art-preservation
tests and three native-capacity tests also passed for the unchanged map data.
The live client passes all 4,156 collision/traversal checks. Release validation
also requires a successful map-to-lobby-to-map transition in the isolated client.
Client appearance at the reported coordinates still needs an in-game check.

Restart Northstar before loading `map mp_phase_runner`.

Fallback snapshot:
`output/installed-backups/PhaseRunner.Preview-0.1.42-before-art-supports`

The failed 0.1.43 archive is retained for diagnosis and is not recommended for use.
Its dedicated-server validation did not exercise client RPak loading.
