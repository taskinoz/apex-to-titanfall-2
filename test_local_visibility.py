"""Exercise native portal/camera safety against independent spatial expectations."""
import bisect, collections, copy, json, math, struct, unittest
from pathlib import Path
from rebuild_local_visibility import build_cells, validate, locate, SOURCE, TARGET, CUTS, CAMERA_MIN, CAMERA_MAX
from repair_preview_index_padding import read_lumps, validate_index_padding
from audit_world_draw_budget import audit, WORLD_INDEX_CAPACITY


class LocalVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current=read_lumps(TARGET,(1,0x50,0x51,0x4f,0x52,*range(0x6a,0x7a)))
        cls.reference=read_lumps(SOURCE,(1,0x50,0x51,0x4f,0x52))

    def test_production_portals_and_boundary_lookup(self):
        proof=validate(self.current,self.current[0x51])
        self.assertEqual(proof['cells'],16)
        self.assertEqual(proof['directed_open_portals'],48)
        self.assertEqual(proof['unique_meshes'],4561)
        self.assertLess(proof['maximum_pending_nodes'],1024)
        self.assertLess(proof['object_references'],32768)
        # Independent directional flood: every cell is reachable, both ways.
        cells=list(struct.iter_unpack('<2H2h',self.current[0x6b]))
        portals=list(struct.iter_unpack('<4B2HI',self.current[0x6c]))
        for start in range(16):
            visited={start};queue=collections.deque([start])
            while queue:
                c=cells[queue.popleft()]
                for p in portals[c[1]:c[1]+c[0]]:
                    if p[1]==0 and p[5] not in visited:visited.add(p[5]);queue.append(p[5])
            self.assertEqual(len(visited),16)

    def test_tunnel_routes_and_reported_outdoor_camera_angles_are_protected(self):
        root=Path(__file__).resolve().parent
        routes=json.loads((root/'output/phase-runner/preview-tunnel-walkways/tunnel-walkways.json').read_text())
        ns=list(struct.iter_unpack('<3f2BH3f2H',self.current[0x77]))
        obs=list(struct.iter_unpack('<3fI3fI',self.current[0x79]))
        cameras=[tuple(p[:2])+ (p[2]+64.,) for r in routes['routes'] for p in r['points']]
        cameras += [(-4176.4,-1463.9,-950.6),(-2163.4,3016.3,-910.4),
                    (3587.7,2513.7,-1088.9),(4484,474,-1088.1),(1839.9,-782,-1136.7)]
        # Check every local object for every route sample, independently of tree walk.
        boxes=[(o[:3],o[4:7]) for o in obs]
        for camera in cameras:
            cell=locate(self.current,camera);r=ns[cell]
            for lo,hi in boxes[r[10]:r[10]+r[5]]:
                self.assertTrue(all(lo[k]<=camera[k]<=hi[k] for k in range(3)))
        # Native projected-silhouette acceptance reduces to zero outside-axis
        # bits for these boxes, independently of pitch/yaw. Side-plane support
        # stays nonnegative even looking straight up/down at the sample routes.
        for camera in cameras[::20]:
            r=ns[locate(self.current,camera)]
            for pitch in (-90,-45,0,45,90):
                for yaw in range(0,360,45):
                    p,y=math.radians(pitch),math.radians(yaw)
                    forward=(math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),-math.sin(p))
                    right=(-math.sin(y),math.cos(y),0.)
                    up=(right[1]*forward[2],-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0])
                    for normal in [tuple(forward[k]+sign*axis[k] for k in range(3))
                                   for sign in (-1,1) for axis in (right,up)]:
                        for lo,hi in boxes[r[10]:r[10]+r[5]]:
                            support=tuple(hi[k] if normal[k]>=0 else lo[k] for k in range(3))
                            self.assertGreaterEqual(sum((support[k]-camera[k])*normal[k] for k in range(3)),-.001)
        self.assertGreater(len(cameras),450)

    def test_geometry_membership_and_backdrop_cover(self):
        ms=list(struct.iter_unpack('<8f',self.current[0x51]));ns=list(struct.iter_unpack('<3f2BH3f2H',self.current[0x77]))
        refs=list(struct.unpack('<'+'H'*(len(self.current[0x78])//2),self.current[0x78]))
        actual=[set(refs[r[10]:r[10]+r[5]]) for r in ns[:16]]
        for i,m in enumerate(ms):
            lo=[m[k]-m[k+4]-1 for k in range(3)];hi=[m[k]+m[k+4]+1 for k in range(3)]
            expected={y*4+x for x in range(bisect.bisect_left(CUTS,lo[0]),bisect.bisect_right(CUTS,hi[0])+1)
                                for y in range(bisect.bisect_left(CUTS,lo[1]),bisect.bisect_right(CUTS,hi[1])+1)}
            self.assertEqual({cell for cell,ids in enumerate(actual) if i in ids},expected)

    def test_opaque_barriers_and_old_visibility_cannot_sneak_back(self):
        for lid in (0x72,0x73,0x75,0x76):self.assertEqual(self.current[lid],b'')
        for lid in (0x50,0x51,0x4f,0x52):self.assertEqual(self.current[lid],self.reference[lid])
        self.assertTrue(self.current[1].startswith(self.reference[1]))
        report=audit(TARGET)
        self.assertLessEqual(report['native_padded_indices'],int(WORLD_INDEX_CAPACITY*.85))
        validate_index_padding(self.current[0x50],self.current[0x4f],self.current[0x52])

    def test_reject_missing_reverse_portal(self):
        damaged=dict(self.current);p=bytearray(damaged[0x6c]);struct.pack_into('<H',p,6,0);damaged[0x6c]=p
        with self.assertRaisesRegex(ValueError,'Reciprocal'):validate(damaged,damaged[0x51])

    def test_reject_missing_local_camera_coverage(self):
        damaged=dict(self.current);obs=bytearray(damaged[0x79]);struct.pack_into('<f',obs,0,CAMERA_MAX[0]);damaged[0x79]=obs
        with self.assertRaises(ValueError):validate(damaged,damaged[0x51])

    def test_preserve_lighting_collision_and_walkways_in_every_other_lump(self):
        changed={1,*range(0x6a,0x7a),0x23}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ha=a.read(2064);hb=b.read(2064)
            for lid in range(128):
                oa,na=struct.unpack_from('<2I',ha,16+16*lid);ob,nb=struct.unpack_from('<2I',hb,16+16*lid)
                if lid in changed:continue
                self.assertEqual(na,nb)
                a.seek(oa);b.seek(ob)
                for start in range(0,na,1024*1024):
                    size=min(1024*1024,na-start);self.assertEqual(a.read(size),b.read(size),f'Lump {lid:#x} changed')
            def normalized(f,h):
                o,n=struct.unpack_from('<2I',h,16+16*0x23);f.seek(o);data=bytearray(f.read(n))
                for j in range(struct.unpack_from('<I',data)[0]):struct.pack_into('<I',data,4+16*j+8,0)
                return data
            self.assertEqual(normalized(a,ha),normalized(b,hb))
        self.assertEqual(SOURCE.with_suffix('.stbsp').read_bytes(),TARGET.with_suffix('.stbsp').read_bytes())

if __name__=='__main__':unittest.main()
