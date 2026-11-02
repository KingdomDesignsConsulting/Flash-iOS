#!/usr/bin/env python3
"""Isolated real SSE checked-forward failures; no executor actions or hardware reset."""
import argparse,http.client
from session_gate_support import *

def stream(b):
 c=http.client.HTTPConnection('127.0.0.1',11243,timeout=120)
 c.request('POST','/v1/chat/completions',json.dumps(b),{'Content-Type':'application/json'})
 r=c.getresponse();status=r.status;raw=r.read().decode();c.close();events=[]
 for line in raw.splitlines():
  if line.startswith('data: '):
   data=line[6:];events.append(data if data=='[DONE]' else json.loads(data))
 return status,events,raw

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 prompt={'role':'user','content':'List the integers from one to one hundred, one number per line. Continue the list without an introduction.'}
 records=[];baseline=None
 # Learn the exact native prompt length from an unmodified successful request.
 with server(a.out/'baseline',args=['--prefill-nrow']) as s:
  b=body([prompt],'baseline-'+uuid.uuid4().hex,True);b['max_tokens']=24
  code,reply=call(b);assert code==200,(code,reply)
  baseline=state(s,b);prefix=reply['usage']['prompt_tokens'];assert prefix>20
  assert baseline['accepted'] and baseline['history_complete']
  write(a.out/'baseline.json',dict(response=reply,state=baseline,prompt_tokens=prefix))
 for name,pos in [('before_first_output',20),('after_visible_deltas',prefix+5),('expert_io_failure',None)]:
  inject={'FLASH_SESSION_TEST_FORWARD_FAIL_POS':str(pos)} if pos is not None else {'FLASH_SESSION_TEST_EXPERT_IO_FAIL':str((a.out/name/'expert-io.arm').resolve())}
  with server(a.out/name,args=['--prefill-nrow'],env_extra=inject) as s:
   if pos is None:(a.out/name/'expert-io.arm').touch(exist_ok=False)
   sid='stream-fault-'+uuid.uuid4().hex;b=body([prompt],sid,True);b.update(stream=True,max_tokens=48,stream_options={'include_usage':True})
   code,events,raw=stream(b);(a.out/(name+'.sse')).write_text(raw)
   errors=[e for e in events if isinstance(e,dict) and 'error' in e]
   assert errors,(code,events)
   error=errors[-1];assert error.get('session_invalidated') and error.get('resend_full_history'),error
   choices=[ch for e in events if isinstance(e,dict) for ch in e.get('choices',[])]
   visible=[ch.get('delta',{}).get('content','') for ch in choices if ch.get('delta',{}).get('content')]
   assert not any(ch.get('finish_reason') in ['stop','tool_calls','length'] for ch in choices),events
   assert not any(ch.get('delta',{}).get('tool_calls') for ch in choices),events
   assert (bool(visible) if name=='after_visible_deltas' else not visible),(name,visible,prefix)
   failed=state(s,b);assert failed['failed'] and not failed['accepted'] and failed['end_position']==0
   stale,missing=call(body([FOLLOW],sid));assert stale==409 and missing.get('session_invalidated')
   fresh=body([prompt],'fresh-'+uuid.uuid4().hex,True);fresh['max_tokens']=24
   recovered,reply=call(fresh);assert recovered==200;equal(baseline,state(s,fresh))
   with urllib.request.urlopen('http://127.0.0.1:11243/health',timeout=3) as r:assert r.status==200
   records.append(dict(case=name,status='PASS',http_status=code,error=error,visible_content_deltas=len(visible),injection_position=pos,end_position=failed['end_position'],stale_status=stale,fresh_state_exact=True,done_count=events.count('[DONE]')))
 control=a.out/'control';control.mkdir();f=a.out/'replay.json';write(f,dict(token_ids=baseline['effective_token_ids'],expected_digests={str(x['position']):x['digest'] for x in baseline['steps']}));gate()
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(f))
 print('STREAM_SCALAR_CONTROL_START',stamp(),flush=True)
 with (control/'engine.log').open('w') as log:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered','--no-prefill-nrow'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 print('STREAM_SCALAR_CONTROL_STOP',stamp(),'exit',r.returncode,flush=True);assert r.returncode==0
 write(a.out/'result.json',dict(status='PASS',cases=records,baseline_matches_scalar_control=True,scope='Real SSE with controlled once-per-process checked-forward failure. No hardware reset or tool executor action.'))
 return 0
if __name__=='__main__':raise SystemExit(main())
