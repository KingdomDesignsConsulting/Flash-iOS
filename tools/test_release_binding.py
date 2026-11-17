import hashlib,json,pathlib,unittest
from test_work_a_gate import Gate
from work_a_manifest import verify_bound_build
class Binding(Gate):
 def prepare(self):
  self.check();b=self.root/'binary';b.write_bytes(b'fixture')
  gate=json.loads((self.root/'result.json').read_text());gate['binary_sha256']=hashlib.sha256(b.read_bytes()).hexdigest()
  (self.root/'result.json').write_text(json.dumps(gate))
  manifest={'source_sha256':{'metal_infer/flash_serve_admission.h':'0'*64},'binary_sha256':gate['binary_sha256'],'model_artifacts':{}}
  path=self.root/'release-manifest.json';path.write_text(json.dumps(manifest));return path,b
 def test_source_rejects(self):
  p,b=self.prepare()
  with self.assertRaises(ValueError):verify_bound_build(p,b,self.root/'result.json')
 def test_binary_rejects(self):
  p,b=self.prepare();m=json.loads(p.read_text());m['source_sha256']={};m['binary_sha256']='foreign';p.write_text(json.dumps(m));(self.root/'build-variants.json').write_text(json.dumps({'release_manifest_sha256':'foreign','variants':{}}))
  with self.assertRaises(ValueError):verify_bound_build(p,b,self.root/'result.json')
 def test_manifest_rejects(self):
  self.gate['release_manifest_sha256']='foreign'
  with self.assertRaises(ValueError):self.check()
 def test_nonfinite_rejects(self):
  self.native['rows'][0]['hidden']['max_abs']=float('nan')
  with self.assertRaises(ValueError):self.check()
 def test_mismatched_fingerprint_rejects(self):
  self.native['rows'][0]['candidate_digest']='foreign'
  with self.assertRaises(ValueError):self.check()
if __name__=='__main__':unittest.main()
