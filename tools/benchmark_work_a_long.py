#!/usr/bin/env python3
"""Balanced matched native-rendered cold/warm HTTP long-prefill timings.
No state-hash observer in timed requests. Charged footprint is not unified total.
"""
import argparse,re,signal,statistics,threading
from session_gate_support import *
from work_a_manifest import verify_bound_build
from qualify_session_accumulation import wait_bounded_process,host_free_percent
ACTIVE_OUT=None

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['control','candidate','manifest','variants','native_gate','render_input','render_output','probe','out']:p.add_argument('--'+key.replace('_','-'),required=True,type=P)
 p.add_argument('--max-seconds',type=int,default=21600);p.add_argument('--count',type=int,choices=[16384,32768],required=True);p.add_argument('--repeats',type=int,choices=[1,2,3],default=3);p.add_argument('--start-round',type=int,default=0);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;assert 300<=a.max_seconds<=43200;deadline=time.monotonic()+a.max_seconds
 verify_bound_build(a.manifest,a.control,a.native_gate);verify_bound_build(a.manifest,a.candidate,a.native_gate);manifest=load(a.manifest);variants=load(a.variants);assert variants['release_manifest_sha256']==sha(a.manifest)
 for name,digest in manifest['source_sha256'].items():assert sha(REPO/name)==digest,'Frozen source changed'
 for b in [a.control,a.candidate]:assert sha(b)==variants['variants'][b.name]['sha256']
 source=load(a.render_input)['cases'][0];gold=load(a.render_output)['cases'][0];assert len(gold['token_ids'])==a.count and not source.get('thinking',False)
 modes=[('ordinary',a.control,0,True),('mask63',a.candidate,63,True),('scalar',a.control,0,False)];rows=[];report=dict(status='RUNNING',started=stamp(),release_manifest_sha256=sha(a.manifest),runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),input_sha256=sha(a.render_input),rendered_ids_sha256=sha(a.render_output),count=a.count,repeats=a.repeats,rows=rows,cache_scope='Fresh process first-request then same-process repeat; same IDs/cache settings, no OS-page-cache purge; system startup may warm experts; no full-binary cache invalidation',attention_latency_scope='Existing host wall-phase aggregates, not GPU timestamp counters');write(a.out/'result.json',report)
 for trial in range(a.start_round,a.start_round+a.repeats):
  for name,binary,mask,nrow in modes[trial%3:]+modes[:trial%3]:
   assert time.monotonic()+300<deadline,'PHASE_BUDGET_NO_NEW_MODEL';free=host_free_percent();assert free is not None and free>=35,'HOST_MEMORY_LAUNCH_BLOCKED'
   output=a.out/f'{trial}-{name}';budget=[];samples=[];observer_errors=[];stop=threading.Event();threads=[]
   with server(output,binary=binary.resolve(),args=['--prefill-nrow' if nrow else '--no-prefill-nrow'],env_extra={'FLASH_FE027_NUMERICS':str(mask),'FLASH_HTTP_QUALIFICATION':'1','FLASH_TRACE_GPU_KV_BOUNDARY':'1'},diagnostic_trace=False) as s:
    def watch_budget():
     code,peak,reason=wait_bounded_process(s['process'],min(10800 if a.count==32768 else 7200,max(1,int(deadline-time.monotonic()))),16*1024**3,host_free_floor=15);budget.append(dict(exit=code,peak_rss_bytes=peak,stop_reason=reason))
    def observe():
     with (output/'memory-samples.jsonl').open('x') as log:
      while not stop.is_set():
       try:
        raw=subprocess.run([str(a.probe.resolve()),str(s['pid'])],capture_output=True,text=True,timeout=5)
        if raw.returncode:
         if s['process'].poll() is not None:break
         raise RuntimeError('Physical footprint monitor failed')
        item=dict(at=stamp(),**json.loads(raw.stdout));assert item['start_abstime']>0;item['gpu_percent']=gpu();samples.append(item);log.write(json.dumps(item)+'\n');log.flush()
       except Exception as error:
        observer_errors.append(str(error));os.killpg(s['pid'],signal.SIGTERM);break
       stop.wait(1)
    for target in [watch_budget,observe]:
     thread=threading.Thread(target=target,daemon=True);thread.start();threads.append(thread)
    cases=[]
    try:
     for label in ['cold','warm']:
      sid='long-perf-'+uuid.uuid4().hex;request=dict(model='qwen3.5',messages=source['messages'],session_id=sid,flash_session_create=True,temperature=0,seed=73941,reasoning_effort='off',max_tokens=32,stream=True,stream_options=dict(include_usage=True))
      started=stamp();result=stream_request(request,timeout=7000);assert result['timings']['context_tokens']==a.count
      # Explicit observer returns allocation/length metadata without advancing state.
      code,memory=call(dict(model='qwen3.5',messages=[dict(role='user',content='Reply exactly READY.')],session_id=sid,max_tokens=1,reasoning_effort='off',flash_qual_count_only=True));assert code==200 and memory['session_reused'];assert len(memory['kv_lengths'])==10 and all(x==memory['resident_pos'] for x in memory['kv_lengths'].values())
      cases.append(dict(label=label,started=started,ended=stamp(),result=result,allocation=memory));write(output/'http-records.json',dict(cases=cases));print('LONG_PERF_CASE',stamp(),trial,name,label,'prefill_ms',round(result['timings']['prefill_ms'],1),'generated',result['timings']['generated_tokens'],flush=True)
    finally:stop.set()
   for thread in threads:thread.join(20)
   assert budget and budget[0]['stop_reason'] is None and not observer_errors and samples,(budget,observer_errors)
   text=(output/'server.log').read_text();phases=[]
   for line in text.splitlines():
    if line.startswith('[prefill-nrow-profile'):
     phases.append({k:float(v) for k,v in re.findall(r'(\w+)=([\d.]+)',line)})
   routes=[dict(length=int(n),layer=int(l),cap=int(c),backend=b,route=r) for n,l,c,b,r in re.findall(r'\[gpu-kv-boundary\] seq=(\d+) layer=(\d+) cap=(\d+) backend=(\w+) route=(\S+)',text)]
   post=gate();row=dict(trial=trial,mode=name,binary_sha256=sha(binary),post_gpu=post,host_free_before=free,budget=budget[0],memory=dict(samples=len(samples),observed_peak_physical_bytes=max(x['physical_bytes'] for x in samples),lifetime_peak_physical_bytes=max(x['peak_physical_bytes'] for x in samples),sampled_peak_rss_bytes=max(x['rss_bytes'] for x in samples)),cases=[dict(label=x['label'],started=x['started'],ended=x['ended'],wall_ms=x['result']['wall_ms'],wire_ttft_ms=x['result']['wire_ttft_ms'],timings=x['result']['timings'],usage=x['result']['usage'],allocation=x['allocation']) for x in cases],nrow_host_phase_records=phases,boundary_routes=routes,expert_cache_hit_counters_available=False);rows.append(row);write(a.out/'result.json',report)
 summaries={}
 for mode,_,_,_ in modes:
  summaries[mode]={}
  for label in ['cold','warm']:
   selected=[c for row in rows if row['mode']==mode for c in row['cases'] if c['label']==label];metrics={}
   for field in ['prefill_ms','prefill_tokens_per_second','generated_tokens','decode_ms','decode_tokens_per_second','cached_prefix_tokens','prefill_tokens']:
    xs=[c['timings'][field] for c in selected];metrics[field]=dict(n=len(xs),median=statistics.median(xs),min=min(xs),max=max(xs),stdev=statistics.stdev(xs) if len(xs)>1 else None)
   for field in ['wall_ms','wire_ttft_ms']:
    xs=[c[field] for c in selected];metrics[field]=dict(n=len(xs),median=statistics.median(xs),min=min(xs),max=max(xs))
   summaries[mode][label]=metrics
 report.update(status='COMPLETED_EXPLORATORY',ended=stamp(),summary=summaries,confidence='Single process/path: variability NOT MEASURED' if a.repeats==1 else 'Exploratory, launch/post GPU gated; during-run contention not separable from own GPU activity');write(a.out/'result.json',report);return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   file=ACTIVE_OUT/'result.json';report=load(file) if file.exists() else {};report.update(status='STOPPED',error_type=type(error).__name__,error=str(error),ended=stamp());write(file,report)
  raise
