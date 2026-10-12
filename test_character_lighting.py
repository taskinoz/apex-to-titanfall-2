"""Independent moving-model lighting and preservation regressions."""
import itertools,json,struct,subprocess,tempfile,unittest
from build_character_lighting import ROOT,SOURCE,TARGET,OUT,np,cKDTree
from audit_character_lighting import PATHS
from repair_preview_index_padding import read_lumps
from finalize_lighting_release import digest
from audit_world_draw_budget import audit
from package_character_lighting import PACKAGE

def nearest_native(tree,refs,q):
    # Native tree nodes address an adjacent low/high child pair; leaves own refs.
    best=float('inf');answer=None;stack=[(0,0)];tested=0;peak=1
    while stack:
        index,bound=stack.pop()
        if bound>best:continue
        tag,value=tree[index];kind=tag&3;first=tag>>2
        if kind==3:
            p=refs[first:first+value,:3];d=((p-q)**2).sum(1);k=int(d.argmin());tested+=len(p)
            if d[k]<best:best=float(d[k]);answer=first+k
        else:
            cut=struct.unpack('<f',struct.pack('<I',value))[0];delta=float(q[kind]-cut)
            high=delta>=0;stack.append((first+(not high),delta*delta));stack.append((first+high,0));peak=max(peak,len(stack))
    return answer,best,tested,peak

class CharacterLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.l=read_lumps(TARGET,(4,6,7,0x65,0x66,0x67,0x68));cls.refs=np.array(list(struct.iter_unpack('<3fIi',cls.l[0x68])))
        cls.tree=list(struct.iter_unpack('<2I',cls.l[0x67]));cls.proof=np.load(OUT/'probe-proof.npz')

    def test_all_existing_bsp_payloads_and_other_assets_exact(self):
        changed={4,0x65,0x67,0x68,0x23}
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            ah=a.read(2064);bh=b.read(2064)
            for i in range(128):
                if i in changed:continue
                ao,an,av,ap=struct.unpack_from('<4I',ah,16+i*16);bo,bn,bv,bp=struct.unpack_from('<4I',bh,16+i*16)
                self.assertEqual((an,av,ap),(bn,bv,bp),hex(i));a.seek(ao);b.seek(bo)
                for at in range(0,an,8*1024*1024):size=min(8*1024*1024,an-at);self.assertEqual(a.read(size),b.read(size),hex(i))
        self.assertEqual(audit(SOURCE)['native_padded_indices'],audit(TARGET)['native_padded_indices'])
        self.assertEqual(digest(SOURCE.with_suffix('.stbsp')),digest(TARGET.with_suffix('.stbsp')))

    def test_native_tree_parent_ranges_and_reference_ownership(self):
        n=len(self.refs);self.assertEqual(struct.unpack('<i6I',self.l[4]),(0,0,n,0,n,0,len(self.tree)))
        self.assertEqual(len(self.l[0x65]),n*48);self.assertEqual(self.l[6],b'');self.assertEqual(self.l[7],b'');self.assertEqual(self.l[0x66],b'')
        seen=[];nodes=set();stack=[(0,[-float('inf')]*3,[float('inf')]*3)]
        while stack:
            i,lo,hi=stack.pop();self.assertNotIn(i,nodes);nodes.add(i);tag,value=self.tree[i];first=tag>>2;k=tag&3
            if k==3:
                self.assertGreater(value,0);self.assertLessEqual(value,8);seen.extend(range(first,first+value));p=self.refs[first:first+value,:3]
                self.assertTrue((p>=np.array(lo)-.01).all());self.assertTrue((p<=np.array(hi)+.01).all())
            else:
                cut=struct.unpack('<f',struct.pack('<I',value))[0];low_hi=hi.copy();low_hi[k]=cut;high_lo=lo.copy();high_lo[k]=cut
                stack.extend([(first,lo,low_hi),(first+1,high_lo,hi)])
        self.assertEqual(len(nodes),len(self.tree));self.assertEqual(sorted(seen),list(range(n)))
        self.assertEqual(sorted(self.refs[:,3].astype(int)),list(range(n)));self.assertTrue((self.refs[:,4]==0).all())

    def test_native_nearest_lookup_matches_independent_spatial_queries(self):
        rng=np.random.default_rng(38);points=self.refs[:,:3];index=cKDTree(points)
        queries=rng.uniform([-6800,-7900,-1300],[6800,4300,1800],(500,3))
        queries=np.concatenate((queries,points[::193]))
        max_tested=0;max_stack=0
        for q in queries:
            r,d,n,s=nearest_native(self.tree,self.refs,q);expected,_=index.query(q)
            self.assertAlmostEqual(d,expected**2,delta=.05);max_tested=max(max_tested,n);max_stack=max(max_stack,s)
        self.assertLess(max_stack,100)
        (ROOT/'logs/character-probe-query-validation.json').write_text(json.dumps(dict(queries=len(queries),maximum_tested_references=max_tested,maximum_pending_nodes=max_stack),indent=2))

    def test_probe_coefficients_sun_and_point_links_match_bake(self):
        values=self.proof['values'];n=len(values);decoded=np.array(list(struct.iter_unpack('<16h4B4hI',self.l[0x65])))
        self.assertTrue(np.allclose(decoded[:n,:16]/8192,values[:,:16],atol=1/8192))
        self.assertTrue(np.array_equal(decoded[:n,16:24],values[:,16:24]));self.assertTrue((decoded[:,-1]==0).all())
        self.assertGreater((decoded[:n,15]==8192).sum(),1000);self.assertGreater((decoded[:n,15]==0).sum(),1000)
        active=decoded[:n,16:20]>0;ids=decoded[:n,20:24]
        self.assertTrue(((ids[active]>=2)&(ids[active]<32)).all());self.assertTrue((ids[~active]==-1).all())
        self.assertGreater(active.any(1).sum(),1000)
        sh=decoded[:n,:12].reshape(n,3,4)/8192
        self.assertTrue((sh[:,:,3]>=np.linalg.norm(sh[:,:,:3],axis=2)).all())

    def test_every_tunnel_standing_eye_has_close_probe(self):
        p=self.proof['positions'];index=cKDTree(p)
        routes=json.loads((SOURCE.parent/'catwalks.json').read_text())['routes']
        for route in routes:
            for h in (32,64,144):
                d,_=index.query(np.array(route['points'])+[0,0,h]);self.assertLess(d.max(),33)
        lights=json.loads((ROOT/'northstar/PhaseRunner.Preview/interior-lights.json').read_text())['lights']
        for light in lights:
            d,_=index.query(np.array(light['origin'])+[0,0,-32]);self.assertLess(d,.01)

    def test_baker_distinguishes_enclosed_and_open_samples_and_occludes_local_light(self):
        # A sealed box lights from an interior fixture, blocks sun/sky, and
        # prevents that fixture illuminating a probe outside its wall.
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as folder:
            p=Path(folder);tri=[]
            for axis in range(3):
                for sign in (-1,1):
                    a=[None]*3;others=[k for k in range(3) if k!=axis];corners=[]
                    for u,v in ((-4,-4),(4,-4),(4,4),(-4,4)):
                        q=[0,0,0];q[axis]=sign*4;q[others[0]]=u;q[others[1]]=v;corners.append(q)
                    tri.extend([[corners[0],corners[1],corners[2]],[corners[0],corners[2],corners[3]]])
            np.array(tri,'<f4').tofile(p/'tri.bin');np.array([[0,0,0],[12,0,0]],'<f4').tofile(p/'points.bin')
            (p/'fixtures.bin').write_bytes(struct.pack('<7fI',0,0,2,30,1,1,1,2))
            subprocess.run([str(ROOT/'tools/bake_character_probes.exe'),str(p/'tri.bin'),str(p/'points.bin'),str(p/'fixtures.bin'),str(p/'out.bin')],check=True,capture_output=True)
            v=np.fromfile(p/'out.bin','<f4').reshape(2,24)
            self.assertEqual(v[0,15],0);self.assertEqual(v[1,15],1);self.assertTrue((v[0,12:15]==0).all())
            self.assertEqual(v[0,16],255);self.assertEqual(v[0,20],2);self.assertTrue((v[1,16:20]==0).all())

    def test_release_retains_loading_art_localizations_and_scripts(self):
        base=ROOT/'northstar/PhaseRunner.Preview';self.assertEqual(json.loads((PACKAGE/'mod.json').read_text())['Version'],'0.1.38')
        for source in base.rglob('*'):
            if not source.is_file():continue
            rel=source.relative_to(base)
            if rel.as_posix() in ('mod.json','build-status.json','checksums.json','mod/maps/mp_phase_runner.bsp'):continue
            self.assertEqual(digest(source),digest(PACKAGE/rel),str(rel))
        self.assertEqual(digest(PACKAGE/'mod/maps/mp_phase_runner.bsp'),digest(TARGET))

from pathlib import Path
if __name__=='__main__':unittest.main()
