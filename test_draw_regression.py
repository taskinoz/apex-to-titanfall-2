"""Verify that the regression repair changes only the declared draw records."""
import hashlib,json,mmap,struct,unittest
from pathlib import Path
from repair_draw_regression import PORTAL_MATERIALS
from extract_native_material import NativePak
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT/'output/phase-runner'

class DrawRegressionTests(unittest.TestCase):
    def test_repaired_bsp_is_exact_pre_experiment_geometry(self):
        reference=PROJECT/'preview-welded/mp_phase_runner_preview.bsp'
        repaired=PROJECT/'preview-draw-restored/mp_phase_runner_preview.bsp'
        # Reverting the four draw-bound lumps reconstructs the entire compact
        # pre-experiment BSP, including every render and collision byte.
        self.assertEqual(hashlib.sha256(reference.read_bytes()).digest(),hashlib.sha256(repaired.read_bytes()).digest())

    def test_rpak_changes_are_only_the_declared_sixteen_flags(self):
        report=json.loads((PROJECT/'preview-draw-restored/source-build.json').read_text())['draw_regression_repair']['material_repair']
        path=PROJECT/'world-materials/build/phase_runner_world.rpak'
        changes=report['changes'];self.assertEqual(len(changes),16)
        before=hashlib.sha256();after=hashlib.sha256()
        with path.open('rb') as f:
            offset=0
            while chunk:=f.read(8*1024*1024):
                after.update(chunk);original=bytearray(chunk)
                for change in changes:
                    at=change['offset']
                    if offset<=at<offset+len(chunk):
                        self.assertEqual(struct.unpack_from('<H',original,at-offset)[0],change['after'])
                        struct.pack_into('<H',original,at-offset,change['before'])
                before.update(original);offset+=len(chunk)
        self.assertEqual(before.hexdigest(),report['previous_sha256'])
        self.assertEqual(after.hexdigest(),report['restored_sha256'])

    def test_portal_flags_match_native_primary_and_colour_pass(self):
        native=NativePak(ROOT/'inputs/tf2-rpak-work/coliseum.raw.rpak')
        expected={}
        for a in native.assets:
            if a['guid'] in (0x92424EA716974A64,0x1F8E00B988C71BBB):
                spec,_=native.material(a);expected[spec['name'].endswith('_colpass')]=spec['rasterizerFlags']
        custom=NativePak(PROJECT/'world-materials/build/phase_runner_world.rpak');seen=set()
        for a in custom.assets:
            if a['type']!='matl':continue
            spec,_=custom.material(a);name=spec['name'].rsplit('/',1)[-1];colpass=name.endswith('_colpass')
            basename=name[:-8] if colpass else name
            if basename not in PORTAL_MATERIALS:continue
            self.assertEqual(spec['rasterizerFlags'],expected[colpass]);seen.add((basename,colpass))
        self.assertEqual(len(seen),16)

if __name__=='__main__':unittest.main()
