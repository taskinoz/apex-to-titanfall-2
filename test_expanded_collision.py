import math
import struct
import unittest
from pathlib import Path
from package_northstar import validate_bsp
from merge_collision import merge


class ExpandedCollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=Path('output/phase-runner/preview-collision/mp_phase_runner_preview.bsp').read_bytes()
        cls.lumps={}
        for i in range(128):
            o,l=struct.unpack_from('<2I',cls.data,16+16*i)
            cls.lumps[i]=cls.data[o:o+l]

    def lump(self,i):
        return self.lumps[i]

    def test_brush_plane_records_and_support_interiors(self):
        planes=list(struct.iter_unpack('<4f',self.lump(1)))
        offsets=list(struct.iter_unpack('<H',self.lump(0x5d)))
        props=self.lump(0x5e)
        count=0
        for record in struct.iter_unpack('<3f2BH3fI',self.lump(0x5c)):
            center=record[:3]; num, index, first=record[4],record[5],record[9]
            self.assertEqual(index,count); count+=1
            self.assertLessEqual((index*6+first+6+num)*2,len(props))
            self.assertTrue(all(v>=0 for v in record[6:9]))
            for j in range(num):
                normal=planes[1+first+j-offsets[first+j][0]]
                self.assertAlmostEqual(sum(v*v for v in normal[:3]),1.,places=5)
        self.assertEqual(count,64000)
        import json
        report=json.loads(Path('output/phase-runner/preview-collision/source-build.json').read_text())
        for i,probe in enumerate(report['collision_probes']):
            center=[(a+b)/2 for a,b in zip(probe['start'],probe['end'])]
            record=struct.unpack_from('<3f2BH3fI',self.lump(0x5c),probe.get('brush_index',i)*32)
            for j in range(record[4]):
                normal=planes[1+record[9]+j]
                self.assertLessEqual(sum(normal[k]*center[k] for k in range(3)),normal[3]+.02)

    def test_grid_references_cover_every_brush(self):
        validate_bsp(Path('output/phase-runner/preview-collision/mp_phase_runner_preview.bsp'))
        sets=list(struct.iter_unpack('<HHI',self.lump(0x57)))
        self.assertEqual({p>>8 for _,_,p in sets},set(range(64000)))
        self.assertEqual(len(self.lump(0x58)),len(sets)*16)
        cells=list(struct.iter_unpack('<HH',self.lump(0x56)))
        self.assertEqual(len(cells),5)
        for cell,(first,count) in enumerate(cells[:4]):
            x=cell%2-1; y=cell//2-1
            for _,_,packed in sets[first:first+count]:
                brush=struct.unpack_from('<3f2BH3fI',self.lump(0x5c),(packed>>8)*32)
                self.assertGreaterEqual(brush[0]+brush[6],x*32768-.02)
                self.assertLessEqual(brush[0]-brush[6],(x+1)*32768+.02)
                self.assertGreaterEqual(brush[1]+brush[7],y*32768-.02)
                self.assertLessEqual(brush[1]-brush[7],(y+1)*32768+.02)

    def test_native_sky_camera_is_present(self):
        self.assertIn(b'"classname" "sky_camera"',self.lump(0))
        self.assertIn(b'"targetname" "skybox_cam_level"',self.lump(0))


if __name__=='__main__': unittest.main()
