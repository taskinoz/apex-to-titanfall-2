"""Verify bounded restoration of a real two-delta chain without network access."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import archive_release_history as archive
import manage_release_archives as releases
import restore_release_archive as restore


class RestoreTests(unittest.TestCase):
    def test_filename_cannot_escape_destination(self):
        with self.assertRaises(ValueError):restore.basename('../escape.zip')

    def test_cycles_are_rejected(self):
        rows=[{'name':a,'asset_name':a+'.zst','encoding':'zstd-patch','base_name':b,'base_tag':restore.ARCHIVE}
              for a,b in [('a.zip','b.zip'),('b.zip','a.zip')]]
        with self.assertRaises(ValueError):restore.chain({'complete':True,'repository':restore.REPO,'objects':rows},'a.zip')

    def test_real_two_delta_chain_restores_exact_bytes_and_preserves_current(self):
        with tempfile.TemporaryDirectory(prefix='release-restore-test-',dir=releases.ROOT) as temporary:
            root=Path(temporary).resolve()
            self.assertEqual(root.parent,releases.ROOT)
            store=root/'store'; store.mkdir()
            current=store/'Current-1.0.0-Northstar.zip'
            middle=store/'Old2.zip'; oldest=store/'Old1.zip'
            current.write_bytes(bytes(range(256))*800)
            middle.write_bytes(current.read_bytes()[:100000]+b'changed middle'+current.read_bytes()[100014:])
            oldest.write_bytes(middle.read_bytes()[:100]+b'changed oldest'+middle.read_bytes()[114:])
            rows=[]
            for path,base,tag in [(middle,current,restore.BETA),(oldest,middle,restore.ARCHIVE)]:
                delta=store/(path.name+'.zst')
                p=subprocess.run([str(archive.ZSTD),'-1','-q','--patch-from='+archive.cygwin(base),archive.cygwin(path),
                                  '-o',archive.cygwin(delta)],capture_output=True)
                self.assertEqual(p.returncode,0,p.stderr.decode())
                rows.append({'name':path.name,'asset_name':delta.name,'encoding':'zstd-patch',
                             'asset_bytes':delta.stat().st_size,'asset_sha256':restore.digest(delta),
                             'original_bytes':path.stat().st_size,'original_sha256':restore.digest(path),
                             'base_name':base.name,'base_sha256':restore.digest(base),
                             'base_bytes':base.stat().st_size,'base_tag':tag})
            (store/'archival-objects.json').write_text(json.dumps({'complete':True,'repository':restore.REPO,'objects':rows}))
            def download(tag,name,destination):
                restore.basename(name)
                target=destination/name
                shutil.copyfile(store/name,target)
                return target
            destination=root/'restored'
            with patch.object(restore,'download',side_effect=download),contextlib.redirect_stdout(io.StringIO()):
                restore.restore(oldest.name,destination,archive.ZSTD,store)
            self.assertEqual((destination/oldest.name).read_bytes(),oldest.read_bytes())
            self.assertEqual(current.read_bytes(),bytes(range(256))*800)
            self.assertEqual([p.name for p in destination.iterdir()],[oldest.name])


if __name__=='__main__':unittest.main()
