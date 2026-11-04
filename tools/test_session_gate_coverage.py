#!/usr/bin/env python3
import unittest
from session_gate_support import equal
def sample(start):return dict(initial_position=start,end_position=4,effective_token_ids=[1,2,3,4],accepted=True,steps=[dict(position=p,digest=str(p)) for p in range(start,5)])
class Coverage(unittest.TestCase):
 def test_cached_prefix_observations(self):equal(sample(0),sample(2))
 def test_restored_endpoint_mismatch_rejects(self):
  b=sample(2);b['steps'][0]['digest']='wrong'
  with self.assertRaises(AssertionError):equal(sample(0),b)
 def test_missing_tail_observation_rejects(self):
  b=sample(2);b['steps'].pop(1)
  with self.assertRaises(AssertionError):equal(sample(0),b)
if __name__=='__main__':unittest.main(verbosity=2)
