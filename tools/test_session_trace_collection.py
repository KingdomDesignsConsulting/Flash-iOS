#!/usr/bin/env python3
"""Model-free collector regressions, including restart reuse and delayed publish."""
import json,pathlib,tempfile,threading,time,unittest
from unittest.mock import patch
from io import BytesIO
from experiment_session_token_exact import collect,make_call
from experiment_session_effective_history import effective_prompt
class Collection(unittest.TestCase):
 def test_nonce_is_sent_in_request(self):
  captured=[]
  def reply(req,timeout):
   captured.append(json.loads(req.data));return BytesIO(json.dumps({'id':'chatcmpl-1','choices':[{'message':{'content':'ok'}}]}).encode())
  with patch('urllib.request.urlopen',side_effect=reply):response=make_call('http://127.0.0.1:11243/v1',[])
  self.assertEqual(captured[0]['flash_trace_id'],response['trace_identity'])
 def test_effective_prompt_includes_cached_prefix(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'state.json';p.write_text(json.dumps({'history_complete':True,'effective_token_ids':[10,11,12,13,14],'end_position':5}))
   self.assertEqual(effective_prompt({'test':{'state_trace':str(p)}},'test',{'forwarded_positions':[4]}),[10,11,12,13])

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
