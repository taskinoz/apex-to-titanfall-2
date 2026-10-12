"""Preserve native TF2 shader bytecode and input flags in RePak's MSW format."""
import struct
from pathlib import Path
from extract_native_material import NativePak

def shader(pak,asset):
    h=pak.address(asset['header']);kind,count=struct.unpack_from('<2I',pak.data,h+8)
    if asset['version']!=8 or not 0<count<=32:raise ValueError('Unsupported shader')
    flags=pak.address(struct.unpack_from('<2I',pak.data,h+24));cpu=pak.address(asset['cpu']);stride=24 if kind==1 else 16
    output=bytearray(16+count*24);output[7]=count
    proof=[]
    for i in range(count):
        at=cpu+i*stride;ptr=struct.unpack_from('<2I',pak.data,at);size=struct.unpack_from('<i',pak.data,at+8)[0]
        desc=16+i*24;inputflags=pak.data[flags+i*16:flags+(i+1)*16];output[desc+8:desc+24]=inputflags
        if size>0:
            address=pak.address(ptr);data=pak.data[address:address+size]
            if data[:4]!=b'DXBC' or len(data)!=size:raise ValueError('Invalid native DXBC')
            struct.pack_into('<2I',output,desc,size,len(output)-desc);output.extend(data)
            proof.append(dict(index=i,bytes=size,input_flags=inputflags.hex()))
        elif size<0:struct.pack_into('<2I',output,desc,(~size)&0xffffffff,0)
        else:struct.pack_into('<2I',output,desc,0xffffffff,0xffffffff)
    return bytes(output),proof

def extract(target):
    p=NativePak(Path('inputs/tf2-rpak-work/homestead.raw.rpak'));a=next(a for a in p.assets if a['guid']==0x92a558802becb2d5)
    h=p.address(a['header']);vs,ps=struct.unpack_from('<2Q',p.data,h+72);vtex,ptex,samplers=struct.unpack_from('<3H',p.data,h+24)
    first,resources=struct.unpack_from('<2H',p.data,h+30)
    pixel,pp=shader(p,next(a for a in p.assets if a['guid']==ps));vertex,vp=shader(p,next(a for a in p.assets if a['guid']==vs))
    data=b'MSW\x03\x01'+struct.pack('<2Q3H2B2I',ps,vs,ptex,vtex,samplers,first,resources,37,37+len(pixel))+pixel+vertex
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return dict(native_shader_set=hex(a['guid']),vertex_guid=hex(vs),pixel_guid=hex(ps),pixel_buffers=pp,vertex_buffers=vp,
                vertex_textures=vtex,pixel_textures=ptex,samplers=samplers,unchanged_native_bytecode=True)
