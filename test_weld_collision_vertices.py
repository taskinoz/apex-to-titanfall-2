"""weld_collision_vertices: welded collision decodes to the same triangles and render vertices keep their positions."""
import struct
import unittest

import numpy as np
from native_triangle_collision import encode
from weld_collision_vertices import weld_lumps, decode, z_flags, HEADER


def grid(n, z=0.):
    """A bumpy n x n quad grid as 2*n*n triangles sharing their corners."""
    p = lambda i, j: [i*64., j*64., z+((i*7+j*3) % 5)*8.]
    return np.array([t for i in range(n) for j in range(n) for t in
                     ([p(i, j), p(i+1, j), p(i+1, j+1)], [p(i, j), p(i+1, j+1), p(i, j+1)])], '<f4')


def lumps(groups, render):
    encoded, _ = encode(groups, first_vertex=len(render))
    positions = np.concatenate([np.asarray(render, '<f4'), np.frombuffer(encoded[3], '<f4').reshape(-1, 3)])
    lit = b''.join(struct.pack('<2I2f4B4f2i', i, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0) for i in (2, 0, 1, 2))
    return {3: positions.tobytes(), 0x42: encoded[0x42], 0x45: encoded[0x45], 0x49: lit}, positions


class WeldTests(unittest.TestCase):
    def check(self, groups):
        render = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        l, positions = lumps(groups, render + [[99, 99, 99]])  # the fourth position is unused
        changes, report = weld_lumps(l)
        new = np.frombuffer(changes[3], '<f4').reshape(-1, 3); words = np.frombuffer(changes[0x42], '<u4')
        for h, faces in zip(struct.iter_unpack(HEADER, changes[0x45]), groups):
            w = words[h[7]:h[7]+h[4]]; got = new[decode(w, h[6])]
            self.assertTrue(((w >> 10 & 127) <= 127).all() and ((w & 1023)+(w >> 10 & 127) < h[3]).all())
            self.assertTrue(np.array_equal(w & 0x70000000, z_flags(got)))
            for a, b in zip(got, np.asarray(faces, '<f4')):  # same triangle, same winding
                self.assertTrue(any(np.array_equal(a, np.roll(b, r, 0)) for r in range(3)))
        ix = np.frombuffer(changes[0x49], '<u4').reshape(-1, 11)[:, 0]
        self.assertTrue(np.array_equal(new[ix], np.asarray(render, '<f4')[[2, 0, 1, 2]]))
        return report

    def test_grid_shares_corners(self):
        report = self.check([grid(4), grid(4, 500.)])
        self.assertEqual(report['collision_positions_after'], 2*25)
        self.assertEqual(report['positions_after'], 3+50)

    def test_long_spans_reemit_positions(self):
        t = (np.random.default_rng(1).random((96, 3, 3))*1000).astype('<f4')
        t[-1, 0] = t[0, 0]; t[1, 0] = t[0, 1]  # one share 285 positions back, one close by
        report = self.check([t])
        self.assertEqual(report['collision_positions_after'], 3*96-1)


if __name__ == '__main__':
    unittest.main()
