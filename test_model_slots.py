import struct
import tempfile
import unittest
from pathlib import Path
from recover_model_slots import mesh_slots, load_bound_sections
from repair_portal_surfaces import key, nondegenerate

ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'tools/legion/exported_files/models'


class ModelSlotTests(unittest.TestCase):
    def test_portal_compiled_slots_include_every_submesh(self):
        for name, count in [('phase_runner_tunnel',10),('phase_runner_tunnel_02',11)]:
            raw=MODELS/name/(name+'.rmdl')
            slots, skins=mesh_slots(raw.read_bytes())
            self.assertEqual(slots,list(range(count)))
            qc=ROOT/'output/phase-runner/prepared-models/mdl/levels_terrain/mp_rr_phase_runner'/name/(name+'.qc')
            sections,bound,materials=load_bound_sections(qc,raw)
            self.assertEqual(bound,slots)
            self.assertEqual(len(sections),count)
            self.assertEqual(materials[0][7],'ambient_occlusion')
            self.assertEqual(materials[0][8],'slum_grime_decal_01_bt')

    def test_empty_skin_family_label_preserves_compiled_skin_order(self):
        name='icelandic_moss_mod_01';folder=MODELS/name
        sections,slots,skins=load_bound_sections(folder/(name+'.qc'),folder/(name+'.rmdl'))
        self.assertEqual(len(sections),1)
        self.assertEqual(slots,[0])
        self.assertEqual([row[0] for row in skins],['icelandic_moss_01_wld_vxd',
            'desertlands_snow_02_wld_vtx','icelandic_yellow_moss_01_wld_vxd'])

    def test_bad_compiled_backrefs_and_truncated_mesh_table_fail(self):
        name='phase_runner_tunnel';raw=bytearray((MODELS/name/(name+'.rmdl')).read_bytes())
        body=struct.unpack_from('<i',raw,240)[0]
        model=body+struct.unpack_from('<i',raw,body+12)[0]
        mesh=model+struct.unpack_from('<i',raw,model+80)[0]
        struct.pack_into('<i',raw,mesh+4,0)
        with self.assertRaisesRegex(ValueError,'Unsupported mesh layout'):mesh_slots(raw)
        with self.assertRaises(ValueError):mesh_slots(raw[:mesh+16])

    def test_partial_export_and_wrong_section_count_fail(self):
        name='icelandic_moss_mod_01';folder=MODELS/name
        text=(folder/(name+'.qc')).read_text(errors='replace')
        with tempfile.TemporaryDirectory() as temp:
            qc=Path(temp)/(name+'.qc');qc.write_text(text)
            smd=Path(temp)/(name+'_LOD0.smd')
            smd.write_text('version 1\ntriangles\nmaterial\n0 0 0 0 0 0 1 0 0\n')
            with self.assertRaisesRegex(ValueError,'Truncated SMD'):load_bound_sections(qc,folder/(name+'.rmdl'))
            smd.write_text('version 1\ntriangles\nend\ntriangles\nend\n')
            with self.assertRaisesRegex(ValueError,'mesh count mismatch'):load_bound_sections(qc,folder/(name+'.rmdl'))

    def test_exact_triangle_identity_retains_normals_and_uv(self):
        vertices=[struct.pack('<8f',*p,0,0,1,0,0) for p in [(0,0,0),(1,0,0),(0,1,0)]]
        self.assertEqual(key(vertices),key(vertices[::-1]))
        changed=vertices.copy();changed[0]=struct.pack('<8f',0,0,0,0,0,1,1,0)
        self.assertNotEqual(key(vertices),key(changed))
        self.assertTrue(nondegenerate(vertices))
        self.assertFalse(nondegenerate([vertices[0]]*3))


if __name__=='__main__':unittest.main()
