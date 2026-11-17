import importlib.util,os,shutil,tempfile,unittest
from pathlib import Path
import recovery_tree as r
class Trees(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.src=self.root/'source';self.src.mkdir();(self.src/'file').write_text('original');(self.src/'empty').mkdir()
 def tearDown(self):self.tmp.cleanup()
 def snapshot(self):return r.inventory(self.src)
 def test_complete(self):a=self.snapshot();r.compare(a,self.snapshot())
 def test_missing(self):a=self.snapshot();(self.src/'file').unlink();self.assertRaises(ValueError,r.compare,a,self.snapshot())
 def test_unexpected(self):a=self.snapshot();(self.src/'new').touch();self.assertRaises(ValueError,r.compare,a,self.snapshot())
 def test_changed(self):a=self.snapshot();(self.src/'file').write_text('changed');self.assertRaises(ValueError,r.compare,a,self.snapshot())
 def test_permissions(self):a=self.snapshot();(self.src/'file').chmod(0o600);self.assertRaises(ValueError,r.compare,a,self.snapshot())
 def test_safe_link(self):(self.src/'link').symlink_to('file');self.assertEqual(self.snapshot()['link']['target'],'file')
 def test_unsafe_link(self):(self.src/'link').symlink_to('/etc/passwd');self.assertRaises(ValueError,self.snapshot)
 def test_escape_link(self):(self.src/'link').symlink_to('../outside');self.assertRaises(ValueError,self.snapshot)
 def test_large_file(self):
  with (self.src/'large').open('wb') as f:f.seek(65*1024*1024);f.write(b'x')
  self.assertEqual(self.snapshot()['large']['bytes'],65*1024*1024+1)
 def test_owners(self):
  a=self.snapshot();b=self.snapshot();b['file']['uid']+=1;self.assertRaises(ValueError,r.compare,a,b);r.compare(a,b,ownership=False)
if __name__=='__main__':unittest.main()
