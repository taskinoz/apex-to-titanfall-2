import json,struct
from pathlib import Path
import pefile
from audit_character_lighting import PATHS
from repair_preview_index_padding import read_lumps
p=pefile.PE('D:/Games/Titanfall2/bin/x64_retail/engine.dll',fast_load=True)
for s in p.sections:
    d=s.get_data()
    for key in (b'LUMP_LIGHTPROBE',b'Mod_LoadLightProbe',b'lightprobe',b'r_light',b'ambientcube'):
        at=0
        while True:
            at=d.find(key,at)
            if at<0:break
            end=d.find(b'\0',at);value=d[at:end].decode('ascii',errors='replace')
            print(hex(s.VirtualAddress+at),value);at+=len(key)
for name,path in PATHS.items():
    with path.open('rb') as f:h=f.read(2064)
    print(name,'headers',{hex(i):struct.unpack_from('<4I',h,16+i*16)[1:3] for i in (4,6,7,0x65,0x67,0x68)})
    l=read_lumps(path,(0x65,0x67,0x68))
    refs=list(struct.iter_unpack('<3fIi',l[0x68]))
    if refs:
        from collections import Counter
        print('reference unknown',Counter(r[4] for r in refs).most_common(8))
        print('tree',list(struct.iter_unpack('<If',l[0x67]))[:12])
        for i in [0,refs[0][3],refs[len(refs)//2][3]]:
            data=l[0x65][i*48:(i+1)*48]
            print('probe',i,'ambient',list(struct.iter_unpack('<4B',data[:24])),'sky',struct.unpack_from('<4h',data,24),'weights',list(data[32:36]),'indices',struct.unpack_from('<4h',data,36))
