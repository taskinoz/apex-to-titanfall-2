"""Keep failed-candidate assets, but use the proven BSP/sidecar to isolate loading."""
import os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=ROOT/'northstar/PhaseRunner.ArtSupportsRelease';dest=ROOT/'northstar/PhaseRunner.ClientPakIsolation'
for p in source.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(source);q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True)
    actual=ROOT/'northstar/PhaseRunner.Preview'/rel if rel.as_posix() in ('mod/maps/mp_phase_runner.bsp','mod/maps/mp_phase_runner.stbsp') else p
    if q.exists():q.unlink()
    if actual.stat().st_size>10*1024*1024:os.link(actual,q)
    else:shutil.copy2(actual,q)
print('Isolated candidate assets with working 0.1.42 BSP/sidecar staged.')
