import copy,unittest
from summarize_fe027_full_attention import summarize,POSITIONS,VALIDATIONS
class Summary(unittest.TestCase):
 def fixture(self):
  metric=dict(exact=True,nonfinite=0,max_abs=0,rms=0,different=0,bit_different=0,first_different=-1)
  stages=['layer_input','input_norm','qproj','kproj','vproj','q_rope','k_rope','attention_gated','oprojection','residual']
  t={'rows':[dict(metric,layer=3,position=p,row=p,stage=s,dimensions=[4],floats=4,reference_observed=True,candidate_observed=True,reference_path='actual',candidate_path='actual') for p in POSITIONS for s in stages]}
  r=dict(heads=16,head_dim=256,rotary_dim=64,rows=[dict(position=p,**{k:copy.deepcopy(metric) for k in VALIDATIONS+['cpu_q_normalization_replay_vs_live','cpu_k_normalization_replay_vs_live']}) for p in POSITIONS]);return t,r,{'active_state_unchanged':True}
 def test_complete(self):self.assertTrue(summarize(*self.fixture())['causal_validation_pass'])
 def test_missing_replay_row(self):
  t,r,s=self.fixture();r['rows'].pop()
  with self.assertRaises(ValueError):summarize(t,r,s)
 def test_missing_validation(self):
  t,r,s=self.fixture();del r['rows'][0][VALIDATIONS[0]];self.assertFalse(summarize(t,r,s)['causal_validation_pass'])
 def test_failed_validation(self):
  t,r,s=self.fixture();r['rows'][0][VALIDATIONS[0]]['exact']=False;self.assertFalse(summarize(t,r,s)['causal_validation_pass'])
 def test_state_mutation(self):
  t,r,s=self.fixture();s['active_state_unchanged']=False;self.assertFalse(summarize(t,r,s)['causal_validation_pass'])
 def test_missing_stage(self):
  t,r,s=self.fixture();t['rows'].pop()
  with self.assertRaises(ValueError):summarize(t,r,s)
 def test_bad_geometry(self):
  t,r,s=self.fixture();t['rows'][0]['floats']=5
  with self.assertRaises(ValueError):summarize(t,r,s)
if __name__=='__main__':unittest.main(verbosity=2)
