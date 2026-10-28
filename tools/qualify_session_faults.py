#!/usr/bin/env python3
"""True half-close and bounded checked-forward fault injection, exact recovery."""
import argparse,os,subprocess,uuid
from session_gate_support import *
def turns(s,half_close=False):
 sid='fault-'+uuid.uuid4().hex;records=[]
 for n,msgs in enumerate([[USER],[FOLLOW]]):
  b=body(msgs,sid,n==0);status,reply=call(b,half_close=half_close and n==0);assert status==200,(status,reply)
  records.append(state(s,b));assert records[-1]['accepted']
 return records
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);cases=[]
 with server(a.out/'half-close') as s:
  baseline=turns(s);half=turns(s,True)
  for x,y in zip(baseline,half):equal(x,y)
 cases.append(dict(case='TCP_SHUT_WR',status='PASS',contract='Successful response and continuation; FIN is not cancellation',state_exact=True))
 for name,pos in [('prefill_failure',20),('decode_failure',40)]:
  with server(a.out/name,env_extra={'FLASH_SESSION_TEST_FORWARD_FAIL_POS':str(pos)}) as s:
   sid='broken-'+uuid.uuid4().hex;b=body([USER],sid,True);status,reply=call(b)
   assert status>=400 and reply.get('session_invalidated') and reply.get('resend_full_history'),(status,reply)
   failed=state(s,b);assert failed['failed'] and not failed['accepted'] and failed['end_position']==0
   stale,error=call(body([FOLLOW],sid));assert stale==409
   recovered=turns(s)
   for x,y in zip(baseline,recovered):equal(x,y)
  cases.append(dict(case=name,status='PASS',http_status=status,stale_status=stale,fresh_state_exact=True,method='Once-per-process diagnostic post-layer checked-forward failure; not real hardware failure'))
 control=a.out/'control';control.mkdir();inputfile=a.out/'input.json';final=baseline[-1];write(inputfile,dict(token_ids=final['effective_token_ids'],expected_digests={str(r['position']):r['digest'] for r in final['steps']}))
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(inputfile));print('FAULT_CONTROL_START',stamp(),flush=True)
 with (a.out/'control.log').open('w') as f:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered','--no-prefill-nrow'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 print('FAULT_CONTROL_STOP',stamp(),'exit',r.returncode,flush=True);assert r.returncode==0
 write(a.out/'result.json',dict(status='PASS',cases=cases,baseline_matches_scalar_control=True,hardware_faults='NOT ESTABLISHED',executor_callbacks='NOT APPLICABLE: HTTP infer returns tool calls; it does not execute external tools'))
 return 0
if __name__=='__main__':raise SystemExit(main())
