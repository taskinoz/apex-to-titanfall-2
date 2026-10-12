"""Regression checks for generated map planes and real target BSP references."""
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from build_preview_source import brush,cross,subtract
from package_northstar import validate_bsp

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/bsp_tool'))
import bsp_tool


class NorthstarBuildTests(unittest.TestCase):
    def test_prism_planes_contain_convex_interior(self):
        points=[(0.,0.,0.),(128.,0.,0.),(0.,128.,0.)]
        result=brush(points)
        center=(128/3,128/3,-1.)
        for line in result.splitlines()[1:-1]:
            import re
            p=[tuple(map(float,v.split())) for v in re.findall(r'\( ([^)]+) \)',line)]
            n=cross(subtract(p[2],p[0]),subtract(p[1],p[0]))
            self.assertLess(sum(n[i]*(center[i]-p[0][i]) for i in range(3)),0)
        self.assertIsNone(brush([(0.,0.,0.)]*3))

    def test_real_compiled_bsp_geometry_and_material(self):
        path=ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp'
        validate_bsp(path)
        bsp=bsp_tool.load_bsp(str(path))
        self.assertEqual(bsp.loading_errors,{})
        report=json.loads(path.with_name('source-build.json').read_text())
        self.assertEqual(sum(m.num_triangles for m in bsp.MESHES),report['render_triangles'])
        self.assertEqual(list(bsp.TEXTURE_DATA_STRING_DATA),
                         ['world\\dev\\dev_gray_512','tools\\toolsclip','tools\\toolsskybox'])
        self.assertTrue(all(bsp.MATERIAL_SORTS[m.material_sort].texture_data in (0,2) for m in bsp.MESHES))
        self.assertTrue(all(math.isfinite(v) for point in bsp.VERTICES for v in point))
        self.assertEqual(len(bsp.CM_BRUSHES),report['collision_sample_brushes'])

    def test_render_gpu_ranges_and_visibility_cover_every_mesh(self):
        bsp=bsp_tool.load_bsp(str(ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp'))
        for mesh,bound in zip(bsp.MESHES,bsp.MESH_BOUNDS):
            sort=bsp.MATERIAL_SORTS[mesh.material_sort]
            indices=bsp.MESH_INDICES[mesh.first_mesh_index:mesh.first_mesh_index+mesh.num_triangles*3]
            self.assertGreaterEqual(min(indices),mesh.first_vertex)
            self.assertLessEqual(max(indices),mesh.first_vertex+mesh.num_vertices)
            self.assertLessEqual(max(indices),sort.last_vertex)
            self.assertGreater(bound.radius,0.)
            self.assertGreaterEqual(bound.radius,math.sqrt(sum(v*v for v in bound.extents)))
        self.assertEqual(sorted(bsp.OBJ_REFERENCES),list(range(len(bsp.MESHES))))
        self.assertEqual(len(bsp.OBJ_REFERENCE_BOUNDS),len(bsp.OBJ_REFERENCES))
        self.assertEqual(bsp.CELLS[0].num_portals,0)
        self.assertEqual(bsp.CELL_AABB_NODES[0].num_obj_refs,len(bsp.MESHES))

    def test_world_material_uses_native_world_vertex_layout(self):
        bsp=bsp_tool.load_bsp(str(ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp'))
        for mesh in bsp.MESHES[:bsp.LEVEL_INFO.first_sky_mesh]:
            self.assertEqual(int(mesh.flags)&0x600,0x200)
            self.assertEqual(mesh.vertex_type,2)
            sort=bsp.MATERIAL_SORTS[mesh.material_sort]
            self.assertEqual(sort.lightmap_header,0)
            self.assertLess(sort.vertex_offset+sort.last_vertex,len(bsp.VERTEX_LIT_BUMP))
        vertices=bsp.VERTEX_LIT_BUMP
        for i in range(0,len(vertices),997):
            vertex=vertices[i]
            self.assertLess(vertex.position_index,len(bsp.VERTICES))
            self.assertLess(vertex.normal_index,len(bsp.VERTEX_NORMALS))
            self.assertLess(vertex.tangent.s&0x7fffffff,len(bsp.VERTEX_NORMALS))

    def test_render_winding_matches_native_clockwise_faces(self):
        bsp=bsp_tool.load_bsp(str(ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp'))
        for mesh in bsp.MESHES:
            sort=bsp.MATERIAL_SORTS[mesh.material_sort]
            vertices=bsp.VERTEX_LIT_BUMP if mesh.vertex_type==2 else bsp.VERTEX_UNLIT
            for t in (0,mesh.num_triangles-1):
                ids=bsp.MESH_INDICES[mesh.first_mesh_index+t*3:mesh.first_mesh_index+t*3+3]
                corners=[vertices[i+sort.vertex_offset] for i in ids]
                points=[bsp.VERTICES[v.position_index] for v in corners]
                a=subtract(points[1],points[0]);b=subtract(points[2],points[0])
                n=cross(a,b)
                normal=bsp.VERTEX_NORMALS[corners[0].normal_index]
                self.assertLess(sum(n[k]*normal[k] for k in range(3)),0.)

    def test_lightmap_sample_is_lit_and_sky_metadata_matches_native(self):
        bsp=bsp_tool.load_bsp(str(ROOT/'output/phase-runner/preview-render/mp_phase_runner_preview.bsp'))
        vertex=bsp.VERTEX_LIT_BUMP[0]
        header=bsp.LIGHTMAP_HEADERS[0]
        uv=vertex.lightmap.uv
        pixel=(int(uv[1]*header.height)*header.width+int(uv[0]*header.width))*4
        self.assertGreater(sum(bsp.LIGHTMAP_DATA_SKY[pixel:pixel+3]),0)
        for mesh in bsp.MESHES[bsp.LEVEL_INFO.first_sky_mesh:]:
            self.assertEqual(mesh.vertex_type,0)
            self.assertEqual(mesh.cubemap,-1)
            self.assertEqual(mesh.styles,(-1,-1,-1,-1))
            self.assertEqual(mesh.luxel_origin,(-1,-1))

    def test_corrupted_collision_grid_is_rejected(self):
        data=bytearray((ROOT/'output/phase-runner/preview-source/mp_phase_runner_preview.bsp').read_bytes())
        offset=struct.unpack_from('<I',data,16+0x56*16)[0]
        struct.pack_into('<HH',data,offset,65535,65535)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.bsp'
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'outside geosets'):
                validate_bsp(path)


if __name__=='__main__':
    unittest.main()
