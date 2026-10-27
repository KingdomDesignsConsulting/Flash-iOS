#!/usr/bin/env python3
"""Model-free collector regressions, including restart reuse and delayed publish."""
import json,pathlib,tempfile,threading,time,unittest
from experiment_session_token_exact import collect
class Collection(unittest.TestCase):
 def test_unique_nonce_and_delayed_generated_publish(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);identity='new';rid='chatcmpl-1'
   (p/'old-generated.json').write_text(json.dumps({'request_id':rid,'trace_identity':'old'}))
   def publish():
    time.sleep(.05);(p/'new-generated.json').write_text(json.dumps({'request_id':rid,'trace_identity':identity,'completed_token_ids':[3]}))
   worker=threading.Thread(target=publish);worker.start()
   file,d=collect(p,{},rid,identity,'generated',attempts=10);worker.join()
   self.assertEqual(file.name,'new-generated.json');self.assertEqual(d['completed_token_ids'],[3])
 def test_stale_nonce_not_accepted(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);(p/'old-prompt.json').write_text(json.dumps({'request_id':'chatcmpl-1','token_ids':[1],'prompt_tokens':1}))
   with self.assertRaises(RuntimeError):collect(p,{},'chatcmpl-1','new',attempts=1)
 def test_same_nonce_wrong_request_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);(p/'new-prompt.json').write_text(json.dumps({'request_id':'wrong','trace_identity':'new','token_ids':[1],'prompt_tokens':1}))
   with self.assertRaises(RuntimeError):collect(p,{},'chatcmpl-1','new',attempts=1)
 def test_legacy_overwrite_detected_by_metadata(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);f=p/'chatcmpl-1.json';f.write_text('{}');before={f:(f.stat().st_mtime_ns,f.stat().st_size)}
   f.write_text(json.dumps({'request_id':'chatcmpl-1','token_ids':[2],'prompt_tokens':1}))
   _,d=collect(p,before,'chatcmpl-1',attempts=1);self.assertEqual(d['token_ids'],[2])
if __name__=='__main__':unittest.main(verbosity=2)
