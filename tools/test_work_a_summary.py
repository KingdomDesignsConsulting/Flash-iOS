import hashlib,json,pathlib,tempfile,unittest
from summarize_work_a_closure import summarize
class Summary(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.manifest=dict(head='source',runtime_repair_commit='repair',binary_sha256='binary',execution={},tree='tree',source_sha256={},model_contract={});(self.root/'release-manifest.json').write_text(json.dumps(self.manifest))
 def tearDown(self):self.temp.cleanup()
 def test_missing_stages_are_not_pass(self):
  d=summarize(self.root);self.assertEqual(d['native_32768']['status'],'NOT_RUN');self.assertEqual(d['literal']['status'],'NOT_RUN');self.assertEqual(d['named_profile']['status'],'NOT_RUN')
 def test_nested_raw_values_not_exported(self):
  p=self.root/'profile';p.mkdir();(p/'result.json').write_text(json.dumps(dict(status='PASS',profile='SECRET',error='SECRET',cases=[dict(messages=[dict(content='SECRET')],token_ids=[123],status='PASS')])));d=summarize(self.root);self.assertEqual(d['named_profile']['status'],'PASS');self.assertNotIn('SECRET',json.dumps(d));self.assertNotIn('token_ids',json.dumps(d))
 def test_claimed_pass_without_native_evidence_rejected(self):
  p=self.root/'repaired-32768';p.mkdir();(p/'result.json').write_text(json.dumps(dict(status='PASS',release_manifest_sha256=hashlib.sha256((self.root/'release-manifest.json').read_bytes()).hexdigest())));self.assertEqual(summarize(self.root)['native_32768']['status'],'EVIDENCE_INVALID')
 def test_explicit_resumed_cohort_does_not_reuse_paused_trial(self):
  for name,status in [('performance-16384','PAUSED_BY_USER'),('resume-16384','COMPLETED_EXPLORATORY')]:
   p=self.root/name;p.mkdir();(p/'result.json').write_text(json.dumps(dict(status=status,rows=[])))
  self.assertEqual(summarize(self.root)['performance']['16384']['status'],'PAUSED_BY_USER')
  d=summarize(self.root,'resume');self.assertEqual(d['performance']['16384']['status'],'COMPLETED_EXPLORATORY');self.assertEqual(d['performance']['32768']['status'],'NOT_RUN')
if __name__=='__main__':unittest.main()
