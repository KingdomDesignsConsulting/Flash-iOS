import json,pathlib,tempfile,unittest
from work_a_manifest import verify_native_gate
class Gate(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);(self.root/'native').mkdir()
  self.gate=dict(status='PASS',release_manifest_sha256='manifest',binary_sha256='binary');self.meta=dict(status='PASS',binary_sha256='binary')
  row=dict(state_max_abs=0,hidden=dict(max_abs=1e-6),logits=dict(max_abs=1e-6),candidate_digest='state',reference_digest='state',**{'pass':True,'finite':True,'greedy_equal':True,'kv_lengths_and_mirrors':True})
  self.native=dict(status='NUMERICAL_PASS',completed_position=32768,rows=[dict(row,position=i) for i in range(128,32769,128)])
  self.routes=''.join(f'[release-n128-attention] seq={n} layer={l} cap=32768 backend=GPU\n' for n in (8192,8193,16384,16385,24576,32768) for l in range(3,40,4))
 def tearDown(self):self.temp.cleanup()
 def check(self):
  for p,data in [('result.json',self.gate),('native/result.json',self.meta),('native/nrow-oracle.json',self.native)]: (self.root/p).write_text(json.dumps(data))
  (self.root/'native/engine.log').write_text(self.routes);return verify_native_gate(self.root/'result.json','manifest')
 def test_complete(self):self.assertEqual(self.check()['endpoints'],256)
 def test_large_state(self):
  self.native['rows'][0]['state_max_abs']=1e-3
  with self.assertRaises(AssertionError):self.check()
 def test_duplicate_position(self):
  self.native['rows'][-1]['position']=128
  with self.assertRaises(AssertionError):self.check()
 def test_missing_actual_candidate_route(self):
  self.routes=self.routes.replace('seq=32768 layer=39','seq=32767 layer=39')
  with self.assertRaises(AssertionError):self.check()
 def test_missing_fingerprint(self):
  self.native['rows'][0]['candidate_digest']='';self.native['rows'][0]['reference_digest']=''
  with self.assertRaises(AssertionError):self.check()
if __name__=='__main__':unittest.main()
