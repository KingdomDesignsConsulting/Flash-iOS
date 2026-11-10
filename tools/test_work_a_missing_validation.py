import copy,unittest
from validate_work_a_missing import validate
class MissingValidation(unittest.TestCase):
 def setUp(self):
  rows=[]
  for mode in ['mask63','scalar']:
   c=dict(label='cold',timings=dict(context_tokens=32768,prefill_tokens=32768,cached_prefix_tokens=0,generated_tokens=32,prefill_ms=1,decode_ms=1,prefill_tokens_per_second=32768000,decode_tokens_per_second=32000),usage=dict(prompt_tokens=32768,completion_tokens=32,total_tokens=32800),allocation=dict(gpu_capacity=32768,cpu_capacity=65536,resident_pos=32800,kv_lengths={str(i):32800 for i in range(3,40,4)}))
   warm=copy.deepcopy(c);warm['label']='warm';rows.append(dict(mode=mode,binary_sha256=mode,host_free_before=40,post_gpu=[1,2,3],budget=dict(stop_reason=None,exit=-15,peak_rss_bytes=1),memory=dict(samples=1),cases=[c,warm],boundary_routes=[dict(length=n,backend=b,layer=i,cap=32768) for n,b in [(32768,'GPU'),(32769,'CPU')] for i in range(3,40,4)]))
  self.r=dict(status='COMPLETED_EXPLORATORY',release_manifest_sha256='m',input_sha256='i',rendered_ids_sha256='r',count=32768,repeats=1,selected_modes=['mask63','scalar'],rows=rows)
 def run_check(self):return validate(self.r,'m',{'mask63':'mask63','scalar':'scalar'},'i','r')
 def test_complete_evidence_accepts_without_claiming_variance(self):self.assertFalse(self.run_check()['variance_measured'])
 def test_running_cannot_pass(self):
  self.r['status']='RUNNING'
  with self.assertRaises(AssertionError):self.run_check()
 def test_missing_warm_cannot_pass(self):
  self.r['rows'][0]['cases'].pop()
  with self.assertRaises(AssertionError):self.run_check()
 def test_missing_layer_cannot_pass(self):
  self.r['rows'][0]['boundary_routes'].pop()
  with self.assertRaises(AssertionError):self.run_check()
 def test_watchdog_event_cannot_pass(self):
  self.r['rows'][0]['budget']['stop_reason']='HOST_MEMORY'
  with self.assertRaises(AssertionError):self.run_check()
 def test_wrong_context_or_binary_cannot_pass(self):
  self.r['rows'][0]['binary_sha256']='foreign'
  with self.assertRaises(AssertionError):self.run_check()
 def test_nonfinite_timing_cannot_pass(self):
  self.r['rows'][0]['cases'][0]['timings']['prefill_ms']=float('nan')
  with self.assertRaises(AssertionError):self.run_check()
if __name__=='__main__':unittest.main()
