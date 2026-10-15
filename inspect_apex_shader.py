"""Disassemble source material shaders locally using the Windows compiler API."""
import ctypes
import struct
import sys
from pathlib import Path
from apex_material_constants import ApexMaterials


def disassemble(materials, name, destination):
    library=ctypes.WinDLL('d3dcompiler_47.dll')
    fn=library.D3DDisassemble
    fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)]
    fn.restype=ctypes.c_long
    d=materials.data
    h=materials.address(materials.materials[name]['header'])
    ss=materials.index[struct.unpack_from('<Q',d,h+88)[0]]
    sh=materials.address(ss['header'])
    for kind,offset in [('vs',48),('ps',56)]:
        a=materials.index[struct.unpack_from('<Q',d,sh+offset)[0]]
        at=materials.address(a['cpu'])
        ptr=struct.unpack_from('<2I',d,at)
        size=struct.unpack_from('<I',d,at+8)[0]
        start=materials.address(ptr)
        dx=d[start:start+size]
        blob=ctypes.c_void_p()
        if fn(dx,len(dx),0,None,ctypes.byref(blob)):
            raise ValueError('Disassembly failed')
        table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        getptr=ctypes.WINFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p)(table[3])
        getsize=ctypes.WINFUNCTYPE(ctypes.c_size_t,ctypes.c_void_p)(table[4])
        raw=ctypes.string_at(getptr(blob),getsize(blob)).decode()
        destination.mkdir(parents=True,exist_ok=True)
        (destination/(name+'-'+kind+'.txt')).write_text(raw)
        ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(blob)


if __name__=='__main__':
    p=ApexMaterials(Path(sys.argv[1]))
    for name in sys.argv[3:]:
        disassemble(p,name,Path(sys.argv[2]))
