#!/usr/bin/env python3
"""Fail during an observed tool envelope; never execute external tool actions."""
import argparse
from qualify_release_stream_faults import stream
from experiment_session_token_exact import collect
from session_gate_support import *
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 tools=[dict(type='function',function=dict(name='echo',description='Echo the synthetic payload.',parameters=dict(type='object',properties={'payload':{'type':'string'}},required=['payload'],additionalProperties=False)))]
 prompt={'role':'user','content':'Use echo once with payload exactly alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.'}
 def request(sid,create=True):
  b=body([SYS,prompt],sid,create);b.update(tools=tools,max_tokens=80);return b
 with server(a.out/'baseline',args=['--prefill-nrow']) as s:
  b=request('baseline-'+uuid.uuid4().hex);code,reply=call(b);assert code==200 and reply['choices'][0]['message'].get('tool_calls')
  baseline=state(s,b);assert baseline['history_complete'] and baseline['accepted'];_,gen=collect(s['trace'],{},reply['id'],b['flash_trace_id'],'generated')
  ids=gen['forwarded_token_ids'];start=ids.index(248058);end=ids.index(248059);assert end>start+6
  inside=(start+end)//2;position=reply['usage']['prompt_tokens']+inside;write(a.out/'baseline.json',dict(response=reply,state=baseline,generated=gen,injection_position=position,inside_tool_envelope=True))
 with server(a.out/'fault',args=['--prefill-nrow'],env_extra={'FLASH_SESSION_TEST_FORWARD_FAIL_POS':str(position)}) as s:
  sid='tool-failure-'+uuid.uuid4().hex;b=request(sid);b['stream']=True;code,events,raw=stream(b);(a.out/'interrupted.sse').write_text(raw);assert code==200
  errors=[e for e in events if isinstance(e,dict) and 'error' in e];assert errors and errors[-1].get('session_invalidated') and errors[-1].get('resend_full_history')
  choices=[c for e in events if isinstance(e,dict) for c in e.get('choices',[])];assert not any(c.get('delta',{}).get('tool_calls') or c.get('finish_reason') in ['tool_calls','stop','length'] for c in choices)
  failed=state(s,b);assert failed['failed'] and not failed['accepted'] and failed['end_position']==0
  partial=waitfile(s['trace']/(b['flash_trace_id']+'-generated.json'));assert 248058 in partial['forwarded_token_ids'] and 248059 not in partial['forwarded_token_ids'],'Failure must occur inside actual unfinished tool wire'
  stale,error=call(body([FOLLOW],sid));assert stale==409
  fresh=request('tool-recovery-'+uuid.uuid4().hex);code,recovered=call(fresh);assert code==200;equal(baseline,state(s,fresh))
  tool=recovered['choices'][0]['message']['tool_calls'][0]
  follow=body([{'role':'tool','tool_call_id':tool['id'],'content':'synthetic success; no external action executed'}],fresh['session_id']);follow.update(tools=tools,max_tokens=16)
  code,answer=call(follow);write(a.out/'followup-response.json',dict(http_status=code,response=answer));assert code==200 and answer['flash_timings']['session_reused'],(code,answer);final=state(s,follow);assert final['accepted'] and final['history_complete']
 control=a.out/'control';control.mkdir();f=a.out/'replay.json';write(f,dict(token_ids=final['effective_token_ids'],expected_digests={str(x['position']):x['digest'] for x in final['steps']}));gate();env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(f));print('TOOL_CONTROL_START',stamp(),flush=True)
 with (control/'engine.log').open('w') as log:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered','--no-prefill-nrow'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=240)
 print('TOOL_CONTROL_STOP',stamp(),'exit',r.returncode,flush=True);assert r.returncode==0
 write(a.out/'result.json',dict(status='PASS',injection_position=position,inside_actual_incomplete_tool_envelope=True,http_status=200,explicit_error=True,partial_tool_delta_emitted=False,end_position_after_failure=0,stale_status=stale,fresh_state_exact=True,resident_tool_result_followup=True,followup_end_position=final['end_position'],scalar_recovery_and_followup_exact=True,external_tools_executed=False))
 return 0
if __name__=='__main__':raise SystemExit(main())
