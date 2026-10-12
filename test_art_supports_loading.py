"""Preserve the art release while making the road shader self-contained."""
import json,struct,unittest
from pathlib import Path
from repair_art_supports_loading import ROOT,PROJECT,PACKAGE
from extract_native_material import NativePak
from extract_world_glass_shader import shader
from finalize_lighting_release import digest

class LoadingRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=NativePak(ROOT/'northstar/PhaseRunner.ArtSupportsRelease/paks/phase_runner_art_supports.rpak')
        cls.new=NativePak(PACKAGE/'paks/phase_runner_art_supports.rpak')
        cls.proof=json.loads((PROJECT/'repair.json').read_text())
    def test_geometry_physics_lighting_and_existing_packages_identical(self):
        for rel in ('mod/maps/mp_phase_runner.bsp','mod/maps/mp_phase_runner.stbsp','mod/scripts/vscripts/_phase_runner_preview.nut',*(f'paks/{name}.rpak' for name in ('phase_runner_world','phase_runner_detail','phase_runner_presentation','phase_runner_glass_console'))):
            self.assertEqual(digest(PACKAGE/rel),digest(ROOT/'northstar/PhaseRunner.ArtSupportsRelease'/rel),rel)
    def test_only_road_material_shader_binding_changed(self):
        old={a['guid']:a for a in self.old.assets};new={a['guid']:a for a in self.new.assets}
        self.assertEqual(len(new)-len(old),3);changed=0
        for guid,a in old.items():
            self.assertIn(guid,new)
            if a['type']=='matl':
                spec,buf=self.old.material(a);fixed,other=self.new.material(new[guid]);self.assertEqual(buf,other)
                if spec['name'].endswith('/decals_asphalt_road_dirty_01_alpha'):
                    self.assertEqual(int(fixed['shaderSet'],16),int(self.proof['new_embedded_shader'],16));changed+=1
                    spec.pop('shaderSet');fixed.pop('shaderSet')
                self.assertEqual(spec,fixed)
        self.assertEqual(changed,1)
    def test_shader_dependencies_local_and_native_bytecode_unchanged(self):
        assets={a['guid']:a for a in self.new.assets};shds=assets[int(self.proof['new_embedded_shader'],16)]
        h=self.new.address(shds['header']);vs,ps=struct.unpack_from('<2Q',self.new.data,h+72)
        self.assertEqual(vs,int(self.proof['new_vertex_guid'],16));self.assertEqual(ps,int(self.proof['new_pixel_guid'],16))
        native=NativePak(ROOT/'inputs/tf2-rpak-work/homestead.raw.rpak')
        for actual,original in ((vs,int(self.proof['vertex_guid'],16)),(ps,int(self.proof['pixel_guid'],16))):
            a=next(a for a in native.assets if a['guid']==original)
            self.assertEqual(shader(self.new,assets[actual]),shader(native,a))
    def test_new_shader_guids_do_not_duplicate_mounted_assets(self):
        added={a['guid'] for a in self.new.assets}-{a['guid'] for a in self.old.assets}
        for p in (ROOT/'northstar/PhaseRunner.Preview/paks').glob('*.rpak'):
            self.assertFalse(added&{a['guid'] for a in NativePak(p).assets},p.name)
        for name in ('common','coliseum'):
            self.assertFalse(added&{a['guid'] for a in NativePak(ROOT/f'inputs/tf2-rpak-work/{name}.raw.rpak').assets})
if __name__=='__main__':unittest.main()
