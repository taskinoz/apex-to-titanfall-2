"""Regression checks for package preprocessing and BSP collision validation."""
import json
import struct
import tempfile
import unittest
from compression import zstd
from pathlib import Path

from decompress_rpak import decompress, normalize_segments
from inspect_maps import inspect_bsp
from decode_collision import decode


class PackageTests(unittest.TestCase):
    def test_collision_respects_model_vertex_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'map.bsp'
            def lump(index,data):
                path.with_name(f'{path.name}.{index:04x}.bsp_lump').write_bytes(data)
            bounds = [0,0,0,0,2,0,0,0, 0,0,0,0,2,0,0,0, 0]*1
            bounds = bounds[:16] + [0]*8
            lump(18,struct.pack('<24h4I',*bounds,0,0,0x14,0x11))
            lump(19,struct.pack('<2I',0,1<<20))
            lump(3,struct.pack('<12f',100,100,100,0,0,0,2,0,0,0,2,0))
            lump(16,struct.pack('<I',1))
            lump(14,struct.pack('<6f2I4i4f',0,0,0,2,2,0,0,0,0,0,1,0,0,0,0,1/65535))
            result = decode(path,Path(folder)/'correct')
            self.assertEqual(result['regular_polygons'],1)
            self.assertEqual(result['errors'],[])
            self.assertEqual(result['polygons_outside_parent_bounds'],0)
            wrong = decode(path,Path(folder)/'wrong',vertex_offset=0)
            self.assertEqual(wrong['polygons_outside_parent_bounds'],1)

    def test_decoding_preserves_payload_and_source(self):
        payload = bytes(range(256)) * 64
        encoded = zstd.compress(payload)
        header = bytearray(128)
        header[:4] = b'RPak'
        struct.pack_into('<HH', header, 4, 8, 0x8020)
        struct.pack_into('<Q', header, 24, 128 + len(encoded))
        struct.pack_into('<Q', header, 48, 128 + len(payload))
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'source.rpak', Path(folder)/'output.rpak'
            original = bytes(header) + encoded
            source.write_bytes(original)
            decompress(source, output)
            result = output.read_bytes()
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(result[128:], payload)
            self.assertEqual(struct.unpack_from('<H',result,6)[0],0x20)
            self.assertEqual(struct.unpack_from('<Q',result,24)[0],len(result))
            with self.assertRaises(ValueError):
                decompress(source, source)

    def test_segment_padding_recomputed_without_changing_pages(self):
        data = bytearray(128 + 16 + 24)
        struct.pack_into('<5H',data,72,0,0,1,2,0)
        struct.pack_into('<IIQ',data,128,1,16,6)
        struct.pack_into('<III',data,144,0,4,3)
        struct.pack_into('<III',data,156,0,8,3)
        original_pages = data[144:]
        changes = normalize_segments(data)
        self.assertEqual(changes,[dict(segment=0,old_size=6,new_size=11)])
        self.assertEqual(data[144:],original_pages)
        self.assertEqual(normalize_segments(data),[])
        struct.pack_into('<I',data,160,3)
        with self.assertRaises(ValueError):
            normalize_segments(data)

    def test_map_inputs_are_consistent(self):
        root = Path(__file__).resolve().parent
        report = json.loads((root/'output/phase-runner/compatibility.json').read_text())
        validation = report['collision_structure_validation']
        self.assertEqual(validation['nodes'],27343)
        self.assertEqual(validation['invalid_active_axis_bounds'],0)
        self.assertEqual(validation['invalid_references'],[])
        client = root/'inputs/extracted-client/maps'
        server = root/'inputs/extracted-server/maps'
        files = list(server.glob('*.bsp_lump'))
        self.assertEqual(len(files),20)
        for path in files:
            self.assertEqual(path.read_bytes(),(client/path.name).read_bytes())
        self.assertEqual(inspect_bsp(client/'mp_rr_arena_phase_runner.bsp')['problems'],[])


if __name__ == '__main__':
    unittest.main()
