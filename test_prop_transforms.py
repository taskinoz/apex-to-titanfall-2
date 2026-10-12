"""Source prop placement must preserve handedness, pitch direction and scale."""
import unittest
import tempfile
from pathlib import Path
from stage_prop_geometry import rotation,transform,load_mesh


class PropTransformTests(unittest.TestCase):
    def assertVector(self,actual,expected):
        for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=6)

    def test_yaw_rotates_source_forward_toward_left(self):
        self.assertVector(transform((1,0,0),rotation((0,90,0))),(0,1,0))

    def test_positive_source_pitch_points_forward_down(self):
        self.assertVector(transform((1,0,0),rotation((90,0,0))),(0,0,-1))

    def test_scale_and_translation_preserve_local_dimensions(self):
        origin=(100,200,-300)
        matrix=rotation((0,90,0))
        a=transform((0,0,0),matrix,origin,2)
        b=transform((10,0,0),matrix,origin,2)
        self.assertVector(a,origin);self.assertVector(b,(100,220,-300))

    def test_rotation_preserves_right_handed_basis(self):
        from build_preview_source import cross
        matrix=rotation((17,73,-31))
        x=transform((1,0,0),matrix);y=transform((0,1,0),matrix);z=transform((0,0,1),matrix)
        self.assertVector(cross(x,y),z)


class PropSectionTests(unittest.TestCase):
    def fixture(self,folder,tail='end\n'):
        qc=Path(folder)/'model.qc'
        qc.write_text('$bodygroup "body" { studio "model.smd" }\n')
        triangle='default_material\n0 0 0 0 0 0 1 0 0\n0 1 0 0 0 0 1 1 0\n0 0 1 0 0 0 1 0 1\n'
        (Path(folder)/'model.smd').write_text('version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\ntriangles\n'+triangle+'end\ntriangles\n'+triangle+tail)
        return qc

    def test_legion_multiple_sections_and_incremental_restoration(self):
        with tempfile.TemporaryDirectory() as folder:
            qc=self.fixture(folder)
            full,_=load_mesh(qc);missing,_=load_mesh(qc,missing_only=True)
            self.assertEqual(len(full),2)
            self.assertEqual(missing,full[1:])

    def test_truncated_later_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):load_mesh(self.fixture(folder,tail=''))


if __name__=='__main__':unittest.main()
