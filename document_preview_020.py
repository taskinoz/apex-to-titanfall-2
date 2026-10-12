from pathlib import Path
import json
p=Path('README.md');s=p.read_text();addition='''

## Northstar preview 0.1.20 — 3 October 2026

Installed under `D:\\Games\\Titanfall2\\R2Northstar\\mods\\PhaseRunner.Preview`. Restart Northstar and load `map mp_phase_runner_preview`.

The original 7,010,627 render triangles now use 22,171 spatial sections (at most 512 triangles each). The 892 material-sort records and all vertex attributes are shared unchanged; the native visibility tree and actual mesh bounds are rebuilt. A development minidump exposed the engine material-sort loader's fixed bitset when duplicate sort records were created. The corrected build shares the original records and rejects oversized sort tables before packaging.

Native collision is added to 341 rock placements and 676 pipe placements, plus partial surface collision on both portal tubes. 845 placements preserve original IRPS convex pieces. 172 dense rock BVHs use bounded convex approximations. 67 approximations overlapping the portal bounds are withheld to avoid closing those areas. 140 exact duplicate world brushes are removed while preserving every original world solid. Compound grid references allow the added brushes within the native index capacity. Large portal collision and small hollow elbow decorations remain incomplete.

56 checks pass. The final dedicated server loaded in 45.278 seconds, retained 24 existing world probes, passed 24 added point probes, and passed 24 pilot-sized hull contacts with clear starts. All 11 installed package files match their recorded hashes. GPU pop-in and complete player movement remain unverified. The package is `output/PhaseRunner.Preview-0.1.20.zip`; the earlier 0.1.19 archive is retained.

Build stages: `spatial_preview_meshes.py` (bundled NumPy runtime), `prepare_portal_collision.py`, `extend_prop_collision.py`, `package_northstar.py`, and `finalize_textured_preview.py`. Physics decoding follows the pinned RSX IRPS and model BVH layouts. Evidence is in the packaged build/runtime JSON and `logs/unit-0.1.20.log`, `logs/preview-0.1.20-final.log`.
'''
if '## Northstar preview 0.1.20' not in s:p.write_text(s+addition)
p=Path('output/phase-runner/client-feedback-0.1.19.json');p.write_text(json.dumps(dict(version='0.1.19',reported_date='2026-10-03',user_feedback='That works better but there is still a bunch of pop in for rocks and props. there is also a bunch of missing collision of the rocks and pipes',remaining=['rock and prop pop-in','missing rock and pipe collision']),indent=2))
