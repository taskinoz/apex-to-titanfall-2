"""Exercise retirement safeguards using disposable files and a fake GitHub API."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import manage_release_archives as releases


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='release-cleanup-test-',dir=releases.ROOT)
        if Path(self.tmp.name).resolve().parent != releases.ROOT:
            raise ValueError('Test directory escaped workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = self.root/'report'
        self.report.mkdir()
        self.current = self.root/'Current-1.0.0-Northstar.zip'
        self.old = self.root/'Old-0.1.0-Northstar.zip'
        self.current.write_bytes(b'current')
        self.old.write_bytes(b'old')
        self.rows = [self.row(self.current,True), self.row(self.old,False)]
        self.plan = self.root/'plan.json'
        self.plan.write_text(json.dumps({'inventory_complete':True,'files':self.rows}))
        self.archive = {'draft':True,'assets':[self.asset(self.rows[1])]}
        self.beta = {'draft':False,'prerelease':True,'html_url':'https://example.invalid/beta',
                     'assets':[self.asset(self.rows[0])]}
        for target, value in [('PLAN',self.plan),('REPORT',self.report),('STORE',self.root)]:
            p = patch.object(releases,target,value)
            p.start()
            self.addCleanup(p.stop)
        for target, value in [('roots',{'output':self.root,'backups':self.root/'backups'}),
                              ('current_names',{self.current.name:('Current','1.0.0')})]:
            p = patch.object(releases,target,return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(releases,'release',side_effect=lambda tag:self.archive if tag==releases.ARCHIVE else self.beta)
        p.start()
        self.addCleanup(p.stop)

    def row(self,path,current):
        return {'name':path.name,'scope':'output','bytes':path.stat().st_size,
                'sha256':releases.sha(path),'current':current}

    def asset(self,row):
        return {'name':row['name'],'id':42,'state':'uploaded','size':row['bytes'],
                'digest':'sha256:'+row['sha256']}

    def run_retire(self,apply=True):
        with contextlib.redirect_stdout(io.StringIO()):
            releases.retire(apply)

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            releases.source({'scope':'output','name':'../escape.zip'})

    def test_remote_hash_mismatch_preserves_local(self):
        self.archive['assets'][0]['digest']='sha256:incorrect'
        with self.assertRaises(ValueError):self.run_retire()
        self.assertTrue(self.old.exists())

    def test_unuploaded_asset_preserves_local(self):
        self.archive['assets'][0]['state']='starter'
        with self.assertRaises(ValueError):self.run_retire()
        self.assertTrue(self.old.exists())

    def test_changed_local_file_is_preserved(self):
        self.old.write_bytes(b'modified')
        with self.assertRaises(ValueError):self.run_retire()
        self.assertEqual(self.old.read_bytes(),b'modified')

    def test_dry_run_removes_nothing(self):
        self.run_retire(False)
        self.assertTrue(self.old.exists())
        self.assertTrue(self.current.exists())

    def test_verified_old_file_retired_current_preserved_and_resume_works(self):
        self.run_retire()
        self.assertFalse(self.old.exists())
        self.assertEqual(self.current.read_bytes(),b'current')
        receipt=json.loads((self.report/'retired.json').read_text())
        self.assertEqual(receipt[0]['sha256'],self.rows[1]['sha256'])
        self.run_retire()  # An interruption after a completed receipt is resumable.

    def test_incomplete_delta_archive_preserves_local(self):
        (self.report/'archival-objects.json').write_text(json.dumps({'complete':False,'objects':[]}))
        with self.assertRaises(ValueError):self.run_retire()
        self.assertTrue(self.old.exists())

    def test_verified_delta_can_retire_original_zip(self):
        original=self.rows[1]
        proof={'scope':'output','name':self.old.name,'original_bytes':original['bytes'],
               'original_sha256':original['sha256'],'restored_sha256':original['sha256'],
               'remote_verified':True,'asset_name':'old.zip.zst','asset_bytes':1,'asset_sha256':'a'*64}
        path=self.report/'archival-objects.json'
        path.write_text(json.dumps({'complete':True,'objects':[proof]}))
        self.archive['assets']=[{'name':'old.zip.zst','id':43,'state':'uploaded','size':1,'digest':'sha256:'+'a'*64},
            {'name':path.name,'id':44,'state':'uploaded','size':path.stat().st_size,'digest':'sha256:'+releases.sha(path)}]
        self.run_retire()
        self.assertFalse(self.old.exists())
        self.assertTrue(self.current.exists())

    def test_bad_checksum_sidecar_is_preserved_without_losing_receipt(self):
        sidecar=self.old.with_suffix('.zip.sha256')
        sidecar.write_bytes(b'\xff\x00')
        self.run_retire()
        self.assertTrue(sidecar.exists())
        self.assertFalse(self.old.exists())
        self.assertEqual(len(json.loads((self.report/'retired.json').read_text())),1)

    def test_interrupted_delete_recovers_durable_journal(self):
        row=self.rows[1]
        pending={k:row[k] for k in ('scope','name','bytes','sha256')}
        pending.update(asset_id=42,asset_name=row['name'],retired_at='test-interruption')
        (self.report/'retirement-pending.json').write_text(json.dumps(pending))
        self.old.unlink()
        self.run_retire()
        receipt=json.loads((self.report/'retired.json').read_text())
        self.assertTrue(receipt[0]['recovered_interrupted_receipt'])
        self.assertTrue(self.current.exists())


if __name__=='__main__':unittest.main()
