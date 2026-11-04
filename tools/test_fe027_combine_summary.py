import copy,unittest
from summarize_fe027_combine import summarize,LAYERS,POSITIONS
class CombineSummary(unittest.TestCase):
    def fixture(self):
        m=dict(exact=True,max_abs=0,rms=0,nonfinite=0)
        names=[('weighted_product',k) for k in range(8)]+[('expert_accumulation',k) for k in range(8)]+[(s,-1) for s in ['sigmoid','shared_contribution','residual_plus_experts','final']]
        rows=[]
        for phase in range(2):
            for l in LAYERS:
                for pos in POSITIONS:rows.append(dict(phase=phase,layer=l,position=pos,path='actual',ids=[l+pos+k for k in range(8)],expected_live_replay_exact=True,trace_vs_original_gpu=copy.deepcopy(m),gpu_replay_vs_live=copy.deepcopy(m),cpu_replay_vs_live=copy.deepcopy(m),stages=[dict(stage=n,slot=k,difference=copy.deepcopy(m)) for n,k in names],operand_differences=[copy.deepcopy(m) for _ in range(10)],weights=copy.deepcopy(m),shared_score=copy.deepcopy(m),same_expert_ids=True,actual_output_difference=copy.deepcopy(m)))
        return dict(dimensions=2048,rows=rows),dict(active_state_unchanged=True)
    def test_complete(self):self.assertTrue(summarize(*self.fixture())['causal_validation_pass'])
    def test_missing_row(self):
        r,s=self.fixture();r['rows'].pop()
        with self.assertRaises(ValueError):summarize(r,s)
    def test_live_mismatch(self):
        r,s=self.fixture();r['rows'][0]['expected_live_replay_exact']=False;self.assertFalse(summarize(r,s)['causal_validation_pass'])
    def test_unfaithful_trace(self):
        r,s=self.fixture();r['rows'][0]['trace_vs_original_gpu']['exact']=False;self.assertFalse(summarize(r,s)['causal_validation_pass'])
    def test_mutation(self):
        r,s=self.fixture();s['active_state_unchanged']=False;self.assertFalse(summarize(r,s)['causal_validation_pass'])
    def test_missing_stage(self):
        r,s=self.fixture();r['rows'][0]['stages'].pop()
        with self.assertRaises(ValueError):summarize(r,s)
    def test_nonfinite(self):
        r,s=self.fixture();r['rows'][0]['weights']['max_abs']=float('nan')
        with self.assertRaises(ValueError):summarize(r,s)
if __name__=='__main__':unittest.main()
