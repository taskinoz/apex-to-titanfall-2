"""Exercise multi-level native visibility traversal and invalid geometry bounds."""
import struct,unittest
from preview_visibility import build_visibility,validate_visibility

class VisibilityTests(unittest.TestCase):
    def bounds(self,count=335):
        return b''.join(struct.pack('<8f',i*100.,(i%7)*500.,-100.,18.,10.,10.,10.,0.) for i in range(count))
    def test_multiple_native_leaves_cover_every_mesh(self):
        b=self.bounds();n,r,o=build_visibility(b)
        report=validate_visibility(n,r,o,b)
        self.assertEqual(report['reachable_meshes'],335)
        self.assertGreater(report['nodes'],3)
        self.assertEqual(sorted(struct.unpack('<335H',r)),list(range(335)))
    def test_bad_child_index_is_rejected(self):
        b=self.bounds();n,r,o=build_visibility(b);n=bytearray(n)
        struct.pack_into('<H',n,28,65535)
        with self.assertRaises(ValueError):validate_visibility(n,r,o,b)
    def test_object_bounds_must_contain_referenced_mesh(self):
        b=self.bounds();n,r,o=build_visibility(b);o=bytearray(o)
        struct.pack_into('<3f',o,0,999999.,999999.,999999.)
        with self.assertRaises(ValueError):validate_visibility(n,r,o,b)
    def test_internal_subtree_starts_follow_native_maps(self):
        from repair_preview_visibility import audit_native,ROOT
        for name,path in [('Homestead','inputs/titanfall2-homestead/maps/mp_homestead.bsp'),
                          ('Colony','inputs/titanfall2-colony/maps/mp_colony02.bsp')]:
            audit=audit_native(ROOT/path)
            self.assertTrue(audit['contiguous_subtree_ranges_verified'],name)
            self.assertGreater(audit['internal_nodes'],1000)
        b=self.bounds(719);n,r,o=build_visibility(b)
        nodes=list(struct.iter_unpack('<3f2BH3f2H',n))
        references=struct.unpack('<719H',r)
        def recursive_meshes(index):
            x=nodes[index]
            result=list(references[x[10]:x[10]+x[4]])
            for child in range(x[9],x[9]+x[3]):result.extend(recursive_meshes(child))
            return result
        self.assertTrue(any(x[3] and x[10]>0 for x in nodes))
        for i,x in enumerate(nodes):
            cursor=x[10]+x[4]
            for child in nodes[x[9]:x[9]+x[3]]:
                self.assertEqual(child[10],cursor)
                cursor+=child[5]
            self.assertEqual(cursor,x[10]+x[5])
            # A whole visible branch must submit the same meshes as descending
            # its leaves; this was the missing check behind distance/angle pop-in.
            self.assertEqual(list(references[x[10]:x[10]+x[5]]),recursive_meshes(i))
    def test_zero_internal_subtree_start_is_rejected(self):
        b=self.bounds(719);n,r,o=build_visibility(b);n=bytearray(n)
        for i in range(len(n)//32):
            node=struct.unpack_from('<3f2BH3f2H',n,i*32)
            if node[3] and node[10]>0:
                struct.pack_into('<H',n,i*32+30,0);break
        else:self.fail('Expected a later internal subtree')
        with self.assertRaisesRegex(ValueError,'not contiguous'):validate_visibility(n,r,o,b)
if __name__=='__main__':unittest.main()
