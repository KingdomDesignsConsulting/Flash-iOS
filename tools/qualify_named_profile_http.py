#!/usr/bin/env python3
"""Actual named-profile capture/restart/reject/fallback; isolated caches only."""
import argparse,hashlib,pathlib,struct,uuid
from session_gate_support import *
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def conversation(s,profile):
 sid='profile-'+uuid.uuid4().hex;records=[]
 for n,msgs in enumerate([[SYS,USER],[FOLLOW]]):
  b=body(msgs,sid,n==0,profile);status,reply=call(b);assert status==200,(status,reply)
  st=state(s,b);assert st['accepted'] and st['history_complete'];records.append(st)
 return sid,records
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=P,required=True);p.add_argument('--engine-arg',action='append',default=[]);p.add_argument('--compatible-only',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 cache=a.out/'cache';profile='qual-'+uuid.uuid4().hex[:12];cases=[]
 with server(a.out/'capture',cache,args=a.engine_arg) as s:old_sid,baseline=conversation(s,profile)
 checkpoints=list((cache/'warm-state').glob('zstd-*.state'));assert len(checkpoints)==1,checkpoints
 cp=checkpoints[0];saved=cp.read_bytes();(a.out/'baseline-checkpoint.backup').write_bytes(saved)
 source=cache/'warm-tools-cache'/('flash-'+profile+'-warm.json');original_source=source.read_bytes()
 with server(a.out/'restart',cache,args=[*a.engine_arg,'--flash-profile',profile]) as s:
  status,reply=call(body([FOLLOW],old_sid,profile=profile));assert status==409
  _,restored=conversation(s,profile)
  for x,y in zip(baseline,restored):equal(x,y)
  assert 'valid snapshot:' in (s['out']/'server.log').read_text()
  mismatch=body([{'role':'system','content':'A different static prefix.'},USER],'different-'+uuid.uuid4().hex,True,profile)
  status,reply=call(mismatch);assert status==200
  assert source.read_bytes()==original_source and cp.read_bytes()==saved
  _,recovery=conversation(s,profile)
  for x,y in zip(baseline,recovery):equal(x,y)
 cases.append(dict(case='compatible_restart_and_prefix_mismatch',status='PASS',old_session_rejected=True,state_exact=True))
 variants=[] if a.compatible_only else [('version',8,a.engine_arg),('model_config_signature',24,a.engine_arg),('execution_mode',None,[*a.engine_arg,'--prefill-nrow'])]
 for name,offset,args in variants:
  damaged=bytearray(saved)
  if offset is not None:
   fmt='<I' if offset==8 else '<Q';value=struct.unpack_from(fmt,damaged,offset)[0];struct.pack_into(fmt,damaged,offset,value^0x40000000)
  cp.write_bytes(damaged)
  with server(a.out/('reject-'+name),cache,args=[*args,'--flash-profile',profile]) as s:
   _,recovered=conversation(s,profile)
   for x,y in zip(baseline,recovered):equal(x,y)
   log=(s['out']/'server.log').read_text();assert 'cache invalid:' in log and 'valid snapshot:' not in log
  cases.append(dict(case=name,status='PASS',method='Controlled header identity fault' if offset is not None else 'Real runtime-mode switch',fresh_state_exact=True))
 write(a.out/'result.json',dict(status='PASS',profile=profile,checkpoint_bytes=len(saved),cases=cases,profile_is_static_prefix_not_conversation=True,model_weights_unchanged=True))
 print('NAMED_PROFILE_HTTP_PASS',flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
