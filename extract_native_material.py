"""Read an unpatched native v7 RPak and stage a material for RePak.

Header layouts follow RSX's cpakfile.h and material.h. The original game file
is never edited; input must be a separately decompressed workspace copy.
"""
import argparse
import json
import struct
from pathlib import Path


class NativePak:
    def __init__(self,path):
        self.data=path.read_bytes()
        magic,version,flags=struct.unpack_from('<4sHH',self.data)
        if magic!=b'RPak' or version!=7 or flags&0x100:
            raise ValueError('Expected decompressed native v7 RPak')
        streaming,segments,pages,patches=struct.unpack_from('<4H',self.data,56)
        pointers,assets,guid_refs,dependencies,external,external_size=struct.unpack_from('<6I',self.data,64)
        if patches:
            raise ValueError('Patch chains require the upstream patch loader')
        offset=88+streaming+segments*16
        page_headers=list(struct.iter_unpack('<3I',self.data[offset:offset+pages*12]))
        offset+=pages*12+pointers*8
        self.assets=[]
        for i in range(assets):
            record=self.data[offset+i*72:offset+(i+1)*72]
            self.assets.append(dict(guid=struct.unpack_from('<Q',record)[0],
                header=struct.unpack_from('<2I',record,16),cpu=struct.unpack_from('<2I',record,24),
                size=struct.unpack_from('<I',record,60)[0],version=struct.unpack_from('<I',record,64)[0],
                type=record[68:72].decode('ascii')))
        offset+=assets*72+guid_refs*8+dependencies*4+external*4+external_size
        self.pages=[]
        for _,_,size in page_headers:
            if offset+size>len(self.data):
                raise ValueError('Page exceeds file bounds')
            self.pages.append((offset,size))
            offset+=size
        if offset!=len(self.data):
            raise ValueError(f'Page data ends at {offset}, file ends at {len(self.data)}')

    def address(self,pointer):
        index,offset=pointer
        if index==0xffffffff:
            return None
        base,size=self.pages[index]
        if offset>=size:
            raise ValueError('Invalid page pointer')
        return base+offset

    def string(self,pointer):
        if pointer==(0,0):
            return ''
        address=self.address(pointer)
        if address is None:
            return ''
        return self.data[address:self.data.index(0,address)].decode('ascii')

    def material(self,asset):
        if asset['version']!=12 or asset['size']!=208:
            raise ValueError('Expected native material v12')
        address=self.address(asset['header'])
        header=self.data[address:address+208]
        ptr=lambda at:struct.unpack_from('<2I',header,at)
        texture_address=self.address(ptr(152))
        stream_address=self.address(ptr(160))
        if stream_address is None or texture_address is None or not 0<=stream_address-texture_address<=1024:
            raise ValueError('Invalid texture handle range')
        textures=struct.unpack_from('<'+'Q'*((stream_address-texture_address)//8),self.data,texture_address)
        dx=struct.unpack_from('<5I2H',header,80)
        cpu_address=self.address(asset['cpu'])
        cpu=self.data[cpu_address:cpu_address+16]
        uber_address=self.address(struct.unpack_from('<2I',cpu))
        uber_size,uber_flags=struct.unpack_from('<2I',cpu,8)
        width,height,depth=struct.unpack_from('<3H',header,200)
        hexnum=lambda value:f'0x{value:X}'
        spec=dict(name=self.string(ptr(24)).replace('\\','/'),width=width,height=height,depth=depth,
            glueFlags=hexnum(struct.unpack_from('<I',header,192)[0]),
            glueFlags2=hexnum(struct.unpack_from('<I',header,196)[0]),
            blendStates=[hexnum(v) for v in dx[:4]],blendStateMask=hexnum(dx[4]),
            depthStencilFlags=hexnum(dx[5]),rasterizerFlags=hexnum(dx[6]),
            uberBufferFlags=hexnum(uber_flags),features=hexnum(struct.unpack_from('<I',header,184)[0]),
            samplers=hexnum(struct.unpack_from('<I',header,170)[0]),
            surfaceProp=self.string(ptr(32)),surfaceProp2=self.string(ptr(40)),shaderType='wld',
            shaderSet=hexnum(struct.unpack_from('<Q',header,144)[0]))
        spec['$textures']={str(i):hexnum(v) for i,v in enumerate(textures) if v}
        for field,offset in [('depthShadowMaterial',48),('depthPrepassMaterial',56),('depthVSMMaterial',64),('colpassMaterial',72)]:
            spec['$'+field]=hexnum(struct.unpack_from('<Q',header,offset)[0])
        return spec,self.data[uber_address:uber_address+uber_size]


def extract(path,name,output):
    pak=NativePak(path)
    matches=[]
    for asset in pak.assets:
        if asset['type']=='matl' and asset['version']==12:
            address=pak.address(asset['header'])
            pointer=struct.unpack_from('<2I',pak.data,address+24)
            stored=pak.string(pointer).replace('\\','/').lower()
            if name.lower() in stored:
                matches.append((asset,stored))
    exact=[match for match in matches if match[1]==name.lower()]
    if exact:
        matches=exact
    if len(matches)!=1:
        raise ValueError(f'Expected one material, found {[(hex(a["guid"]),n) for a,n in matches]}')
    asset,stored=matches[0]
    spec,uber=pak.material(asset)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(spec,indent=2))
    output.with_suffix('.uber').write_bytes(uber)
    print(json.dumps(dict(guid=hex(asset['guid']),name=stored,uber_bytes=len(uber),spec=spec),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pak',type=Path)
    parser.add_argument('name')
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    extract(args.pak,args.name,args.output)
