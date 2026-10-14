import json
import tempfile
import unittest
from pathlib import Path
from map_pack_lifetime import scope, audit, MAPS, ROOT


class PackLifetimeTests(unittest.TestCase):
    def test_five_installed_maps_share_exactly_one_ui_atlas(self):
        from map_pack_lifetime import audit_shared
        self.assertEqual(audit_shared()['custom_ui_atlases'], 1)
        for package, map_name in MAPS.items():
            report = audit(ROOT/'northstar'/package/'paks', map_name)
            self.assertEqual(report['startup_map_atlases'], 0)
            self.assertFalse(any(n.endswith('_minimap.rpak') for n in report['packs']))

    def test_dependency_lifetime_cannot_silently_regress(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ('test_world.rpak', 'test_presentation.rpak'):
                (p / name).touch()
            original = dict(Aliases={'mp_test.rpak': 'mp_coliseum.rpak',
                                    'mp_test_loadscreen.rpak': 'test_presentation.rpak'},
                            Postload={'test_presentation.rpak': 'common.rpak'},
                            Preload={'test_world.rpak': True})
            (p / 'rpak.json').write_text(json.dumps(original))
            from unittest.mock import patch
            with patch('extract_native_material.NativePak') as pak:
                pak.return_value.assets = [dict(type='matl'),dict(type='txtr')]
                with self.assertRaises(ValueError):
                    audit(p, 'mp_test')
                scope(p, 'mp_test')
                fixed = json.loads((p / 'rpak.json').read_text())
                self.assertEqual(fixed['Aliases'], original['Aliases'])
                self.assertEqual(fixed['Postload'], {'test_world.rpak':'mp_coliseum.rpak','test_presentation.rpak':'common.rpak'})
                before = (p / 'rpak.json').read_bytes()
                scope(p, 'mp_test')
                self.assertEqual(before, (p / 'rpak.json').read_bytes())
                pak.return_value.assets = [dict(type='uimg')]
                with self.assertRaises(ValueError):
                    audit(p, 'mp_test')


if __name__ == '__main__':
    unittest.main()
