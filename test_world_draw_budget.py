"""Prevent reuse of the failed all-visible build and verify its native limit."""
import unittest
from pathlib import Path
from audit_world_draw_budget import ROOT,WORLD_INDEX_CAPACITY,audit,enforce_camera_bypass_budget


class WorldDrawBudgetTests(unittest.TestCase):
    def test_capacity_matches_installed_native_instruction(self):
        import pefile
        module=Path('D:/Games/Titanfall2/bin/x64_retail/engine.dll')
        pe=pefile.PE(str(module),fast_load=True)
        opcode=pe.get_data(0xb72af,11)
        self.assertEqual(opcode[:5],b'\x3d'+WORLD_INDEX_CAPACITY.to_bytes(4,'little'))
        self.assertEqual(opcode[5:7],b'\x0f\x87') # JA overflow -> epilogue
        displacement=int.from_bytes(opcode[7:11],'little',signed=True)
        self.assertEqual(0xb72af+11+displacement,0xb74b1)

    def test_native_reference_maps_fit_all_world_meshes(self):
        for relative in ('inputs/titanfall2-homestead/maps/mp_homestead.bsp',
                         'inputs/titanfall2-colony/maps/mp_colony02.bsp'):
            proof=enforce_camera_bypass_budget(ROOT/relative)
            self.assertTrue(proof['all_meshes_fit_simultaneously'])

    def test_failed_visibility_experiment_is_rejected(self):
        path=ROOT/'output/phase-runner/preview-camera-visibility/mp_phase_runner_preview.bsp'
        proof=audit(path)
        self.assertEqual(proof['native_padded_indices'],21064278)
        self.assertLess(proof['maximum_all_visible_mesh_prefix'],proof['meshes'])
        with self.assertRaisesRegex(ValueError,'Withdrawn camera-bypass experiment'):
            enforce_camera_bypass_budget(path)


if __name__=='__main__':unittest.main()
