import copy,unittest
from analyze_nrow_routes import analyze

class Routes(unittest.TestCase):
    def fixture(self):
        row=dict(layer=0,position=0,experts=[0,1],router_scores=[2.,1.,.5],post_sha256='abc')
        return dict(start=0,end=1,layers=1,reference={'0:0':row},candidate={'0:0':copy.deepcopy(row)})
    def test_exact(self):
        r=analyze(self.fixture());self.assertEqual(r['expert_set_changes'],0);self.assertEqual(r['exact_post_inputs'],1)
    def test_order_only_is_not_set_flip(self):
        t=self.fixture();t['candidate']['0:0']['experts']=[1,0];r=analyze(t)
        self.assertEqual(r['ordered_selection_changes'],1);self.assertEqual(r['expert_set_changes'],0)
    def test_tie_crossing(self):
        t=self.fixture();t['reference']['0:0']['router_scores']=[2.,1.000001,1.]
        t['candidate']['0:0'].update(experts=[0,2],router_scores=[2.,1.,1.]);r=analyze(t)
        self.assertEqual(r['expert_set_changes'],1);self.assertAlmostEqual(r['first_by_layer_then_position']['reference_cutoff_margin'],1e-6)
        self.assertEqual(r['first_by_layer_then_position']['candidate_cutoff_margin'],0)
    def test_missing_and_extra_coverage_rejected(self):
        for key in ('reference','candidate'):
            t=self.fixture();t[key]={}
            with self.assertRaises(ValueError):analyze(t)
        t=self.fixture();t['candidate']['extra']=t['candidate']['0:0']
        with self.assertRaises(ValueError):analyze(t)
    def test_mismatched_identity_rejected(self):
        t=self.fixture();t['candidate']['0:0']['position']=1
        with self.assertRaises(ValueError):analyze(t)
if __name__=='__main__':unittest.main(verbosity=2)
