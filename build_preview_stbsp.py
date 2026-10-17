"""Write a native v8.0 STBSP catalog for the preview's resident RPak assets.

Empty coverage columns use the native Coliseum empty-column encoding. This is
not a mip-streaming implementation: current custom textures have no starpak.
The upstream parser's writer uses incorrect header offsets; write a 392-byte
native header explicitly and independently round-trip it through the parser.
"""
import json
import struct
import sys
from pathlib import Path
from extract_native_material import NativePak

ROOT=Path(__file__).resolve().parent


def build(folder=None,material_project=None,map_name='mp_phase_runner_preview',pak_name='phase_runner_world',extra_paks=()):
    sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
    from bsp_tool.extensions.stbsp import StreamBsp
    folder=Path(folder) if folder is not None else ROOT/'output/phase-runner/preview-lighting'
    source=folder/(map_name+'.bsp')
    data=source.read_bytes()
    def lump(i):
        o,n,_,_=struct.unpack_from('<4I',data,16+i*16);return data[o:o+n]
    textures,table,strings=lump(2),lump(0x2c),lump(0x2b)
    names=set()
    for off in range(0,len(textures),36):
        index=struct.unpack_from('<I',textures,off+12)[0]
        start=struct.unpack_from('<I',table,index*4)[0]
        names.add(strings[start:strings.index(0,start)].decode().replace('\\','/'))
    assets={}
    project=Path(material_project) if material_project else ROOT/'output/phase-runner/world-materials'
    # Maps whose materials span several packs (Phase Runner) pass them as extra_paks.
    for path in (ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak',project/'build'/(pak_name+'.rpak'),*map(Path,extra_paks)):
        pak=NativePak(path)
        for asset in pak.assets:
            if asset['type']!='matl':continue
            addr=pak.address(asset['header'])
            name=pak.string(struct.unpack_from('<2I',pak.data,addr+24)).replace('\\','/')
            assets[name]=asset['guid']
    material_strings=bytearray();infos=bytearray()
    for name in sorted(names):
        if name not in assets:raise ValueError(f'No mounted material GUID for {name}')
        offset=len(material_strings);material_strings.extend(name.encode()+b'\0')
        infos.extend(struct.pack('<2IQ2I',offset,0,assets[name],0,0))
    native=StreamBsp.from_file('D:/Games/Titanfall2/r2/maps/mp_coliseum.stbsp')
    empty=next(c for c in native.columns if c.length==32 and native.column_data[c.offset:c.offset+32]==bytes(32))
    columns=bytearray();payload=bytearray()
    for y in range(-80,80,4):
        for x in range(-80,80,4):
            columns.extend(struct.pack('<QIf4h',len(payload),32,empty.coverage_scale,x,y,x+4,y+4))
            payload.extend(bytes(32))
    blocks=[material_strings,infos,b'',b'',columns,payload]
    counts=[len(material_strings),len(infos)//24,0,0,len(columns)//24,len(payload)]
    offsets=[0]*6;cursor=392
    for i in (1,2,3,0,4,5):offsets[i]=cursor;cursor+=len(blocks[i])
    header=bytearray(struct.pack('<I2H4iI2f',0xcb00cbb5,8,0,-80,-80,159,159,4,128.,128.))
    header.extend(bytes(132))
    for off,count in zip(offsets,counts):header.extend(struct.pack('<2Q',off,count))
    header.extend(bytes(128))
    if len(header)!=392:raise ValueError('Invalid native STBSP header')
    output=source.with_suffix('.stbsp')
    output.write_bytes(header+b''.join(blocks[i] for i in (1,2,3,0,4,5)))
    check=StreamBsp.from_file(str(output))
    if check.version!=(8,0) or len(check.columns)!=1600 or len(check.material_infos)!=len(names):
        raise ValueError('STBSP round-trip failed')
    for column in check.columns:
        if column.offset+column.length>len(check.column_data):raise ValueError('Column range exceeds payload')
    if {m.guid for m in check.material_infos}!={assets[n] for n in names}:
        raise ValueError('STBSP material GUIDs differ from mounted assets')
    status=json.loads(source.with_name('source-build.json').read_text())
    status['streaming_sidecar']=dict(version='8.0',materials=len(names),columns=1600,
        bytes=output.stat().st_size,native_parser_round_trip=True,material_guids_verified=True,
        coverage='Native empty columns for resident textures',client_load_verified=False,
        limitation='No spatial mip coverage or starpak-backed texture streaming yet.')
    source.with_name('source-build.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status['streaming_sidecar'],indent=2))


if __name__=='__main__':build()
