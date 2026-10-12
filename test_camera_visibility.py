"""Check native camera acceptance and immutable draw/physics data independently."""
import math, struct, unittest
from pathlib import Path
from repair_camera_visibility import build_camera_visibility, CAMERA_MIN, CAMERA_MAX
from preview_visibility import validate_visibility
from repair_preview_index_padding import read_lumps


class CameraVisibilityTests(unittest.TestCase):
    def test_count_limits_and_reference_order(self):
        bounds = b''.join(struct.pack('<8f', i*10, 0, 0, 2, 1, 1, 1, 0) for i in range(701))
        refs = struct.pack('<701H', *reversed(range(701)))
        nodes, actual_refs, objects = build_camera_visibility(bounds, refs)
        self.assertEqual(actual_refs, refs)
        self.assertEqual(len(nodes)//32, 4)
        self.assertEqual(validate_visibility(nodes, actual_refs, objects, bounds)['reachable_meshes'], 701)
        self.assertEqual(struct.unpack_from('<3f2BH3f2H', nodes)[3:6], (3, 0, 701))

    def test_reject_bad_inputs(self):
        bounds = struct.pack('<8f', 0, 0, 0, 2, 1, 1, 1, 0)
        for refs in (b'', struct.pack('<H', 1), struct.pack('<2H', 0, 0)):
            with self.assertRaises(ValueError): build_camera_visibility(bounds, refs)
        for limit in (0, 256):
            with self.assertRaises(ValueError): build_camera_visibility(bounds, b'\0\0', leaf_size=limit)
        with self.assertRaises(ValueError):
            build_camera_visibility(bounds, b'\0\0', camera_max=CAMERA_MIN)

    def test_production_visibility_geometry_and_collision_preservation(self):
        root = Path(__file__).resolve().parent/'output/phase-runner'
        before = read_lumps(root/'preview-full-collision/mp_phase_runner_preview.bsp', range(128))
        after = read_lumps(root/'preview-camera-visibility/mp_phase_runner_preview.bsp', range(128))
        for lid in range(128):
            if lid not in (0x23, 0x77, 0x79):
                self.assertEqual(before[lid], after[lid], f'Unexpected modified lump {lid:#x}')
        validate_visibility(after[0x77], after[0x78], after[0x79], after[0x51])
        # Game-lump directory pointers relocate when compacting. Its payload must
        # still match after normalizing those absolute pointers.
        def normalized(data):
            result = bytearray(data)
            for j in range(struct.unpack_from('<I', result)[0]):
                struct.pack_into('<I', result, 4+16*j+8, 0)
            return result
        self.assertEqual(normalized(before[0x23]), normalized(after[0x23]))

    def test_camera_sweep_native_frustum_support_and_inside_mask(self):
        import numpy as np
        path = Path(__file__).resolve().parent/'output/phase-runner/preview-camera-visibility/mp_phase_runner_preview.bsp'
        data = read_lumps(path, (0x77, 0x79))
        # Native node and object layouts both contain minXYZ at 0, maxXYZ at 16.
        boxes = np.frombuffer(data[0x77]+data[0x79], dtype='<f4').reshape(-1, 8)
        lo, hi = boxes[:, :3].astype(float), boxes[:, 4:7].astype(float)
        positions = [(-4176.4,-1463.9,-950.6),(-2163.4,3016.3,-910.4),
                     (3587.7,2513.7,-1088.9),(4484,474,-1088.1),
                     (1839.9,-782,-1136.7),(-761.37,-4444.36,-927)]
        positions += [(x,y,z) for x in (-12000,12000) for y in (-12000,12000) for z in (-4096,4096)]
        checked = 0
        for camera in positions:
            camera = np.array(camera)
            # This is the native camera-inside classification at client+0x2e9983:
            # no outside-axis bits means accept without projected silhouette clip.
            self.assertTrue(np.all((lo <= camera) & (hi >= camera)))
            for pitch in range(-90, 91, 15):
                for yaw in range(0, 360, 30):
                    p,y = math.radians(pitch),math.radians(yaw)
                    forward=np.array([math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),-math.sin(p)])
                    right=np.array([-math.sin(y),math.cos(y),0])
                    up=np.cross(right,forward)
                    for normal in (forward+right,forward-right,forward+up,forward-up):
                        # Four camera-origin plane maximum-support tests. A box
                        # containing the camera cannot be wholly outside a plane.
                        support = np.where(normal >= 0, hi, lo)
                        distance = (support-camera) @ normal
                        self.assertTrue(np.all(distance >= -1e-5))
                    checked += 1
        self.assertEqual(checked, 2184)


if __name__ == '__main__': unittest.main()
