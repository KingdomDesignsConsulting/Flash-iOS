#!/usr/bin/env python3
"""Actual native chat executable against deterministic loopback HTTP faults.
No model, shell tool execution, HOME override, or production server access.
"""
import argparse,json,os,pathlib,signal,socketserver,subprocess,tempfile,threading,time,unittest
P=pathlib.Path
def event(body):return 'data: '+json.dumps(body,ensure_ascii=False)+'\n\n'
def delta(text):return event({'choices':[{'delta':{'content':text},'finish_reason':None}]})
FINISH=event({'choices':[{'delta':{},'finish_reason':'stop'}]})
HEADER='HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n'
INVALID={'error':{'message':'resident unavailable'},'session_invalidated':True,'resend_full_history':True}
def success(text='ANSWER'):return HEADER+delta(text)+FINISH+'data: [DONE]\n\n'
def invalid(stream=True):return HEADER+event(INVALID)+'data: [DONE]\n\n' if stream else 'HTTP/1.1 409 Conflict\r\nConnection: close\r\n\r\n'+json.dumps(INVALID)
class Mock(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
 def __init__(self,plans):
  self.plans=list(plans);self.requests=[];self.received=threading.Event()
  class Handler(socketserver.BaseRequestHandler):
   def handle(h):
    h.request.settimeout(3);raw=b''
    try:
     while b'\r\n\r\n' not in raw:
      part=h.request.recv(4096)
      if not part:return  # native client's initial health connection
      raw+=part
     head,body=raw.split(b'\r\n\r\n',1)
     n=int(next(x.split(b':',1)[1] for x in head.split(b'\r\n') if x.lower().startswith(b'content-length:')))
     while len(body)<n:body+=h.request.recv(n-len(body))
     self.requests.append(json.loads(body));self.received.set();plan=self.plans.pop(0)
     if callable(plan):plan(h.request)
     else:h.request.sendall(plan.encode())
    except (OSError,IndexError):pass
  super().__init__(('127.0.0.1',0),Handler)
  self.thread=threading.Thread(target=self.serve_forever,daemon=True);self.thread.start()
 def close(self):self.shutdown();self.server_close();self.thread.join()
class ChatTests(unittest.TestCase):
 def run_chat(self,plans,lines='question\n/quit\n',fixture=None,resume=False,cancel=False,pending=None,concurrent_fixture=None,tool_stub=False):
  with tempfile.TemporaryDirectory(prefix='flash-chat-mock-') as folder:
   state=P(folder);sid='fixture'
   if fixture is not None:(state/(sid+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in fixture))
   if pending is not None:(state/(sid+'.jsonl.pending.json')).write_text(json.dumps(pending))
   if concurrent_fixture is not None:
    def change_history(sock):
     (state/(sid+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in concurrent_fixture))
     sock.sendall(success().encode())
    plans=[change_history]
   mock=Mock(plans)
   try:
    args=[str(BINARY.with_name('chat-tool-fixture-test') if tool_stub else BINARY),'--port',str(mock.server_address[1]),'--max-tokens','24']
    if resume:args+=['--resume',sid]
    proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,FLASH_CHAT_STATE_DIR=folder,FLASH_CHAT_TIMEOUT_MS='150'))
    def interrupt():
     if mock.received.wait(3):
      time.sleep(.03)
      if proc.poll() is None:proc.send_signal(signal.SIGINT)
    timer=threading.Thread(target=interrupt,daemon=True) if cancel else None
    if timer:timer.start()
    stdout,stderr=proc.communicate(lines.encode(),timeout=8)
    if timer:timer.join(timeout=1)
    self.assertIn(proc.returncode,(0,1),stderr.decode())
    files={p.name:[json.loads(x) for x in p.read_text().splitlines()] for p in state.glob('*.jsonl')}
    return mock.requests,files,stderr.decode(),stdout.decode()
   finally:mock.close()
 def test_initial_and_multiple_continuations(self):
  req,files,_,_=self.run_chat([success('ONE'),success('TWO'),success('THREE')],'a\nb\nc\n/quit\n')
  self.assertEqual([x['content'] for x in next(iter(files.values()))],['a','ONE','b','TWO','c','THREE'])
  self.assertTrue(req[0]['flash_session_create']);self.assertEqual([len(r['messages']) for r in req],[1,1,1]);self.assertEqual(len({r['session_id'] for r in req}),1)
 def test_resume_uses_full_history_fresh_id(self):
  fixture=[{'role':'user','content':'old'},{'role':'assistant','content':'answer'}]
  req,files,_,_=self.run_chat([success()],fixture=fixture,resume=True)
  self.assertEqual(req[0]['messages'][:-1],fixture);self.assertTrue(req[0]['flash_session_create']);self.assertNotEqual(req[0]['session_id'],'fixture');self.assertEqual(len(files['fixture.jsonl']),4)
 def test_eviction_http409_and_sse(self):
  for stream in (False,True):
   with self.subTest(stream=stream):
    req,files,_,_=self.run_chat([success('ONE'),invalid(stream),success('TWO')],'a\nb\n/quit\n')
    self.assertEqual(len(req),3);self.assertNotEqual(req[1]['session_id'],req[2]['session_id']);self.assertTrue(req[2]['flash_session_create']);self.assertEqual([x['content'] for x in req[2]['messages']],['a','ONE','b']);self.assertEqual(len(next(iter(files.values()))),4)
 def test_repeated_invalidation_is_bounded(self):
  req,files,_,_=self.run_chat([invalid(),invalid()]);self.assertEqual(len(req),2);self.assertFalse(files)
 def test_partial_output_invalidation_no_replay(self):
  req,files,_,_=self.run_chat([HEADER+delta('partial')+event(INVALID)+'data: [DONE]\n\n']);self.assertEqual(len(req),1);self.assertFalse(files)
 def test_unicode_quotes_whitespace_and_literal_error_words(self):
  answer='session_invalidated: false — 雪 😀 "quoted"\n\\path'
  req,files,_,_=self.run_chat([success(answer)]);self.assertEqual(next(iter(files.values()))[1]['content'],answer);self.assertEqual(len(req),1)
 def test_failed_turn_not_saved_next_request_recreates(self):
  req,files,_,_=self.run_chat([success('ONE'),HEADER+delta('partial'),success('THREE')],'a\nfailed\nc\n/quit\n')
  self.assertTrue(req[2]['flash_session_create']);self.assertNotEqual(req[1]['session_id'],req[2]['session_id']);self.assertEqual([x['content'] for x in req[2]['messages']],['a','ONE','c']);self.assertEqual([x['content'] for x in next(iter(files.values()))],['a','ONE','c','THREE'])
 def test_clear_starts_independent_transcript(self):
  req,files,_,_=self.run_chat([success('ONE'),success('TWO')],'a\n/clear\nb\n/quit\n');self.assertEqual(len(files),2);self.assertTrue(req[1]['flash_session_create']);self.assertEqual(len(req[1]['messages']),1)
 def test_legacy_tool_markup_preserved_in_replay_no_execution(self):
  tool='<tool_call>{"name":"bash","arguments":{"command":"DO NOT EXECUTE"}}</tool_call>'
  fixture=[{'role':'user','content':'old'},{'role':'assistant','content':tool},{'role':'user','content':'<tool_response>synthetic fixture only</tool_response>'},{'role':'assistant','content':'done'}]
  req,files,_,_=self.run_chat([invalid(),success()],fixture=fixture,resume=True)
  self.assertEqual(req[1]['messages'][:-1],fixture);self.assertEqual(len(files['fixture.jsonl']),6)
 def test_corrupt_or_incomplete_transcript_refused(self):
  req,_,err,_=self.run_chat([],fixture=[{'role':'user','content':'orphan'}],resume=True);self.assertFalse(req);self.assertIn('resume',err)
  req,_,_,_=self.run_chat([],fixture=[{'role':'user','content':'x'},{'role':'assistant','content':'x','tool_calls':[{'id':'must-not-be-discarded'}]}],resume=True);self.assertFalse(req)
 def test_pending_tool_output_replayed_once_without_command_execution(self):
  fixture=[{'role':'user','content':'read fixture'},{'role':'assistant','content':'<tool_call>synthetic, never executed</tool_call>'}]
  pending={'role':'user','content':'<tool_response>FIXTURE</tool_response>','anchor_count':2}
  req,files,_,_=self.run_chat([invalid(),success()],'/retry-tool\n/quit\n',fixture=fixture,resume=True,pending=pending)
  self.assertEqual(len(req),2);self.assertEqual(req[1]['messages'][-1]['content'],pending['content']);self.assertEqual(len(files['fixture.jsonl']),4)
 def test_already_committed_pending_tool_not_duplicated(self):
  turn={'role':'user','content':'<tool_response>FIXTURE</tool_response>'}
  fixture=[{'role':'user','content':'read'},{'role':'assistant','content':'tool'},turn,{'role':'assistant','content':'done'}]
  req,files,_,_=self.run_chat([],'/retry-tool\n/quit\n',fixture=fixture,resume=True,pending={**turn,'anchor_count':2})
  self.assertFalse(req);self.assertEqual(len(files['fixture.jsonl']),4)
 def test_concurrent_history_change_never_overwritten(self):
  old=[{'role':'user','content':'old'},{'role':'assistant','content':'old answer'}]
  winner=old+[{'role':'user','content':'other writer'},{'role':'assistant','content':'other reply'}]
  _,files,err,_=self.run_chat([],fixture=old,resume=True,concurrent_fixture=winner)
  self.assertEqual(files['fixture.jsonl'],winner);self.assertIn('commit failed',err)
 def test_real_tool_path_stub_is_never_rerun_on_invalidation(self):
  tool='<tool_call>{"name":"bash","arguments":{"command":"NEVER EXECUTED"}}</tool_call>'
  req,files,err,_=self.run_chat([success(tool),invalid(),success('done')],'question\ny\n/quit\n',tool_stub=True)
  self.assertEqual(err.count('TEST_TOOL_STUB_CALLED'),1);self.assertEqual(len(req),3)
  turns=next(iter(files.values()));self.assertEqual(len(turns),4);self.assertIn('SYNTHETIC_TOOL_OUTPUT',turns[2]['content']);self.assertEqual(req[2]['messages'][1]['content'],tool)
 def test_interrupted_tool_followup_manual_retry_reuses_saved_output(self):
  tool='<tool_call>{"name":"bash","arguments":{"command":"NEVER EXECUTED"}}</tool_call>'
  req,files,err,_=self.run_chat([success(tool),HEADER+delta('partial'),success('done')],'question\ny\n/retry-tool\n/quit\n',tool_stub=True)
  self.assertEqual(err.count('TEST_TOOL_STUB_CALLED'),1);self.assertEqual(len(req),3);self.assertTrue(req[2]['flash_session_create']);self.assertEqual(len(next(iter(files.values()))),4)
 def test_manual_retry_failed_user_turn_occurs_once(self):
  req,files,_,_=self.run_chat([HEADER+delta('partial'),success('done')],'repeat\nrepeat\n/quit\n')
  self.assertTrue(req[1]['flash_session_create']);self.assertEqual([x['content'] for x in next(iter(files.values()))],['repeat','done'])
 def test_transport_fault_matrix(self):
  cases={'before_headers':'','after_headers':HEADER,'partial_event':HEADER+'data: {"choices":',
   'missing_done':HEADER+delta('partial')+FINISH,'malformed_json':HEADER+'data: nope\n\ndata: [DONE]\n\n',
   'missing_finish':HEADER+delta('partial')+'data: [DONE]\n\n',
   'server_500':'HTTP/1.1 500 Internal Server Error\r\n\r\n{"error":"failed"}',
   'false_invalidation':'HTTP/1.1 429 Too Many Requests\r\n\r\n{"error":"session_invalidated","session_invalidated":false}',
   'response_overflow':HEADER+delta('x'*70000)+FINISH+'data: [DONE]\n\n',
   'structured_tool':HEADER+event({'choices':[{'delta':{'tool_calls':[{'id':'x'}]},'finish_reason':'tool_calls'}]})+'data: [DONE]\n\n'}
  cases['bad_content_length']=HEADER.replace('Connection: close','Content-Length: 999999\r\nConnection: close')+delta('partial')+FINISH+'data: [DONE]\n\n'
  cases['truncated_invalidation']=HEADER+event(INVALID)
  cases['unsupported_chunked']=HEADER.replace('Connection: close','Transfer-Encoding: chunked\r\nConnection: close')+delta('partial')+FINISH+'data: [DONE]\n\n'
  for name,wire in cases.items():
   with self.subTest(name=name):
    req,files,_,_=self.run_chat([wire]);self.assertEqual(len(req),1);self.assertFalse(files)
 def test_declared_content_length_complete_response(self):
  wire=success('OK');header,body=wire.split('\r\n\r\n',1)
  wire=header+'\r\nContent-Length: '+str(len(body.encode()))+'\r\n\r\n'+body
  _,files,_,_=self.run_chat([wire]);self.assertEqual(next(iter(files.values()))[-1]['content'],'OK')
 def test_prefill_and_generation_timeout(self):
  for prelude in (HEADER,HEADER+delta('partial')):
   def stall(sock):sock.sendall(prelude.encode());time.sleep(.4)
   req,files,_,_=self.run_chat([stall]);self.assertEqual(len(req),1);self.assertFalse(files)
 def test_cancellation_does_not_commit(self):
  def stall(sock):sock.sendall((HEADER+delta('partial')).encode());time.sleep(.4)
  _,files,_,_=self.run_chat([stall],cancel=True);self.assertFalse(files)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=P,default=P(__file__).resolve().parents[1]/'metal_infer/chat');ap.add_argument('--out',type=P,required=True);a=ap.parse_args();BINARY=a.binary.resolve()
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(ChatTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps({'result':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':[str(x) for x in result.failures],'errors':[str(x) for x in result.errors],'model_inference':False,'shell_tools_executed':False},indent=2))
 raise SystemExit(not result.wasSuccessful())
