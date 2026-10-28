"""Provenance checks using disposable archives, never installed game assets."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import prepare_anniversary_release as prep


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'candidate'
        self.downloads=self.root/'output/releases/maps-beta-2026-10-25'
        self.downloads.mkdir(parents=True)
        self.patch=patch.multiple(prep,ROOT=self.root,OUT=self.out,BASE=('PhaseRunner',))
        self.patch.start();self.addCleanup(self.patch.stop)
        self.rows=[]
        for name in ('PhaseRunner','ApexMaps.UI'):self.archive(name)
        self.manifest()

    def archive(self,name,extra=None):
        path=self.downloads/(name+'.zip')
        with zipfile.ZipFile(path,'w') as z:
            z.writestr(name+'/mod.json',json.dumps({'Name':name,'Version':'1'}))
            z.writestr(name+'/mod/scripts/script.nut','printl("original")')
            z.writestr(name+'/mod/resource/name_english.txt','Original translation')
            if extra:z.writestr(name+'/'+extra,b'escape')
        row={'name':path.name,'sha256':prep.digest(path),'checks':{'mod':name,'version':'1'}}
        self.rows=[r for r in self.rows if r['checks']['mod']!=name]+[row]

    def manifest(self):
        (self.downloads/'release-manifest.json').write_text(json.dumps({'packages':self.rows}))

    def stage(self):
        with contextlib.redirect_stdout(io.StringIO()):prep.stage()

    def test_modified_download_is_refused_before_extraction(self):
        with (self.downloads/'PhaseRunner.zip').open('ab') as f:f.write(b'changed')
        with self.assertRaisesRegex(ValueError,'Accepted ZIP changed'):self.stage()
        self.assertFalse(self.out.exists())

    def test_mutated_staged_script_is_not_reaccepted(self):
        self.stage()
        (self.out/'baseline/PhaseRunner/mod/scripts/script.nut').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Staged bytes differ'):self.stage()

    def test_archive_cannot_write_outside_its_mod(self):
        self.archive('PhaseRunner','../escaped.txt');self.manifest()
        with self.assertRaisesRegex(ValueError,'Unsafe archive member'):self.stage()
        self.assertFalse((self.out/'baseline/escaped.txt').exists())

    def test_translations_and_scripts_are_in_runtime_provenance(self):
        self.stage();self.stage()
        data=json.loads((self.out/'baseline-manifest.json').read_text())['PhaseRunner']['payloads']
        self.assertEqual(data['mod/scripts/script.nut'],hashlib.sha256(b'printl("original")').hexdigest())
        self.assertIn('mod/resource/name_english.txt',data)


if __name__=='__main__':unittest.main()
