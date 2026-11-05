"""weld_shadow_meshes: welded shadow meshes decode to the same triangles; alpha meshes are untouched."""
import struct
import unittest

import numpy as np
from weld_shadow_meshes import weld_lumps


def quads(n, z):
    p = lambda i, j: [i*64., j*64., z]
    return np.array([t for i in range(n) for j in range(n)
                     for t in ([p(i, j), p(i+1, j), p(i+1, j+1)], [p(i, j), p(i+1, j+1), p(i, j+1)])], '<f4')


class ShadowWeldTests(unittest.TestCase):
    def test_meshes_share_positions_and_keep_triangles(self):
        a, b = quads(3, 0.), quads(2, 100.)
        positions = np.concatenate([a.reshape(-1, 3), b.reshape(-1, 3)])
        indices = np.concatenate([np.arange(len(a)*3), np.arange(len(b)*3), [0, 1, 2]]).astype('<u2')
        meshes = struct.pack('<2I2h', 0, len(a), 1, -1)+struct.pack('<2I2h', len(a)*3, len(b), 1, -1) + \
            struct.pack('<2I2h', 0, 1, 0, 3)  # an alpha mesh indexing 0x7D
        changes, report = weld_lumps({0x7C: positions.tobytes(), 0x7E: indices.tobytes(), 0x7F: meshes})
        new = np.frombuffer(changes[0x7C], '<f4').reshape(-1, 3); ix = np.frombuffer(changes[0x7E], '<u2')
        m = list(struct.iter_unpack('<2I2h', changes[0x7F]))
        self.assertEqual(report['positions_after'], 16+9)
        self.assertTrue(np.array_equal(new[m[0][0]+ix[:len(a)*3]].reshape(-1, 3, 3), a))
        self.assertTrue(np.array_equal(new[m[1][0]+ix[len(a)*3:len(a)*3+len(b)*3]].reshape(-1, 3, 3), b))
        self.assertEqual(m[2], (0, 1, 0, 3)); self.assertEqual(list(ix[-3:]), [0, 1, 2])
        self.assertEqual(len(changes[0x7E]), len(indices)*2)


if __name__ == '__main__':
    unittest.main()
