#!/usr/bin/env python3
"""Reject oversized legal requests before state mutation; no long generation."""
import argparse
from session_gate_support import *
def observe(sid):
 b=body([FOLLOW],sid);b.update(flash_qual_count_only=True,flash_qual_hash=True,max_tokens=1)
 code,x=call(b);assert code==200 and x['session_reused'] and x['state_hash']!='not_requested';assert len(x['kv_lengths'])==10 and all(v==x['resident_pos'] for v in x['kv_lengths'].values());return x

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);cases=[]
 with server(a.out/'server',args=['--prefill-nrow'],env_extra={'FLASH_HTTP_QUALIFICATION':'1'}) as s:
  sid='capacity-'+uuid.uuid4().hex;b=body([USER],sid,True);code,reply=call(b);assert code==200;before=observe(sid)
  # Valid input text is intentionally one token beyond the runtime limit after
  # rendering. The server must count and reject it, not attempt its prefill.
  for fresh in [False,True]:
   target_sid=('fresh-'+uuid.uuid4().hex) if fresh else sid;n=65536
   # Use the real renderer/count-only observer to target cap+1 precisely.
   # Counting does not prefill the large prompt or replace the active session.
   for attempt in range(4):
    rejected=body([{'role':'user','content':' x'*n}],target_sid,fresh);rejected['max_tokens']=2
    counted=dict(rejected,flash_qual_count_only=True);code,info=call(counted);assert code==200
    required=info['context_tokens']+2;delta=required-(info['cpu_capacity']+1)
    if delta==0:break
    n-=delta;assert n>0
   else:raise AssertionError('Could not construct exact cap+1 request')
   assert required==info['cpu_capacity']+1
   code,error=call(rejected);assert code==400 and error.get('error')=='context length exceeds engine KV capacity',(code,error)
   after=observe(sid);assert after==before,(before,after)
   cases.append(dict(case='fresh' if fresh else 'continuation',status='PASS',http_status=code,resident_position=after['resident_pos'],all_ten_kv_lengths=after['kv_lengths'],state_hash_before=before['state_hash'],state_hash_after=after['state_hash'],cpu_capacity=after['cpu_capacity'],counted_context_tokens=info['context_tokens'],requested_generation_tokens=2,required_tokens=required,exactly_one_over_capacity=True))
  b=body([FOLLOW],sid);code,reply=call(b);assert code==200;st=state(s,b);assert st['accepted'] and not st['failed']
 control=a.out/'control';control.mkdir();f=a.out/'replay.json';write(f,dict(token_ids=st['effective_token_ids'],expected_digests={str(x['position']):x['digest'] for x in st['steps']}));gate();env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(f))
 print('CAPACITY_CONTROL_START',stamp(),flush=True)
 with (control/'engine.log').open('w') as log:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered','--no-prefill-nrow'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 print('CAPACITY_CONTROL_STOP',stamp(),'exit',r.returncode,flush=True);assert r.returncode==0
 write(a.out/'result.json',dict(status='PASS',cases=cases,post_rejection_continuation_matches_scalar=True,scope='Real runtime capacity rejection at 65536; not execution beyond GPU cap.'))
 return 0
if __name__=='__main__':raise SystemExit(main())
