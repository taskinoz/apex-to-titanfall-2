import json
import struct
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
from bsp_tool.extensions.stbsp import StreamBsp
from bsp_tool.branches.respawn.titanfall2 import WorldLightv3


class StreamingLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'output/phase-runner/preview-structures/mp_phase_runner_preview.bsp').read_bytes()
        cls.target=(ROOT/'output/phase-runner/preview-lighting/mp_phase_runner_preview.bsp').read_bytes()

    @staticmethod
    def lump(data,i):
        o,n,_,_=struct.unpack_from('<4I',data,16+i*16);return data[o:o+n]

    def test_source_sun_agrees_with_level_and_static_shadows_stay_unconverted(self):
        lights=list(WorldLightv3.from_bytes(r) for r in self.records(self.lump(self.target,0x36),112))
        self.assertEqual({l.type.name for l in lights},{'SKY_LIGHT','SKY_AMBIENT'})
        sun=next(l for l in lights if l.type.name=='SKY_LIGHT')
        level=struct.unpack_from('<3f',self.lump(self.target,0x7b),16)
        self.assertEqual(tuple(sun.normal),level)
        self.assertEqual(self.lump(self.target,5),b'')
        self.assertEqual(self.lump(self.target,0x7f),b'')
        self.assertTrue(all(l.texture_data==-1 for l in lights))

    @staticmethod
    def records(raw,size):
        return (raw[i:i+size] for i in range(0,len(raw),size))

    def test_all_geometry_material_and_physics_lumps_are_unchanged(self):
        for i in range(128):
            if i not in (0x36,0x63,0x7b):
                self.assertEqual(self.lump(self.source,i),self.lump(self.target,i),f'Lump {i:#x}')

    def test_native_streaming_grid_and_material_catalog(self):
        stream=StreamBsp.from_file(str(ROOT/'output/phase-runner/preview-lighting/mp_phase_runner_preview.stbsp'))
        self.assertEqual(stream.version,(8,0))
        self.assertEqual(len(stream.columns),1600)
        self.assertTrue(all(m.guid and m.material in stream.materials for m in stream.material_infos))
        positions={(c.mins_x,c.mins_y) for c in stream.columns}
        self.assertEqual(positions,{(x,y) for y in range(-80,80,4) for x in range(-80,80,4)})
        self.assertTrue(all(c.maxs_x-c.mins_x==4 and c.maxs_y-c.mins_y==4 for c in stream.columns))
        self.assertEqual(stream.column_data,bytes(1600*32))


if __name__=='__main__':unittest.main()
