#!/usr/bin/env python3
"""Release evidence cannot silently turn missing/failed native data into PASS."""
import json,pathlib,tempfile,unittest
from summarize_release_qualification import oracle
class SummaryTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.temp.name)
  self.meta=dict(status='PASS',input_tokens=128,completed_position=128)
  self.row={'pass':True,'finite':True,'greedy_equal':True,'kv_lengths_and_mirrors':True,'state_max_abs':0,'hidden':{'max_abs':1e-6},'logits':{'max_abs':2e-6},'reference_digest':'reference','candidate_digest':'reference'}
  self.native=dict(status='NUMERICAL_PASS',completed_position=128,rows=[self.row])
 def tearDown(self):self.temp.cleanup()
 def run_oracle(self):
  (self.p/'result.json').write_text(json.dumps(self.meta));(self.p/'nrow-oracle.json').write_text(json.dumps(self.native));return oracle(self.p)
 def test_valid_observation(self):self.assertTrue(self.run_oracle()['exact_recorded_persistent_fingerprints'])
 def test_empty_success_rejected(self):
  self.native['rows']=[]
  with self.assertRaises(AssertionError):self.run_oracle()
 def test_failed_capture_without_rows_preserved(self):
  self.meta['status']='EXECUTION_ERROR';self.native['rows']=[];self.assertEqual(self.run_oracle()['status'],'EXECUTION_ERROR')
 def test_false_success_with_large_error_rejected(self):
  self.row['state_max_abs']=.001
  with self.assertRaises(AssertionError):self.run_oracle()
 def test_digest_mismatch_rejected(self):
  self.row['candidate_digest']='different'
  with self.assertRaises(AssertionError):self.run_oracle()
 def test_nonfinite_rejected(self):
  self.row['hidden']['max_abs']=float('nan')
  with self.assertRaises(AssertionError):self.run_oracle()
 def test_native_failure_cannot_be_success(self):
  self.native['status']='FAIL'
  with self.assertRaises(AssertionError):self.run_oracle()
if __name__=='__main__':unittest.main()
