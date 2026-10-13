"""Regress material-loader contracts and layer-mask/colour confusion."""
import unittest
from new_arena_ports import folder,CONFIG
from apex_material_constants import ApexMaterials,reflect
from recover_arena_atmosphere import vertex_tint,tint
from verify_arena_atmosphere import require_bindings


class AtmosphereTests(unittest.TestCase):
    def test_terrain_layer_masks_are_not_rgb_tints(self):
        self.assertFalse(vertex_tint('thunderdome_rock_shale_thunderdome_white_sand_01_bm'))
        self.assertFalse(vertex_tint('painted_metal_tank_welded_vert_color_grease_bm'))
        self.assertFalse(vertex_tint('beacon_metal_panel_grey_03_lighter_vc'))
        self.assertFalse(vertex_tint('light_strip_01_vc'))
        self.assertTrue(vertex_tint('light_strip_01_vc',verified=True))

    def test_source_constants_are_reflected_not_guessed(self):
        p=ApexMaterials(folder('party-crasher')/'paks'/(CONFIG['party-crasher']['source']+'.rpak'))
        values,fields=p.constants('light_strip_01_vc')
        self.assertEqual(fields['c_depthBlendScalarAndL0_emissiveTint'],(368,16))
        self.assertEqual(tint(values,'c_depthBlendScalarAndL0_emissiveTint'),[7,7,7])
        with self.assertRaises(ValueError):reflect(b'DXBC'+bytes(28))

    def test_missing_pbr_bindings_rejected_before_game_load(self):
        spec={'name':'fixture','\u0024textures':{'0':'albedo','4':'emission'}}
        with self.assertRaisesRegex(ValueError,'Incomplete'):require_bindings(spec,'Native HDR emission')
        require_bindings(spec,'Native unlit source advertisement atlas')
        spec['\u0024textures'].update({'1':'normal','2':'gloss','3':'spec','11':'ao'})
        require_bindings(spec,'Native HDR emission')


if __name__=='__main__':unittest.main()
