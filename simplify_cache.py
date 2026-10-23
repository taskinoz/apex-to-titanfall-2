"""Cached meshoptimizer simplification of one model LOD (run out of process: the native simplifier faults intermittently).

`cached(folder, lod, error, cache_dir)` returns the simplified sections (list of (n,3,12) float32 arrays, same
order as read_vg_static.load) and computes them in a child process on first use, retrying up to three times.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np


def cached(folder, lod, error, cache_dir):
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir/f'{Path(folder).name}_lod{lod}_e{error:g}.npz'
    for attempt in range(3):
        if out.exists():
            break
        subprocess.run([sys.executable, __file__, str(folder), str(lod), str(error), str(out)], capture_output=True)
    if not out.exists():
        return None
    with np.load(out) as z:
        return [z[str(k)] for k in range(len(z.files))]


def _child(folder, lod, error, out):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from read_vg_static import load
    from recover_party_columns import simplified
    sections, slots, skins = load(folder, int(lod), True)
    result = {}
    for k, s in enumerate(sections):
        a = np.asarray(s, 'f4').reshape(-1, 3, 12)
        result[str(k)] = simplified(a.copy(), float(error)) if len(a) else a
    tmp = Path(out).with_suffix('.partial.npz'); np.savez(tmp, **result); tmp.replace(out)


if __name__ == '__main__':
    _child(*sys.argv[1:5])
