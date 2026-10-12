from pathlib import Path
p=Path('package_northstar.py');s=p.read_text();needle="    sets=lumps.get(0x57,(0,0,0))[1]//8"
s=s.replace(needle,"    # Engine loader uses a fixed 1024-byte material-sort bitset.\n    # The 0.1.20 development minidump showed an oversized memset overwriting\n    # its saved model pointer; retain shared sorts below this native capacity.\n    if lumps.get(0x52,(0,0,0))[1]//12>8192:\n        raise ValueError('Native material-sort loader capacity exceeded')\n"+needle);p.write_text(s)
p=Path('test_prop_physics.py');s=p.read_text();needle='class SpatialSectionTests(unittest.TestCase):'
s=s.replace(needle,'''class SpatialSectionTests(unittest.TestCase):
 def test_native_material_sort_loader_overflow_is_rejected(self):
  path=ROOT/'output/phase-runner/preview-draw-restored/mp_phase_runner_preview.bsp';d=bytearray(path.read_bytes());at=len(d);d.extend(bytes(8193*12));struct.pack_into('<4I',d,16+0x52*16,at,8193*12,0,0)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'bad.bsp';p.write_bytes(d)
   with self.assertRaisesRegex(ValueError,'material-sort loader capacity'):validate_bsp(p)
''');p.write_text(s)
