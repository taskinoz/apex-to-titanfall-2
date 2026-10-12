"""Remove the obsolete 3D sky camera, keeping the recovered world sky dome."""
import json
import re
import shutil
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def build():
    source=ROOT/'output/phase-runner/preview-lighting/mp_phase_runner_preview.bsp'
    output=ROOT/'output/phase-runner/preview-clean-sky/mp_phase_runner_preview.bsp'
    original=source.read_bytes()
    off,length,version,_=struct.unpack_from('<4I',original,16)
    text=original[off:off+length].decode().rstrip('\0')
    text,count=re.subn(r'\{[^{}]*"classname"\s+"sky_camera"[^{}]*\}\s*','',text)
    if count!=1:raise ValueError('Expected exactly one obsolete sky camera')
    data=bytearray(original);data.extend(bytes((-len(data))%16));offset=len(data)
    payload=text.encode()+b'\0';data.extend(payload)
    struct.pack_into('<4I',data,16,offset,len(payload),version,0)
    for i in range(1,128):
        o,n,_,_=struct.unpack_from('<4I',original,16+i*16)
        if data[o:o+n]!=original[o:o+n]:raise ValueError(f'Unexpected change in lump {i}')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    status=json.loads(source.with_name('source-build.json').read_text())
    status['legacy_sky_cleanup']=dict(sky_cameras_removed=1,native_vista_spawn_removed=True,
        world_sky_dome_preserved=True,geometry_and_physics_unchanged=True,visual_verified=False)
    output.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status['legacy_sky_cleanup'],indent=2))


if __name__=='__main__':build()
