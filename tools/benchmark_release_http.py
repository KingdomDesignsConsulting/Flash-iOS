#!/usr/bin/env python3
"""Balanced isolated HTTP performance; never a numerical qualification oracle."""
import argparse,statistics,threading
from session_gate_support import *
from qualify_session_accumulation import wait_bounded_process
from build_release_corpus import TECH


def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--control',required=True,type=P);p.add_argument('--candidate',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out
 modes=[('ordinary',a.control,0,True),('mask63',a.candidate,63,True),('scalar',a.control,0,False)];rows=[]
 report=dict(status='RUNNING',started=stamp(),rows=rows,runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),scope='Fresh-process first-request vs same-process warm execution, no OS page-cache purge; 64-token maximum decode, resident follow-up; three balanced process trials per path')
 write(a.out/'result.json',report)
 for trial in range(3):
  for name,binary,mask,nrow in modes[trial:]+modes[:trial]:
   output=a.out/f'{trial}-{name}';budget=[];thread=None
   with server(output,binary=binary.resolve(),args=['--prefill-nrow' if nrow else '--no-prefill-nrow'],env_extra={'FLASH_FE027_NUMERICS':str(mask)},diagnostic_trace=False) as s:
    def monitor():
     code,peak,reason=wait_bounded_process(s['process'],2400,16*1024**3,host_free_floor=15)
     budget.append(dict(exit=code,observed_native_rss_bytes=peak,stop_reason=reason))
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    cases=[]
    for label,repeats in [('cold_1k',16),('warm_1k',16),('warm_4k',62)]:
     sid='perf-'+uuid.uuid4().hex
     messages=[SYS,dict(role='user',content=TECH*repeats+'\nReturn consecutive integers separated by spaces, starting at 1. Continue until stopped.')]
     payload=dict(model='qwen3.5',messages=messages,session_id=sid,flash_session_create=True,temperature=0,seed=73941,reasoning_effort='off',stream=True,stream_options=dict(include_usage=True),max_tokens=64)
     result=stream_request(payload);assert not result['timings']['session_reused'];cases.append(dict(label=label,request=payload,**result))
     print('HTTP_BENCH_CASE',stamp(),trial,name,label,result['timings']['context_tokens'],'tokens',round(result['wall_ms'],1),'ms',flush=True)
    follow=dict(model='qwen3.5',messages=[dict(role='user',content='Reply exactly READY.')],session_id=sid,temperature=0,seed=73941,reasoning_effort='off',stream=True,stream_options=dict(include_usage=True),max_tokens=16)
    result=stream_request(follow);assert result['timings']['session_reused'] and 'READY' in result['visible'];cases.append(dict(label='resident_4k',request=follow,**result));write(output/'http-records.json',dict(cases=cases))
   thread.join(timeout=20);assert budget and budget[0]['stop_reason'] is None,budget
   post=gate()
   row=dict(trial=trial,mode=name,binary_sha256=sha(binary),post_gpu=post,budget=budget[0],cases=[{k:v for k,v in case.items() if k not in ['request','visible','events']} for case in cases]);rows.append(row);write(a.out/'result.json',report)
 summaries={}
 for mode,_,_,_ in modes:
  summaries[mode]={}
  for label in ['cold_1k','warm_1k','warm_4k','resident_4k']:
   samples=[case for row in rows if row['mode']==mode for case in row['cases'] if case['label']==label];metrics={}
   for field in ['wall_ms','wire_ttft_ms']:
    values=[x[field] for x in samples];metrics[field]=dict(n=len(values),median=statistics.median(values),min=min(values),max=max(values))
   for field in ['prefill_ms','prefill_tokens_per_second','decode_ms','decode_tokens_per_second','generated_tokens','context_tokens','cached_prefix_tokens','prefill_tokens']:
    values=[x['timings'][field] for x in samples];metrics[field]=dict(n=len(values),median=statistics.median(values),min=min(values),max=max(values))
   summaries[mode][label]=metrics
 report.update(status='COMPLETED_EXPLORATORY',ended=stamp(),summary=summaries);write(a.out/'result.json',report);return 0
ACTIVE_OUT=None
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   file=ACTIVE_OUT/'result.json';report=load(file) if file.exists() else {};report.update(status='FAIL',error_type=type(error).__name__,error=str(error));write(file,report)
  raise
