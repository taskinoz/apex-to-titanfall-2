"""Extract Respawn client VPKs using bsp_tool and r5vpk's LZHAM DLL."""
import argparse
import ctypes as c
import fnmatch
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/bsp_tool'))
from bsp_tool.archives.respawn import Vpk
from bsp_tool.archives.valve import Vpk as ValveVpk


class RespawnVpk(Vpk):
    """Support both server and client directory naming conventions."""
    def __init__(self, filename='untitled_dir.vpk'):
        ValveVpk.__init__(self, filename)
        for marker in ('client_', 'server_'):
            start = self.filename.find(marker)
            if start >= 0:
                self.base_filename = self.filename[start:-len('_dir.vpk')]
                break
        else:
            raise ValueError('Expected a client or server Respawn VPK index')


class Params(c.Structure):
    _fields_ = [('size', c.c_uint32), ('dictionary', c.c_uint32),
                ('flags', c.c_uint32), ('seed_size', c.c_uint32), ('seed', c.c_void_p)]


def extract(index, output, pattern='*'):
    dll = c.CDLL(str(ROOT / 'tools/r5vpk/r5vpk/lzham_x64.dll'))
    decompress = dll.lzham_decompress_memory
    decompress.argtypes = [c.POINTER(Params), c.c_void_p, c.POINTER(c.c_size_t),
                           c.c_void_p, c.c_size_t, c.POINTER(c.c_uint32)]
    decompress.restype = c.c_int
    params = Params(c.sizeof(Params), 20, 1, 0, None)
    archive = RespawnVpk.from_file(str(index.resolve()))
    output = output.resolve()
    count = 0
    for name in archive.namelist():
        if not fnmatch.fnmatchcase(name, pattern):
            continue
        target = (output / name).resolve()
        if not target.is_relative_to(output):
            raise ValueError(f'Unsafe archive path: {name}')
        entry = archive.entries[name]
        archive._file.seek(entry.preload_offset)
        chunks = [archive._file.read(entry.preload_length)]
        for part in entry.file_parts:
            stream = archive.archive_vpk(part.archive_index)
            stream.seek(part.offset)
            data = stream.read(part.compressed_length)
            if len(data) != part.compressed_length:
                raise ValueError(f'Truncated archive part: {name}')
            if part.is_compressed:
                buf = c.create_string_buffer(part.length)
                length, checksum = c.c_size_t(part.length), c.c_uint32()
                status = decompress(c.byref(params), buf, c.byref(length), data,
                                    len(data), c.byref(checksum))
                if status != 3 or length.value != part.length:
                    raise ValueError(f'LZHAM error {status}: {name}')
                data = buf.raw
            chunks.append(data)
        data = b''.join(chunks)
        if zlib.crc32(data) != entry.crc:
            raise ValueError(f'CRC mismatch: {name}')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        count += 1
    print(f'Extracted and CRC verified {count} files into {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--pattern', default='*', help='Extract only matching archive paths')
    args = parser.parse_args()
    extract(args.index, args.output, args.pattern)
