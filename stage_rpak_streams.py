"""Stage only RPak-referenced starpak blocks in owned sparse cache files.

Original archives are opened read-only. Native offsets and directory entries
are retained so Legion can read this cache without copying entire libraries.
"""
import argparse,ctypes,json,os,struct
from pathlib import Path
def stage(pak,source):
    data=pak.read_bytes();a,b,segments,pages,patches=struct.unpack_from('<5H',data,72)
    if data[:4]!=b'RPak' or struct.unpack_from('<H',data,4)[0]!=8 or patches:
        raise ValueError('An unpatched, decompressed v8 RPak is required')
    descriptors,assets=struct.unpack_from('<2I',data,84)
    names=[ [Path(n.decode().replace('\\','/')).name for n in raw.split(b'\0') if n] for raw in (data[128:128+a],data[128+a:128+a+b])]
    at=128+a+b+segments*16+pages*12+descriptors*8
    needed=[{} for _ in range(2)]
    for i in range(assets):
        for k,ref in enumerate(struct.unpack_from('<2Q',data,at+i*80+32)):
            if ref in (0,0xffffffffffffffff):continue
            index=ref&255
            if index>=len(names[k]):raise ValueError('Stream index out of range')
            needed[k].setdefault(names[k][index],set()).add(ref&~255)
    report=[]
    for k in range(2):
        for name,offsets in needed[k].items():
            original=source/name;target=pak.parent/name
            if original.resolve()==target.resolve():raise ValueError('Cache must differ from original')
            with original.open('rb') as src:
                src.seek(-8,2);count=struct.unpack('<Q',src.read(8))[0]
                if count>1000000:raise ValueError('Invalid starpak directory count')
                src.seek(-8-count*16,2);tail=src.read();table=dict(struct.iter_unpack('<2Q',tail[:-8]))
                missing=offsets-table.keys()
                if missing:raise ValueError(f'Missing blocks: {name}: {missing}')
                size=original.stat().st_size;copied=0
                with target.open('r+b' if target.exists() else 'w+b') as dst:
                    if os.name=='nt':
                        import msvcrt
                        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                        kernel.DeviceIoControl.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
                        returned=ctypes.c_uint32()
                        if not kernel.DeviceIoControl(msvcrt.get_osfhandle(dst.fileno()),0x900c4,None,0,None,0,ctypes.byref(returned),None):
                            raise ctypes.WinError(ctypes.get_last_error())
                    if os.name=='nt':
                        # CRT _chsize_s can materialize the entire zero-filled
                        # extension despite FSCTL_SET_SPARSE. SetEndOfFile keeps
                        # unreferenced starpak extents sparse on NTFS.
                        kernel.SetFilePointerEx.argtypes=[ctypes.c_void_p,ctypes.c_longlong,ctypes.c_void_p,ctypes.c_uint32]
                        kernel.SetEndOfFile.argtypes=[ctypes.c_void_p]
                        handle=msvcrt.get_osfhandle(dst.fileno())
                        if not kernel.SetFilePointerEx(handle,size,None,0) or not kernel.SetEndOfFile(handle):
                            raise ctypes.WinError(ctypes.get_last_error())
                        dst.seek(0)
                    else:dst.truncate(size)
                    src.seek(0);dst.write(src.read(4096))
                    for offset in sorted(offsets):
                        length=table[offset]
                        if offset+length>size-len(tail):raise ValueError('Starpak block overlaps directory')
                        src.seek(offset);dst.seek(offset);remaining=length
                        while remaining:
                            block=src.read(min(remaining,8*1024*1024))
                            if not block:raise ValueError('Truncated source stream')
                            dst.write(block);remaining-=len(block)
                        copied+=length
                    dst.seek(size-len(tail));dst.write(tail)
            report.append(dict(name=name,referenced_blocks=len(offsets),logical_bytes=size,copied_bytes=copied))
            print(name,len(offsets),'blocks',copied,'bytes',flush=True)
    pak.with_suffix('.streams.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pak',type=Path);p.add_argument('source',type=Path);a=p.parse_args();stage(a.pak,a.source)
