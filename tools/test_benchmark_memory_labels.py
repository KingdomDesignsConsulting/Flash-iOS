"""Model-free checks for observer labels and historical launch-based correction."""
import json, pathlib, tempfile, unittest
from observe_benchmark_memory import classify_mode
from summarize_benchmark_memory import summarize

class Labels(unittest.TestCase):
 def test_final_override(self):
  self.assertEqual(classify_mode('infer-control --no-prefill-nrow --serve 11243 --prefill-nrow'),'control')
  self.assertEqual(classify_mode('infer-control --prefill-nrow --no-prefill-nrow'),'scalar')
  self.assertEqual(classify_mode('infer-release-prefetch-performance --no-prefill-nrow --prefill-nrow'),'candidate')
 def test_derived_correction_preserves_raw(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory); p=root/'performance-http/0-ordinary';p.mkdir(parents=True)
   (p/'launch.json').write_text(json.dumps(dict(started='2026-11-02T15:00:00-08:00',command=['infer-control','--no-prefill-nrow','--prefill-nrow'])))
   raw=root/'samples.jsonl';raw.write_text(json.dumps(dict(kind='SAMPLE',at='2026-11-02T15:00:01-08:00',scope='http',mode='scalar',pid=1,start_abstime=7,physical_bytes=10,peak_physical_bytes=11,rss_bytes=12))+'\n');before=raw.read_bytes()
   result=summarize(root,raw)
   self.assertEqual(result['corrected_sample_count'],1);self.assertEqual(result['groups'][0]['mode'],'control');self.assertEqual(raw.read_bytes(),before)
 def test_unmatched_launch_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);raw=root/'samples.jsonl';raw.write_text(json.dumps(dict(kind='SAMPLE',at='2026-11-02T15:00:01-08:00',scope='http',mode='scalar'))+'\n')
   with self.assertRaises(AssertionError):summarize(root,raw)
if __name__=='__main__':unittest.main()
