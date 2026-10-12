"""Regression checks for hull edge contacts, mesh ranges and removed barriers."""
import itertools,json,struct,unittest
from pathlib import Path
import numpy as np
from read_prop_physics import convex_planes
from repair_preview_hull_edges import vertices_and_bevels
from repair_preview_index_padding import read_lumps,validate_index_padding

ROOT=Path(__file__).resolve().parent;P=ROOT/'output/phase-runner'

class HullEdgeGeometryTests(unittest.TestCase):
    def fixture(self):
        points=[(0,0,0),(120,0,30),(0,120,30),(30,30,120)]
        faces=[[points[i] for i in f] for f in ((0,1,2),(0,3,1),(1,3,2),(2,3,0))]
        v,q=convex_planes(faces);lo=np.min(v,axis=0);hi=np.max(v,axis=0)
        vertices,extra=vertices_and_bevels(lo,hi,q)
        return np.array(v),np.array(q),np.array(extra),lo,hi
    def test_slope_corner_false_contacts_are_removed(self):
        v,faces,bevels,lo,hi=self.fixture();self.assertGreater(len(bevels),0)
        mn=np.array([-16,-16,0]);mx=np.array([16,16,72])
        rng=np.random.default_rng(123);p=rng.uniform(lo-mx,hi-mn,(10000,3))
        inside=lambda q:np.all(p@q[:,:3].T<=q[:,3]-np.minimum(q[:,:3]*mn,q[:,:3]*mx).sum(axis=1),axis=1)
        corrected=inside(faces)&inside(bevels);wrong=inside(faces)&~corrected
        self.assertGreater(int(wrong.sum()),0)
        # An independent separating-axis oracle: tetra face normals, box face
        # normals and cross products of every tetra edge with each box axis.
        axes=[*faces[:,:3],*np.eye(3)]
        for a,b in itertools.combinations(v,2):
            for axis in np.eye(3):
                n=np.cross(b-a,axis);length=np.linalg.norm(n)
                if length>1e-8:axes.append(n/length)
        axes=np.array(axes);projection=p@axes.T
        bounds=v@axes.T
        intersects=np.all((projection+np.minimum(axes*mn,axes*mx).sum(axis=1)>=bounds.min(axis=0)-1e-6)&
                          (projection+np.maximum(axes*mn,axes*mx).sum(axis=1)<=bounds.max(axis=0)+1e-6),axis=1)
        # Outward float safety can admit a very thin near-contact fringe.
        self.assertTrue(np.all(corrected[intersects]));self.assertGreater(int((wrong&~intersects).sum()),100)
    def test_bevels_do_not_translate_or_shrink_point_collision(self):
        v,faces,bevels,_,_=self.fixture()
        self.assertTrue(np.all(v@bevels[:,:3].T<=bevels[:,3]+1e-5))
        w=np.random.default_rng(321).dirichlet(np.ones(4),1000);inside=w@v
        self.assertTrue(np.all(inside@bevels[:,:3].T<=bevels[:,3]+1e-5))

class SurfaceBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ids=(1,2,3,0x49,0x4f,0x50,0x51,0x52,0x53,0x5c,0x5d,0x5e,0x5f,0x62,0x69)
        cls.old=read_lumps(P/'preview-index-repaired/mp_phase_runner_preview.bsp',ids)
        cls.new=read_lumps(P/'preview-aligned/mp_phase_runner_preview.bsp',ids)
        cls.status=json.loads((P/'preview-aligned/source-build.json').read_text())
    def test_point_brush_volume_and_side_records_are_retained(self):
        old,new=self.old,self.new
        a=list(struct.iter_unpack('<3f2BH3fI',old[0x5c]));b=list(struct.iter_unpack('<3f2BH3fI',new[0x5c]))
        self.assertEqual(len(a),len(b));added=0
        for at,(x,y) in enumerate(zip(a,b)):
            self.assertEqual(old[0x5c][at*32:at*32+13],new[0x5c][at*32:at*32+13]);self.assertEqual(x[5:9],y[5:9]);self.assertGreaterEqual(y[4],x[4])
            self.assertEqual(old[1][16+x[9]*16:16+(x[9]+x[4])*16],new[1][16+y[9]*16:16+(y[9]+x[4])*16])
            os,ns=x[5]*6+x[9],y[5]*6+y[9];count=6+x[4]
            self.assertEqual(old[0x5e][os*2:(os+count)*2],new[0x5e][ns*2:(ns+count)*2])
            self.assertEqual(old[0x5f][os*32:(os+count)*32],new[0x5f][ns*32:(ns+count)*32])
            flags=struct.unpack_from('<'+'H'*(y[4]-x[4]),new[0x5e],(ns+count)*2)
            self.assertTrue(all(f&0x4000 for f in flags));added+=len(flags)
        self.assertEqual(added,self.status['surface_alignment_repair']['collision']['edge_planes_added'])
    def test_triangle_padding_and_local_spans_are_exact(self):
        validate_index_padding(self.new[0x50],self.new[0x4f],self.new[0x52])
        for first,count,minimum,span,*_ in struct.iter_unpack('<I3H18s',self.new[0x50]):
            ids=struct.unpack_from('<'+'H'*(count*3),self.new[0x4f],first*2)
            self.assertEqual((minimum,span),(min(ids),max(ids)-min(ids)))
    def test_only_start_barrier_triangles_are_removed(self):
        removed={r['mesh'] for r in self.status['surface_alignment_repair']['draw']['removed_arena_barriers']}
        cursor=0;total=0
        for i in range(len(self.old[0x50])//28):
            first,count=struct.unpack_from('<IH',self.old[0x50],i*28)
            if i in removed:total+=count;continue
            nf,nc=struct.unpack_from('<IH',self.new[0x50],cursor*28);self.assertEqual(count,nc)
            self.assertEqual(self.old[0x4f][first*2:(first+count*3)*2],self.new[0x4f][nf*2:(nf+nc*3)*2]);cursor+=1
        self.assertEqual(total,108)
        for i in (2,3,0x49,0x52,0x53):self.assertEqual(self.old[i],self.new[i])
    def test_lightmap_pages_contain_no_borrowed_spatial_patterns(self):
        sky,rtl=self.new[0x62],self.new[0x69];sa=ra=0
        for _,w,h in struct.iter_unpack('<I2H',self.new[0x53]):
            n=w*h*4
            for j in range(2):
                s=sky[sa+j*n:sa+(j+1)*n];r=rtl[ra+j*n:ra+(j+1)*n]
                self.assertEqual(s,s[:4]*(w*h));self.assertEqual(r,r[:4]*(w*h))
            sa+=2*n;ra+=2*n+w*h
        self.assertEqual(len(sky),len(self.old[0x62]));self.assertEqual(len(rtl),len(self.old[0x69]))
    def test_native_homestead_bevel_flags_and_counts_match_layout(self):
        l=read_lumps(ROOT/'inputs/titanfall2-homestead/maps/mp_homestead.bsp',(0x5c,0x5e))
        count=0
        for r in struct.iter_unpack('<3f2BH3fI',l[0x5c]):
            at=r[5]*6+r[9]+6;flags=struct.unpack_from('<'+'H'*r[4],l[0x5e],at*2)
            self.assertEqual(r[3],sum(not f&0x4000 for f in flags))
            self.assertTrue(all(not f&0x4000 for f in flags[:r[3]]));self.assertTrue(all(f&0x4000 for f in flags[r[3]:]));count+=int(r[4]>r[3])
        self.assertGreater(count,1000)

if __name__=='__main__':unittest.main()
