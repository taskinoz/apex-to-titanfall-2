"""Protect the stable map while restoring source anchors and small details."""
import json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/lighting-python'))
import numpy as np
from repair_preview_index_padding import read_lumps
from audit_world_draw_budget import audit
from repair_environment_lighting import entities
OUT=ROOT/'output/composite';MAP=OUT/'mp_arena_composite.bsp'
OLD=ROOT/'output/repair-backups/20261007-before-detail-recovery/mp_arena_composite.bsp'
# Preserve the 0.4.0-specific byte comparison against its retained snapshot.
# The 0.5.0 regression suite separately verifies deliberate menu/RTL changes.
DETAIL_MAP=ROOT/'output/repair-backups/20261007-before-screen-repair/mp_arena_composite.bsp'
if not (OUT/'screen-repair/result.json').exists():DETAIL_MAP=MAP

class DetailRecoveryTests(unittest.TestCase):
    def test_all_zipline_source_attachments_use_original_transforms(self):
        source={p['index']:p for p in json.loads((OUT/'source-inventory.json').read_text())['props']}
        rows={p['index']:p for p in json.loads((OUT/'scene.json').read_text())['placements']}
        for index in (1651,1652,1669,1670,4960,4974,4994,4995):
            for key in ('model','origin','angles','scale','skin'):self.assertEqual(rows[index][key],source[index][key])
            self.assertGreater(rows[index]['triangles'],0)
            self.assertGreater(rows[index]['collision_triangles'],0)

    def test_old_geometry_entities_and_collision_streams_are_preserved(self):
        ids=(0,3,0x1e,0x42,0x44,0x45,0x49,0x4f,0x7c,0x7e,0x7f,0x65,0x67,0x68)
        before=read_lumps(OLD,ids);after=read_lumps(DETAIL_MAP,ids)
        for key in ids:self.assertEqual(before[key],after[key][:len(before[key])],key)
        self.assertEqual(entities(OLD),entities(DETAIL_MAP))
        positions=np.frombuffer(after[3],'<f4').reshape(-1,3)
        words=np.frombuffer(after[0x42],'<u4')
        nodes=len(after[0x44])//16
        for h in struct.iter_unpack('<6h4i4f',after[0x45][len(before[0x45]):]):
            self.assertLess(h[8],nodes);self.assertGreaterEqual(h[8],len(before[0x44])//16)
            w=words[h[7]:h[7]+h[4]];ix=w&1023
            faces=positions[h[6]+np.stack((ix,ix+(w>>10&127),ix+(w>>17&127)),1)]
            self.assertTrue(np.isfinite(faces).all());self.assertTrue(np.all(abs(faces)<12000))

    def test_old_lightmap_charts_remain_identical(self):
        before=read_lumps(OLD,(0x62,0x69));after=read_lumps(DETAIL_MAP,(0x62,0x69))
        count=json.loads((ROOT/'output/repair-backups/20261007-before-detail-recovery/scene.json').read_text())['triangles']
        tiles=512*512;mask=np.repeat(np.repeat((np.arange(tiles).reshape(512,512)<count%tiles),4,0),4,1)
        for key,stride in ((0x62,2048*2048*8),(0x69,2048*2048*8+1024*1024*4)):
            self.assertEqual(before[key][:stride*3],after[key][:stride*3])
            for channel in range(2):
                start=stride*3+channel*2048*2048*4
                a=np.frombuffer(before[key][start:start+2048*2048*4],'u1').reshape(2048,2048,4)
                b=np.frombuffer(after[key][start:start+2048*2048*4],'u1').reshape(2048,2048,4)
                self.assertTrue(np.array_equal(a[mask],b[mask]))

    def test_added_materials_are_recovered_with_budget_margin(self):
        result=json.loads((OUT/'detail-recovery/result.json').read_text());a=audit(MAP)
        self.assertEqual(result['added_props'],95)
        self.assertLessEqual(result['added_triangles'],36000)
        self.assertLess(a['native_padded_indices'],3145728*.9)
        self.assertLess(a['static_batch_runs'],512)
        scene=np.load(OUT/'detail-recovery/addition.npz');names=list(scene['names']);scene.close()
        mapping=json.loads((OUT/'materials/mapping.json').read_text())['materials']
        for name in names:
            self.assertTrue(mapping[name]['recovered'],name)
            self.assertIn('0',mapping[name]['textures'])

if __name__=='__main__':unittest.main()
