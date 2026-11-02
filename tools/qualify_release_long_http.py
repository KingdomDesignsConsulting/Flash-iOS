#!/usr/bin/env python3
"""Long HTTP resident execution vs independent scalar replay at observed points.
Requires the opt-in extended, sparse diagnostic build. No template changes.
"""
import argparse,threading,urllib.request,urllib.error,sys
ACTIVE_OUT=None
from experiment_session_token_exact import collect
from qualify_session_accumulation import wait_bounded_process
from session_gate_support import *
def request(b):
 req=urllib.request.Request('http://127.0.0.1:11243/v1/chat/completions',json.dumps(b).encode(),{'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=5400) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--corpus',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--reference-only',type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;write(a.out/'result.json',dict(status='RUNNING'));b=a.binary.resolve();records=[];responses=[];budget=[]
 if a.reference_only:
  previous=load(a.reference_only);assert previous['binary_sha256']==sha(b);records=previous['traces'];responses=previous['responses']
 else:
  # Select the complete native-rendered 16K history, not a truncated ID prefix.
  corpus=a.corpus.resolve().parent;source=None
  for i in range(16):
   ip=corpus/f'long-16384-{i}-input.json';rp=corpus/f'long-16384-{i}-render.json'
   if rp.exists() and load(rp)['cases'][0]['count']==16384:source=load(ip)['cases'][0];break
  assert source
  first=source['messages'];first[0]=dict(first[0],content=first[0]['content']+' Retain the identifier STATE-73941 for this conversation.');first[-1]=dict(first[-1],content=first[-1]['content']+'\nReply exactly READY.')
  monitor_thread=None
  try:
   with server(a.out/'server',args=['--prefill-nrow'],binary=b,env_extra={'FLASH_HTTP_QUALIFICATION':'1','FLASH_TRACE_GPU_KV_BOUNDARY':'1'}) as s:
    def monitor_server():
     code,peak,reason=wait_bounded_process(s['process'],7200,16*1024**3,host_free_floor=15)
     item=dict(exit=code,observed_rss_bytes=peak,stop_reason=reason);budget.append(item);write(a.out/'server-budget.json',item)
    monitor_thread=threading.Thread(target=monitor_server,daemon=True);monitor_thread.start()
    manifest=waitfile(s['trace']/'server.json');assert manifest['limit']==32768 and manifest['gpu_kv_capacity']==32768
    sid='long-'+uuid.uuid4().hex
    for n,messages in enumerate([first,[FOLLOW],[FOLLOW]]):
     req=body(messages,sid,n==0);req['max_tokens']=24
     if n==0:
      code,counted=request(dict(req,flash_qual_count_only=True));assert code==200 and 16384<=counted['context_tokens']<32000
     start=time.monotonic();code,reply=request(req);wall=(time.monotonic()-start)*1000;assert code==200 and not reply.get('session_invalidated'),(code,reply)
     _,prompt=collect(s['trace'],{},reply['id'],req['flash_trace_id'],'prompt');_,generated=collect(s['trace'],{},reply['id'],req['flash_trace_id'],'generated');st=state(s,req)
     assert st['accepted'] and not st['failed'] and st['history_complete'] and st['end_position']==len(st['effective_token_ids'])
     assert st['steps'][-1]['position']==st['end_position'] and generated['end_pos']==st['end_position']
     assert all(x['kv_lengths_match'] and not any(c['nonfinite'] for c in x['components']) for x in st['steps'])
     assert bool(reply['flash_timings']['session_reused'])==(n>0)
     records.append(dict(state=st,prompt=prompt,generated=generated,request_wall_ms=wall));responses.append(reply)
     write(a.out/'http-records.json',dict(binary_sha256=sha(b),traces=records,responses=responses));print('LONG_HTTP_TURN',stamp(),n,'position',st['end_position'],'observations',len(st['steps']),flush=True)
     if n==0:assert any('batch_rows' in point for point in st['steps']),'No actual N128 slab observed'
     if n:assert 'STATE-73941' in reply['choices'][0]['message'].get('content',''),('identifier recall',n,reply['choices'][0]['message'])
  finally:
   if monitor_thread:monitor_thread.join(timeout=20)
  assert budget and budget[0]['stop_reason'] is None,budget
 expected={};expected_parts={}
 for rec in records:
  for point in rec['state']['steps']:
   key=str(point['position']);assert key not in expected or expected[key]==point['digest'],'Resident boundary divergence'
   expected[key]=point['digest'];expected_parts[key]=point
 ids=records[-1]['state']['effective_token_ids'];assert 16384<len(ids)<32768 and str(len(ids)) in expected
 f=a.out/'replay.json';write(f,dict(token_ids=ids,expected_digests=expected));control=a.out/'control';control.mkdir();gate()
 env=dict(os.environ,FLASH_FE027_NUMERICS='63',FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(f));cmd=[str(b),'--model',MODEL,'--tiered','--no-prefill-nrow'];print('LONG_HTTP_CONTROL_START',stamp(),'tokens',len(ids),'COMMAND',json.dumps(cmd),flush=True)
 with (control/'engine.log').open('w') as log:
  proc=subprocess.Popen(cmd,cwd=b.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  code,peak,reason=wait_bounded_process(proc,7200,16*1024**3,host_free_floor=15)
 print('LONG_HTTP_CONTROL_STOP',stamp(),'exit',code,flush=True)
 result=dict(status='PASS' if code==0 else 'FAIL',reference_exit=code,reference_stop_reason=reason,observed_reference_rss_bytes=peak,end_position=len(ids),candidate_observation_points=len(expected),resident_turns=len(records),binary_sha256=sha(b),comparison='Exact synchronized active KV/GDN/convolution fingerprints at actual completed slabs, selected scalar prefill points, final prefill, every decode/EOS and request boundary; no intermediate batch-state claims')
 if (control/'continuous-replay-state.json').exists():
  ref=load(control/'continuous-replay-state.json');points={str(x['position']):x for x in ref['steps']};bad=[k for k,v in expected.items() if k not in points or points[k].get('digest')!=v]
  result['exact_shared_observations']=not bad
  if bad:result.update(status='FAIL',first_failed_observed_position=min(map(int,bad)))
  else:assert ref['end_position']==len(ids) and ref['accepted']
 else:result['exact_shared_observations']=False
 write(a.out/'result.json',result);return 0 if result['status']=='PASS' else 3
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   budget=load(ACTIVE_OUT/'server-budget.json') if (ACTIVE_OUT/'server-budget.json').exists() else {}
   write(ACTIVE_OUT/'result.json',dict(status='BLOCKED' if budget.get('stop_reason') else 'FAIL',error_type=type(error).__name__,error=str(error),server_budget=budget))
  raise
