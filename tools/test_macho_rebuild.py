import pathlib,struct,tempfile,unittest
from compare_macho_rebuild import describe
class Rebuild(unittest.TestCase):
 def image(self,root,name,uuid=b'A'*16,signature=b'S'*8,payload=b'code'):
  header=struct.pack('<8I',0xfeedfacf,0,0,0,2,40,0,0);data=header+struct.pack('<II',0x1b,24)+uuid+struct.pack('<4I',0x1d,16,76,8)+payload+signature;p=root/name;p.write_bytes(data);return p
 def test_metadata_only(self):
  with tempfile.TemporaryDirectory() as folder:
   r=pathlib.Path(folder);a=describe(self.image(r,'a'));b=describe(self.image(r,'b',uuid=b'B'*16,signature=b'T'*8));self.assertNotEqual(a['sha256'],b['sha256']);self.assertEqual(a['normalized_sha256'],b['normalized_sha256'])
 def test_real_payload_not_hidden(self):
  with tempfile.TemporaryDirectory() as folder:
   r=pathlib.Path(folder);a=describe(self.image(r,'a'));b=describe(self.image(r,'b',payload=b'Code'));self.assertNotEqual(a['normalized_sha256'],b['normalized_sha256'])
 def test_bad_signature_extent(self):
  with tempfile.TemporaryDirectory() as folder:
   r=pathlib.Path(folder);p=self.image(r,'a');p.write_bytes(p.read_bytes()[:-1])
   with self.assertRaises(AssertionError):describe(p)
if __name__=='__main__':unittest.main()
