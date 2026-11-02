#!/usr/bin/env python3
"""Repeated HTTP prefill/decode vs fresh scalar histories; no template edits.
Default reproduces the two stateless SDK requests that exposed orphan prefetch.
--resident --turns 3 additionally crosses batched continuation boundaries.
Raw token histories remain in the requested private output directory.
"""
import argparse,threading
from session_gate_support import *
from qualify_session_accumulation import wait_bounded_process
ACTIVE_OUT=None

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--resident',action='store_true');p.add_argument('--turns',type=int,default=2,choices=[2,3]);p.add_argument('--no-expert-prefetch',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;b=a.binary.resolve();write(a.out/'result.json',dict(status='RUNNING'));records=[];budget=[];messages=[SYS,dict(role='user',content='Context:'+' x'*128+'\nReply exactly ADAPTER_73941.')];sid='phase-'+uuid.uuid4().hex
 flags=['--prefill-nrow']+(['--no-expert-prefetch'] if a.no_expert_prefetch else [])
 with server(a.out/'server',binary=b,args=flags,env_extra={'FLASH_FE027_NUMERICS':'63'}) as s:
  def monitor():
   code,peak,reason=wait_bounded_process(s['process'],300,16*1024**3,host_free_floor=15);budget.append(dict(exit=code,observed_rss_bytes=peak,stop_reason=reason))
  thread=threading.Thread(target=monitor,daemon=True);thread.start()
  for turn in range(a.turns):
   if turn:
    user=dict(role='user',content=('Additional context:'+' y'*128+'\nReply exactly READY.') if a.resident else 'Reply exactly ADAPTER_FOLLOWUP_73941.')
    if a.resident:messages=[user]
    else:messages=messages+[dict(role='assistant',content=records[-1]['response']['visible']),user]
   request=dict(model='qwen3.5',messages=messages,temperature=0,max_tokens=256,stream=True,stream_options=dict(include_usage=True),flash_trace_id='prefetch-phase-'+str(turn))
   if a.resident:
    request['session_id']=sid
    if not turn:request['flash_session_create']=True
   response=stream_request(request,timeout=240);st=state(s,request);assert st['accepted'] and st['history_complete'] and not st['failed'];assert st['end_position']==len(st['effective_token_ids'])<=512
   assert st['steps'][-1]['position']==st['end_position'] and any('batch_rows' in point for point in st['steps'])
   assert all(point['kv_lengths_match'] and not any(part['nonfinite'] for part in point['components']) for point in st['steps'])
   assert response['timings']['session_reused']==bool(a.resident and turn)
   if not turn:assert response['timings']['generated_tokens']>=4,'Need decode history to prime temporal prefetch'
   records.append(dict(state=st,response=response,request=request));write(a.out/'records.json',dict(records=records));print('PREFETCH_PHASE_TURN',stamp(),turn,st['end_position'],flush=True)
 thread.join(timeout=20);assert budget and budget[0]['stop_reason'] is None
 groups=[records] if a.resident else [[record] for record in records];comparisons=[]
 for index,group in enumerate(groups):
  trace=a.out/f'control-{index}';trace.mkdir();ids=group[-1]['state']['effective_token_ids'];expected={}
  for record in group:
   if a.resident:assert ids[:len(record['state']['effective_token_ids'])]==record['state']['effective_token_ids']
   for point in record['state']['steps']:
    key=str(point['position']);assert key not in expected or expected[key]==point['digest'],'Resident boundary changed';expected[key]=point['digest']
  source=trace/'replay.json';write(source,dict(token_ids=ids,expected_digests=expected));pre=gate();cmd=[str(b),'--model',MODEL,'--tiered','--no-prefill-nrow'];env=dict(os.environ,FLASH_FE027_NUMERICS='63',FLASH_SESSION_TOKEN_TRACE_DIR=str(trace),FLASH_SESSION_REPLAY_INPUT=str(source));print('PREFETCH_PHASE_REFERENCE_START',stamp(),index,'COMMAND',json.dumps(cmd),flush=True)
  with (trace/'engine.log').open('w') as log:
   proc=subprocess.Popen(cmd,cwd=b.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);code,peak,reason=wait_bounded_process(proc,240,16*1024**3,host_free_floor=15)
  print('PREFETCH_PHASE_REFERENCE_STOP',stamp(),index,'exit',code,flush=True);row=dict(index=index,exit=code,stop_reason=reason,pre_gpu=pre,observed_rss_bytes=peak,expected_positions=len(expected),input_tokens=len(ids));comparisons.append(row)
  if (trace/'continuous-replay-state.json').exists():
   reference=load(trace/'continuous-replay-state.json');points={str(point['position']):point['digest'] for point in reference['steps']};bad=[int(key) for key,digest in expected.items() if points.get(key)!=digest];row['exact']=not bad
   if bad:row['first_failed_observed_position']=min(bad)
   if code==0:assert reference['accepted'] and reference['end_position']==len(ids) and not bad
  if code or not row.get('exact'):break
 passed=len(comparisons)==len(groups) and all(row['exit']==0 and row['exact'] for row in comparisons)
 result=dict(status='PASS' if passed else 'FAIL',resident=a.resident,turns=len(records),prefetch_enabled=not a.no_expert_prefetch,end_positions=[record['state']['end_position'] for record in records],candidate_observations=[len(record['state']['steps']) for record in records],references=comparisons,server_budget=budget[0],binary_sha256=sha(b),runner_sha256=sha(P(__file__)),state_comparison='Exact fingerprints at observed completed slabs/tails/decode/boundaries; independent scalar from zero',model_followup_literal_honored='ADAPTER_FOLLOWUP_73941' in records[-1]['response']['visible'] if not a.resident else None)
 write(a.out/'result.json',result);return 0 if passed else 3
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:write(ACTIVE_OUT/'result.json',dict(status='FAIL',error_type=type(error).__name__,error=str(error)))
  raise
