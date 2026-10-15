"""Regressions for the Firing Range 0.4.0 tooling fixes."""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import compact_preview_bsp
from read_vg_static import packed_normal


def pack_normal(axis, negative, b, c):
    return (axis << 29) | (int(negative) << 28) | ((b+256) << 19) | ((c+256) << 10)


class PackedNormalTest(unittest.TestCase):
    def test_axis_order_matches_source_vertex_shader(self):
        # rib_giant_large_01 VS: axis 0 -> (a,b,c), 1 -> (c,a,b), 2 -> (b,c,a).
        a, b, c = 255., 40., -90.
        length = (a*a+b*b+c*c)**.5
        for axis, expected in ((0, (a, b, c)), (1, (c, a, b)), (2, (b, c, a))):
            got = packed_normal(pack_normal(axis, False, int(b), int(c)))
            for x, y in zip(got, expected):
                self.assertAlmostEqual(x, y/length, places=6)

    def test_legacy_flag_is_compatibility_only(self):
        value = pack_normal(1, True, 17, -200)
        self.assertEqual(packed_normal(value), packed_normal(value, legacy=True))


def synthetic_bsp(path, game_offset_pad):
    """rBSP with lump 0 and a one-entry game lump whose payload it contains."""
    header = bytearray(2064)
    struct.pack_into('<4s3I', header, 0, b'rBSP', 37, 0, 127)
    body = bytearray()
    lump0 = b'\x11' * (16 + game_offset_pad)
    lump0_at = 2064
    body += lump0
    body += bytes((-(2064+len(body))) % 16)
    game_at = 2064 + len(body)
    payload = b'prps-payload-bytes!!'
    game = bytearray(struct.pack('<I', 1) + struct.pack('<4sHHII', b'prps', 0, 13, game_at+20, len(payload)) + payload)
    body += game
    struct.pack_into('<4I', header, 16, lump0_at, len(lump0), 0, 0)
    struct.pack_into('<4I', header, 16+0x23*16, game_at, len(game), 0, 0)
    path.write_bytes(bytes(header)+bytes(body))
    return bytes(game)


class GameLumpRelocationTest(unittest.TestCase):
    def check(self, output):
        data = output.read_bytes()
        at, n, _, _ = struct.unpack_from('<4I', data, 16+0x23*16)
        ptr, length = struct.unpack_from('<2I', data, at+4+8)
        self.assertEqual(ptr, at+20)
        self.assertEqual(data[ptr:ptr+length], b'prps-payload-bytes!!')

    def test_relocates_when_game_lump_is_copied(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compact_preview_bsp, 'validate_bsp', return_value=[]):
            src, out = Path(d)/'a.bsp', Path(d)/'b.bsp'
            synthetic_bsp(src, 0)
            compact_preview_bsp.compact(src, out, {0: b'\x22'*48})
            self.check(out)

    def test_relocates_when_game_lump_is_passed_as_replacement(self):
        # repair_firing_range_surfaces passes every source lump as a replacement.
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compact_preview_bsp, 'validate_bsp', return_value=[]):
            src, out = Path(d)/'a.bsp', Path(d)/'b.bsp'
            game = synthetic_bsp(src, 0)
            replacements = {0: b'\x22'*48, 0x23: game}
            compact_preview_bsp.compact(src, out, replacements)
            self.check(out)
            self.assertEqual(replacements[0x23], game, 'Caller buffers must not be mutated')

    def test_rejects_edited_game_lump_replacement(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(compact_preview_bsp, 'validate_bsp', return_value=[]):
            src, out = Path(d)/'a.bsp', Path(d)/'b.bsp'
            game = bytearray(synthetic_bsp(src, 0)); game[-1] ^= 1
            with self.assertRaises(ValueError):
                compact_preview_bsp.compact(src, out, {0x23: bytes(game)})



class WorldUvClassifierTest(unittest.TestCase):
    """Albedo UV tracing on the two shapes seen in Apex wld pixel shaders."""

    WORLD = '''dcl_temps 4
add r0.xyz, v1.xyzx, cb2[0].yzwy
mov r0.w, -r0.y
dp2 r1.x, r0.xwxx, cb0[0].xyxx
dp2 r1.z, r0.xwxx, cb0[0].zwzz
add r1.xy, r1.xzxx, cb0[1].xyxx
dp2 r1.z, r0.xwxx, cb0[1].zwzz
add r2.x, r1.z, cb0[2].z
dp2 r0.w, r0.xwxx, cb0[2].xyxx
add r2.y, r0.w, cb0[2].w
sample_indexable(texture2d)(float,float,float,float) r0.w, r1.xyxx, t5.yzwx, s2
sample_indexable(texture2d)(float,float,float,float) r6.xyz, r2.xyxx, t0.xyzw, s2
'''
    MESH = '''dcl_temps 4
add r0.xyz, v1.xyzx, cb2[0].yzwy
dp2 r0.w, v0.xyxx, cb0[0].xyxx
add r1.x, r0.w, cb0[1].x
dp2 r0.w, v0.xyxx, cb0[0].zwzz
add r1.y, r0.w, cb0[1].y
sample_indexable(texture2d)(float,float,float,float) r3.xyzw, r1.xyxx, t0.xyzw, s2
'''

    def test_world_projection_slots(self):
        from classify_world_uv import albedo_source
        self.assertEqual(albedo_source(self.WORLD, 0), dict(kind='world', slot=2, scroll=False))
        self.assertEqual(albedo_source(self.WORLD, 5), dict(kind='world', slot=1, scroll=False))

    def test_mesh_uv_transform_is_not_world(self):
        from classify_world_uv import albedo_source
        self.assertEqual(albedo_source(self.MESH, 0), dict(kind='mesh', slot=1, scroll=False))

    def test_projection_formula(self):
        import numpy as np
        from repair_party_surfaces import project
        info = dict(rot_x=[1/256, 0], rot_y=[0, 1/256], translate=[0, 0])
        np.testing.assert_allclose(project(info, np.array([[256., 512., 7.]])), [[1., -2.]])



class TriggerPlaneTranslationTest(unittest.TestCase):
    """Decoded trigger pieces are relative to the entity origin, in source coordinates."""

    def test_planes_follow_origin_and_map_offset(self):
        import numpy as np
        from unittest import mock
        import analyse_visibility as av
        # Unit cube [-1,1]^3 as n.x <= d planes, entity at source (100,0,0), map offset (-32000,7000,28000).
        planes = [[1, 0, 0, 1], [-1, 0, 0, 1], [0, 1, 0, 1], [0, -1, 0, 1], [0, 0, 1, 1], [0, 0, -1, 1]]
        scene = {'source_entities': [{'classname': 'trigger_out_of_bounds', 'origin': '100 0 0'}]}
        with mock.patch.object(av, 'pieces', create=True),              mock.patch('decode_source_trigger_volumes.pieces', return_value=[{'planes': planes}]),              mock.patch.object(av, 'folder') as folder,              mock.patch.dict(av.CONFIG, {'t': {'offset': [-32000, 7000, 28000]}}):
            folder.return_value.__truediv__.return_value.read_text.return_value = __import__('json').dumps(scene)
            P = av.triggers('t')
        inside = av.inside(np.array([[-31900., 7000., 28000.], [100., 0., 0.]]), P)
        self.assertEqual(inside.tolist(), [True, False])


if __name__ == '__main__':
    unittest.main()
