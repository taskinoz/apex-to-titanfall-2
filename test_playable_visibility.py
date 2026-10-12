"""Independent native acceptance and immutable gameplay/render data checks."""
import math, struct, unittest
from repair_playable_visibility import ROOT, SOURCE, TARGET, PACKAGE, BASE, CAMERA_MIN, CAMERA_MAX
from repair_preview_index_padding import read_lumps, validate_index_padding
from preview_visibility import validate_visibility
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY
from finalize_lighting_release import digest
import sys
sys.path.insert(0, str(ROOT/'tools/lighting-python'))
import numpy as np

class PlayableVisibilityTests(unittest.TestCase):
    def test_only_two_culling_payloads_change(self):
        with SOURCE.open('rb') as a, TARGET.open('rb') as b:
            ah=a.read(2064); bh=b.read(2064)
            for lid in range(128):
                if lid in (0x77, 0x79): continue
                ao,an,av,ap=struct.unpack_from('<4I',ah,16+lid*16)
                bo,bn,bv,bp=struct.unpack_from('<4I',bh,16+lid*16)
                self.assertEqual((an,av,ap),(bn,bv,bp),hex(lid))
                a.seek(ao); b.seek(bo)
                if lid==0x23:
                    aa=bytearray(a.read(an)); bb=bytearray(b.read(bn))
                    for j in range(struct.unpack_from('<I',aa)[0]):
                        off=4+j*16+8
                        self.assertEqual(struct.unpack_from('<I',aa,off)[0]-ao,
                                         struct.unpack_from('<I',bb,off)[0]-bo)
                        struct.pack_into('<I',aa,off,0);struct.pack_into('<I',bb,off,0)
                    self.assertEqual(aa,bb)
                else:
                    for at in range(0,an,8*1024*1024):
                        n=min(8*1024*1024,an-at);self.assertEqual(a.read(n),b.read(n),hex(lid))

    def test_native_reference_ownership_and_flat_queue(self):
        l=read_lumps(TARGET,(0x51,0x77,0x78,0x79))
        proof=validate_visibility(l[0x77],l[0x78],l[0x79],l[0x51])
        self.assertEqual(proof['reachable_meshes'],4586)
        nodes=list(struct.iter_unpack('<3f2BH3f2H',l[0x77]))
        self.assertLess(len(nodes),1024) # native pending-node ring
        self.assertEqual(nodes[0][3],len(nodes)-1)
        self.assertEqual(nodes[0][5],4586)
        for row in nodes[1:]:
            self.assertEqual(row[3],0);self.assertLessEqual(row[4],255)
            self.assertEqual(row[4],row[5])
        self.assertEqual(read_lumps(SOURCE,(0x78,))[0x78],l[0x78])

    def test_camera_inside_native_classifier_for_outdoor_and_tunnels(self):
        l=read_lumps(TARGET,(0x77,0x79))
        boxes=np.frombuffer(l[0x77]+l[0x79],'<f4').reshape(-1,8)
        low=boxes[:,:3].astype(float);high=boxes[:,4:7].astype(float)
        # Actual reported missing-rock, crate, stairs and tunnel/barrier locations,
        # plus supported-domain corners and regular outdoor/airborne samples.
        cameras=[(-4176.4,-1463.9,-950.6),(-2163.4,3016.3,-910.4),
                 (-1330.3,3043.2,-864),(3587.7,2513.7,-1088.9),(4484,474,-1088.1),
                 (1839.9,-782,-1136.7),(186,-5211,-891),(-1716,-3994,-899),
                 (1221,-2481,57),(-4704.6,16.5,-671.5),(4866.9,137.4,-682.4)]
        cameras += [(x,y,z) for x in (CAMERA_MIN[0],0,CAMERA_MAX[0])
                    for y in (CAMERA_MIN[1],0,CAMERA_MAX[1])
                    for z in (CAMERA_MIN[2],0,CAMERA_MAX[2])]
        for camera in cameras:
            q=np.array(camera)
            # client+0x2e9983 combines outside-axis bits. Zero bypasses silhouette clipping.
            self.assertTrue(np.all((low<=q)&(high>=q)))
            for pitch in range(-90,91,30):
                for yaw in range(0,360,45):
                    p,y=map(math.radians,(pitch,yaw))
                    forward=np.array([math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),-math.sin(p)])
                    right=np.array([-math.sin(y),math.cos(y),0]);up=np.cross(right,forward)
                    for normal in (forward+right,forward-right,forward+up,forward-up):
                        support=np.where(normal>=0,high,low)
                        self.assertTrue(np.all((support-q)@normal>=-1e-5))

    def test_complete_world_draw_fits_with_padding(self):
        before=audit(SOURCE);after=audit(TARGET)
        self.assertEqual(after['real_triangles'],before['real_triangles'])
        self.assertEqual(after['native_padded_indices'],before['native_padded_indices'])
        self.assertLess(after['native_padded_indices'],WORLD_INDEX_CAPACITY*.85)
        l=read_lumps(TARGET,(0x50,0x4f,0x52))
        validate_index_padding(l[0x50],l[0x4f],l[0x52])

    def test_working_assets_and_character_lighting_retained(self):
        self.assertEqual(digest(SOURCE.with_suffix('.stbsp')),digest(TARGET.with_suffix('.stbsp')))
        for p in BASE.rglob('*'):
            if not p.is_file():continue
            rel=p.relative_to(BASE)
            if rel.as_posix() in ('mod.json','build-status.json','mod/maps/mp_phase_runner.bsp'):continue
            self.assertEqual(digest(p),digest(PACKAGE/rel),str(rel))

if __name__=='__main__':unittest.main()
