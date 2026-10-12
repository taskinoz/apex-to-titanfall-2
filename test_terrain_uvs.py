import unittest
from restore_terrain_uvs import transformed_uv


class TerrainUVTests(unittest.TestCase):
    def test_identity_keeps_imported_coordinates(self):
        self.assertEqual(transformed_uv(4,-8,(1,0,0,1,0,0)),(4,-8))

    def test_world_scale_undoes_v_flip_first(self):
        self.assertEqual(transformed_uv(1024,1-2048,(1/1024,0,0,1/1024,0,0)),(1,-1))

    def test_rotation_and_translation_use_source_coordinates(self):
        self.assertEqual(transformed_uv(2,1-3,(0,-1,1,0,10,20)),(7,-21))

    def test_fractional_coordinates_are_preserved(self):
        u,v=transformed_uv(26245.8125,1-11567.96875,(1/1024,0,0,1/1024,0,0))
        self.assertAlmostEqual(u,25.63067626953125)
        self.assertAlmostEqual(v,-10.296844482421875)


if __name__ == '__main__': unittest.main()
