import hashlib
import json
import tempfile
import tomllib
import urllib.error
import unittest
import zipfile
from unittest.mock import MagicMock
from pathlib import Path
from unittest.mock import patch

import thunderstore_ci as ci
import thunderstore_upload as uploader


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = next(p.copy() for p in ci.catalog() if p['mod'] == 'ArenaOverflow')

    def source(self, extra=None, version=None):
        p = self.root/'source.zip'
        mod = self.package['mod']
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr(mod+'/mod.json', json.dumps({'Name': mod, 'Version': version or self.package['version']}))
            z.writestr(mod+'/README.md', 'Known limitations and manual install notes')
            z.writestr(mod+'/mod/maps/mp_overflow.bsp', b'exact geometry bytes')
            z.writestr(mod+'/paks/overflow_world.rpak', b'exact texture bytes')
            z.writestr(mod+'/paks/rpak.json', b'{}')
            if extra:
                z.writestr(extra, b'not allowed')
        self.package.update(bytes=p.stat().st_size, sha256=ci.digest(p))
        return p

    def test_repackage_preserves_runtime_and_dependency(self):
        p = self.source()
        receipt = ci.build(self.package, p, self.root/'built')
        self.assertEqual(receipt['name'], 'Overflow')
        with zipfile.ZipFile(receipt['path']) as z:
            self.assertEqual(z.read('mods/taskinoz.ArenaOverflow/mod/maps/mp_overflow.bsp'), b'exact geometry bytes')
            manifest = json.loads(z.read('manifest.json'))
            self.assertEqual(manifest['dependencies'], ['taskinoz-ApexMaps_UI-0.2.1'])
            self.assertTrue({'icon.png', 'README.md', 'manifest.json'} <= set(z.namelist()))
            self.assertFalse(any('harness' in n for n in z.namelist()))
        # Fixed archive timestamps make repeats identical on the same toolchain.
        repeated = ci.build(self.package, p, self.root/'other')
        self.assertEqual(receipt['sha256'], repeated['sha256'])
        config = tomllib.loads(Path(receipt['config']).read_text())
        self.assertEqual(config['package']['dependencies'], {'taskinoz-ApexMaps_UI': '0.2.1'})
        self.assertEqual(config['publish']['communities'], ['northstar'])

    def test_rejects_tampered_source(self):
        p = self.source()
        p.write_bytes(p.read_bytes()+b'tamper')
        with self.assertRaisesRegex(ValueError, 'locked release'):
            ci.build(self.package, p, self.root/'built')

    def test_rejects_unexpected_version(self):
        with self.assertRaisesRegex(ValueError, 'identity/version'):
            ci.build(self.package, self.source(version='9.9.9'), self.root/'built')

    def test_rejects_traversal_and_development_files(self):
        for name in ('ArenaOverflow/../secret', 'ArenaOverflow/logs/session.json',
                     'ArenaOverflow\\mod.json', '/ArenaOverflow/mod.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ci.build(self.package, self.source(extra=name), self.root/'built')

    def test_selection_adds_ui_and_deduplicates(self):
        selected = ci.select(ci.catalog(), 'ArenaOverflow')
        self.assertEqual([p['mod'] for p in selected], ['ApexMaps.UI', 'ArenaOverflow'])
        self.assertEqual(len(ci.select(ci.catalog(), 'current')), 8)
        with self.assertRaises(ValueError):
            ci.select(ci.catalog(), 'unreviewed-new-release')

    def test_publish_requires_secret_before_network(self):
        with patch.dict(ci.os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, 'TS_KEY'):
            ci.publish([])

    def test_publish_uses_async_uploader_and_fresh_version_lookup(self):
        receipt = ci.build(self.package, self.source(), self.root/'built')
        missing = urllib.error.HTTPError('https://thunderstore.io', 404, 'not found', {}, None)
        with patch.dict(ci.os.environ, {'TCLI_AUTH_TOKEN': 'unit-test-placeholder'}), \
                patch.object(ci.urllib.request, 'urlopen', side_effect=missing) as get, \
                patch.object(uploader, 'submit') as submit:
            ci.publish([receipt])
        self.assertEqual(submit.call_args.args[:2], (receipt['path'], 'taskinoz'))
        self.assertIn('?ci=', get.call_args.args[0].full_url)
        self.assertEqual(get.call_args.args[0].get_header('Cache-control'), 'no-cache')

    def test_reuse_rejects_other_workflows_and_branches(self):
        for branch, name in [('feature', 'Publish Northstar maps to Thunderstore'), ('main', 'Untrusted workflow')]:
            response = json.dumps(dict(headBranch=branch, event='workflow_dispatch', name=name)).encode()
            with patch.object(ci.subprocess, 'check_output', return_value=response), self.assertRaises(ValueError):
                ci.reuse('123', self.root/'out', 'current')

    def test_reuse_restores_outputs_and_skips_old_source_duplicates(self):
        source = self.source(extra='ArenaOverflow/paks/zz_sorted_last.rpak')
        receipt = ci.build(self.package, source, self.root/'built')
        source_zip = Path(receipt['path']).read_bytes()
        receipt['name'] = 'mods/taskinoz.ArenaOverflow/paks/zz_sorted_last.rpak'
        run = json.dumps(dict(headBranch='main', event='workflow_dispatch', name='Publish Northstar maps to Thunderstore')).encode()
        artifacts = json.dumps({'artifacts': [dict(id=1, name='thunderstore-packages-123', expired=False),
                                             dict(id=2, name='thunderstore-packages-123', expired=False)]}).encode()
        def download(command, **kwargs):
            self.assertIn('artifacts/2/zip', command[-1])
            with zipfile.ZipFile(kwargs['stdout'], 'w') as z:
                z.writestr('receipts.json', json.dumps([receipt]))
                z.writestr('Overflow/taskinoz-Overflow-0.4.2.zip', source_zip)
                z.writestr('downloads/'+self.package['asset'], b'redundant source not extracted')
        with patch.object(ci, 'catalog', return_value=[self.package]), \
                patch.object(ci.subprocess, 'check_output', side_effect=[run, artifacts]), \
                patch.object(ci.subprocess, 'run', side_effect=download):
            restored = ci.reuse('123', self.root/'restored', 'ArenaOverflow')
        self.assertEqual(ci.digest(restored[0]['path']), receipt['sha256'])
        self.assertEqual(restored[0]['name'], 'Overflow')
        self.assertFalse((self.root/'restored/downloads').exists())

    def test_async_protocol_uploads_then_polls_background_validation(self):
        p = self.root/'tiny.zip'
        p.write_bytes(b'test')
        initial = {'user_media': {'uuid': 'upload-test'}, 'upload_urls': [dict(offset=0, length=4, part_number=1)]}
        done = {'status': 'FINISHED', 'result': {'package_version': {'download_url': 'https://thunderstore.io/download/test'}}}
        with patch.object(uploader, 'api', side_effect=[initial, {}, {'id': 'submit-test', 'status': 'PENDING'}, done]) as api, \
                patch.object(uploader, 'upload_part', return_value={'ETag': 'part', 'PartNumber': 1}), \
                patch.object(uploader.time, 'sleep'):
            uploader.submit(p, 'taskinoz', 'unit-test-placeholder')
        calls = api.call_args_list
        self.assertEqual(calls[1].args[0], 'usermedia/upload-test/finish-upload/')
        self.assertEqual(calls[2].args[0], 'submission/submit-async/')
        self.assertEqual(calls[2].args[2]['communities'], ['northstar'])
        self.assertTrue(calls[3].args[0].startswith('submission/poll-async/submit-test/'))

    def test_invalid_part_ranges_abort_before_upload(self):
        p = self.root/'tiny.zip'
        p.write_bytes(b'test')
        initial = {'user_media': {'uuid': 'upload-test'}, 'upload_urls': [dict(offset=1, length=4, part_number=1)]}
        with patch.object(uploader, 'api', side_effect=[initial, {}]) as api, \
                patch.object(uploader, 'upload_part') as part, self.assertRaises(ValueError):
            uploader.submit(p, 'taskinoz', 'unit-test-placeholder')
        part.assert_not_called()
        self.assertEqual(api.call_args.args[0], 'usermedia/upload-test/abort-upload/')

    def test_storage_request_has_checksum_and_no_api_credential(self):
        p = self.root/'tiny.zip'
        p.write_bytes(b'test')
        response = MagicMock()
        response.__enter__.return_value.headers = {'ETag': 'test-etag'}
        with patch.object(uploader.urllib.request, 'urlopen', return_value=response) as put:
            part = uploader.upload_part(p, dict(url='https://storage.example/part', offset=0, length=4, part_number=1))
        request = put.call_args.args[0]
        self.assertIsNone(request.get_header('Authorization'))
        self.assertEqual(request.data, b'test')
        self.assertEqual(part['ETag'], 'test-etag')
        self.assertIsNotNone(request.get_header('Content-md5'))

    def test_api_rejects_external_origin_and_storage_errors_hide_signed_url(self):
        with self.assertRaises(ValueError):
            uploader.api('https://untrusted.example', 'unit-test-placeholder')
        p = self.root/'tiny.zip'
        p.write_bytes(b'test')
        with patch.object(uploader.urllib.request, 'urlopen', side_effect=urllib.error.URLError('secret-signed-url')):
            with self.assertRaises(RuntimeError) as error:
                uploader.upload_part(p, dict(url='https://storage.example/?signature=private', offset=0, length=4, part_number=1))
        self.assertNotIn('signature', str(error.exception))
        self.assertNotIn('secret-signed-url', str(error.exception))


if __name__ == '__main__':
    unittest.main()
