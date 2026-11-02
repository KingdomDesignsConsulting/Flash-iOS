#!/usr/bin/env python3
"""Live partial snapshot-allocation failure and private checkpoint write EIO.
No real memory exhaustion, hardware fault or production profile mutation.
"""
import argparse
from session_gate_support import *
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);profile='qual-resource-'+uuid.uuid4().hex[:8];sysmsg={'role':'system','content':'You are a helpful assistant. Context labels:'+(' x'*128)};cases=[]
 def turns(s):
  sid='resource-'+uuid.uuid4().hex;records=[]
  for n,msgs in enumerate([[sysmsg,USER],[FOLLOW]]):
   b=body(msgs,sid,n==0,profile);code,reply=call(b);assert code==200,(code,reply);st=state(s,b);assert st['accepted'] and st['history_complete'] and not st['failed'];records.append(st)
  return records
 with server(a.out/'baseline',args=['--prefill-nrow']) as s:baseline=turns(s)
 for name in ['snapshot_allocation','checkpoint_write']:
  arm=a.out/name/'fault.arm';env={'FLASH_SESSION_TEST_SNAPSHOT_OOM_ARM':str(arm.resolve())} if name=='snapshot_allocation' else {'FLASH_SESSION_TEST_WRITE_FAIL_AFTER':'4096'}
  cache=a.out/(name+'-cache')
  with server(a.out/name,cache,args=['--prefill-nrow'],env_extra=env) as s:
   if name=='snapshot_allocation':arm.touch(exist_ok=False)
   records=turns(s)
   for x,y in zip(baseline,records):equal(x,y)
   recovered=turns(s)
   for x,y in zip(baseline,recovered):equal(x,y)
  log=(a.out/name/'server.log').read_text()
  marker='simulated snapshot allocation failure after partial capture' if name=='snapshot_allocation' else 'warm-state'
  assert marker in log,('fault not exercised',name)
  if name=='checkpoint_write':assert 'write failed' in log or 'save failed' in log or 'save failure' in log or 'failed to save' in log,log[-4000:]
  leftovers=list(cache.rglob('*.tmp.*'));assert not leftovers,leftovers
  with server(a.out/(name+'-restart'),cache,args=['--prefill-nrow','--flash-profile',profile]) as s:
   restart=turns(s)
   for x,y in zip(baseline,restart):equal(x,y)
  cases.append(dict(case=name,status='PASS',request_and_followup_state_exact=True,fresh_state_exact=True,restart_state_exact=True,temp_files_remaining=0,real_resource_exhaustion=False))
  write(a.out/'result.json',dict(status='RUNNING',cases=cases))
 write(a.out/'result.json',dict(status='PASS',cases=cases,scope='Controlled diagnostic partial-allocation failure and write EIO; no real system OOM or storage failure.'))
 return 0
if __name__=='__main__':raise SystemExit(main())
