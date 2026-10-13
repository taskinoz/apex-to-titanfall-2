"""Regression tests for source entity sidecars, sun direction and sparse caches."""
import ctypes
import os
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from new_arena_ports import ROOT, WORK
from repair_environment_lighting import entities
from stage_rpak_streams import stage


class PortSupportTests(unittest.TestCase):
    def test_external_entities_override_binary_header(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp:
            p=Path(tmp)/'mp_test.bsp'
            p.write_bytes(b'rBSP'+bytes(32)+b'{'+bytes(2000))
            Path(str(p)+'.0000.bsp_lump').write_bytes(b'{\n"classname" "worldspawn"\n}\n\0')
            p.with_name('mp_test_env.ent').write_bytes(b'ENTITIES02 num_models=0\n{\n"classname" "light_environment"\n}\n\0')
            self.assertEqual([e['classname'] for e in entities(p)],['worldspawn','light_environment'])

    def test_native_embedded_entities_still_load(self):
        p=ROOT/'northstar/PhaseRunner/mod/maps/mp_phase_runner.bsp'
        rows=entities(p)
        self.assertEqual(sum(e['classname']=='worldspawn' for e in rows),1)
        self.assertTrue(any(e.get('script_name')=='menu_scene_ref' for e in rows))

    def test_source_sun_changes_character_occlusion(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp:
            p=Path(tmp)
            tris=[[[2,-100,-100],[2,100,-100],[2,100,100]],[[2,-100,-100],[2,100,100],[2,-100,100]]]
            (p/'tri').write_bytes(b''.join(struct.pack('<9f',*(v for point in t for v in point)) for t in tris))
            (p/'positions').write_bytes(struct.pack('<3f',0,0,0));(p/'fixtures').write_bytes(b'')
            exe=WORK/'tools/bake_arena_character_probes.exe'
            for direction,expected in (((1,0,0),0),((-1,0,0),1)):
                subprocess.run([str(exe),str(p/'tri'),str(p/'positions'),str(p/'fixtures'),str(p/'result'),
                                *map(str,direction)],check=True,capture_output=True)
                values=struct.unpack('<24f',(p/'result').read_bytes())
                self.assertEqual(values[15],expected)
            invalid=subprocess.run([str(exe),str(p/'tri'),str(p/'positions'),str(p/'fixtures'),str(p/'result'),
                                    '0','0','0'],capture_output=True)
            self.assertNotEqual(invalid.returncode,0)

    @unittest.skipUnless(os.name=='nt','Native sparse allocation check is Windows specific')
    def test_stream_cache_retains_offsets_without_allocating_unused_extents(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp:
            p=Path(tmp);source=p/'source';cache=p/'cache';source.mkdir();cache.mkdir()
            name=b'test.starpak\0';size=16*1024*1024;block=b'asset block'.ljust(4096,b'x')
            with (source/'test.starpak').open('wb') as stream:
                stream.truncate(size);stream.seek(4096);stream.write(block)
                stream.seek(size-24);stream.write(struct.pack('<3Q',4096,4096,1))
            header=bytearray(128);header[:4]=b'RPak';struct.pack_into('<H',header,4,8)
            struct.pack_into('<5H',header,72,len(name),0,0,0,0);struct.pack_into('<2I',header,84,0,1)
            asset=bytearray(80);struct.pack_into('<2Q',asset,32,4096,0xffffffffffffffff)
            pak=cache/'test.rpak';pak.write_bytes(header+name+asset)
            stage(pak,source);target=cache/'test.starpak'
            self.assertEqual(target.stat().st_size,size)
            with target.open('rb') as stream:
                stream.seek(4096);self.assertEqual(stream.read(4096),block)
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetCompressedFileSizeW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
            kernel.GetCompressedFileSizeW.restype=ctypes.c_ulong
            high=ctypes.c_ulong();low=kernel.GetCompressedFileSizeW(str(target),ctypes.byref(high))
            self.assertLess((high.value<<32)|low,size//4)

    def test_native_v7_stream_cache_uses_single_stream_reference(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as tmp:
            p=Path(tmp);source=p/'source';cache=p/'cache';source.mkdir();cache.mkdir()
            name=b'native.starpak\0';block=b'native texture'.ljust(4096,b'x')
            (source/'native.starpak').write_bytes(bytes(4096)+block+struct.pack('<3Q',4096,4096,1))
            header=bytearray(88);header[:4]=b'RPak';struct.pack_into('<H',header,4,7)
            struct.pack_into('<4H',header,56,len(name),0,0,0);struct.pack_into('<2I',header,64,0,1)
            asset=bytearray(72);struct.pack_into('<Q',asset,32,4096)
            pak=cache/'native.rpak';pak.write_bytes(header+name+asset);stage(pak,source)
            self.assertEqual((cache/'native.starpak').read_bytes()[4096:8192],block)


if __name__=='__main__':unittest.main()
