"""Read-only native lightmap and asset-package comparisons for the load hang."""
import json,struct
from pathlib import Path
from extract_native_material import NativePak
ROOT=Path(__file__).resolve().parent
for name in ('glass-console','art-supports'):
    p=ROOT/f'output/phase-runner/{name}/mp_phase_runner.bsp'
    with p.open('rb') as f:
        h=f.read(2064);print(name,p.stat().st_size)
        for i in (0x53,0x62,0x69):print(hex(i),struct.unpack_from('<4I',h,16+i*16))
        o,n,*_=struct.unpack_from('<4I',h,16+0x53*16);f.seek(o);print('Light headers',list(struct.iter_unpack('<4H',f.read(n))))
for name in ('phase_runner_glass_console','phase_runner_art_supports'):
    p=ROOT/f'northstar/PhaseRunner.ArtSupportsRelease/paks/{name}.rpak';pak=NativePak(p)
    print(name,len(pak.data),struct.unpack_from('<4sHH',pak.data),len(pak.assets))
