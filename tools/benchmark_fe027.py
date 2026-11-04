#!/usr/bin/env python3
"""Alternating fresh-process FE-027/control prefill timings; private logs/fixture.
Includes first N128 workspace setup, excludes loading and final scalar token.
Not a resident steady-state throughput or uncontended-GPU qualification claim.
"""
import argparse,json,os,pathlib,re,resource,signal,statistics,struct,subprocess,time
from run_session_state_mission import MODEL,gpu,stamp,sha
from qualify_session_accumulation import wait_bounded_process
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['control','candidate','fixture','out']:p.add_argument('--'+name,type=P,required=True)
 p.add_argument('--scalar-reference',type=P,help='Optional unchanged control binary with N128 disabled')
 p.add_argument('--timeout',type=int,default=180);p.add_argument('--max-rss-gib',type=float,default=16);p.add_argument('--decode-tokens',type=int,default=8);p.add_argument('--count',type=int,default=1025);p.add_argument('--repeats',type=int,default=3);p.add_argument('--candidate-numerics',type=int,choices=range(64),default=15);a=p.parse_args()
 assert a.count>128 and 2<=a.repeats<=5 and 1<=a.decode_tokens<=256 and 1<=a.timeout<=7200 and a.max_rss_gib>0;a.out.mkdir(parents=True,exist_ok=False)
 values=struct.unpack('<'+'I'*(a.fixture.stat().st_size//4),a.fixture.read_bytes());assert values[0]==len(values)-1 and a.count<=values[0]
 inp=a.out/'prompt.bin';inp.write_bytes(struct.pack('<I',a.count)+struct.pack('<'+'I'*a.count,*values[1:1+a.count]))
 rows=[];report=dict(started=stamp(),scope=__doc__,runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),fixture_sha256=sha(a.fixture),input_tokens=a.count,candidate_numerics=a.candidate_numerics,rows=rows)
 report['cache_scope']='Fresh-process expert caches and matched token IDs; OS page cache is not purged. Decode follows prefill. First N128 workspace/setup is included, not separately claimed as steady state.'
 modes=[('control',a.control,0),('candidate',a.candidate,a.candidate_numerics)]
 if a.scalar_reference:modes.append(('scalar',a.scalar_reference,0))
 for trial in range(a.repeats):
  order=(modes[trial%len(modes):]+modes[:trial%len(modes)])
  for label,binary,mask in order:
   stable=0;readings=[]
   for _ in range(60):
    g=gpu();readings.append(g);stable=stable+1 if g is not None and g<30 else 0
    if stable==3:break
    time.sleep(1)
   if stable<3:
    report.update(status='GPU_GATE_NOT_RUN',stopped_trial=trial,stopped_mode=label,pre_gpu=readings);(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError('GPU gate: no model launched')
   for port in [11241,11243]:assert not subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout
   binary=binary.resolve();cmd=[str(binary),'--model',MODEL,'--tiered','--no-prefill-nrow' if label=='scalar' else '--prefill-nrow','--prompt-tokens',str(inp),'--tokens',str(a.decode_tokens),'--temperature','0','--seed','73941']
   env=dict(os.environ,FLASH_FE027_NUMERICS=str(mask));env.pop('FLASH_SESSION_TOKEN_TRACE_DIR',None)
   log=a.out/f'{trial}-{label}.log';start=stamp();usage_before=resource.getrusage(resource.RUSAGE_CHILDREN);wall_start=time.perf_counter();print('BENCH_START',start,label,trial,flush=True)
   with log.open('w') as f:
    proc=subprocess.Popen(cmd,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    code,observed_rss,stop_reason=wait_bounded_process(proc,a.timeout,int(a.max_rss_gib*1024**3),host_free_floor=15)
   end=stamp();elapsed_wall_ms=(time.perf_counter()-wall_start)*1000;print('BENCH_STOP',end,label,trial,'exit',code,flush=True)
   if code!=0:
    report.update(status='EXECUTION_ERROR',failed_attempt=dict(trial=trial,mode=label,exit=code,stop_reason=stop_reason,observed_native_rss_bytes=observed_rss,started=start,ended=end,binary_sha256=sha(binary)));(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError('Bounded benchmark process failed: '+str(code))
   text=log.read_text();m=re.search(r'\[prefill\] (\d+)/(\d+) tokens: ([\d.]+) ms',text);assert m,'Missing prefill timing'
   row=dict(trial=trial,mode=label,started=start,ended=end,command=cmd,binary_sha256=sha(binary),pre_gpu=readings,prefill_tokens=int(m[1]),prompt_tokens=int(m[2]),prefill_ms=float(m[3]),reported_generated_ids=[int(x) for x in re.findall(r'\[gen \d+/\d+\] token_id=(\d+)',text)])
   row.update(process_wall_ms=elapsed_wall_ms,observed_native_rss_bytes=observed_rss,rss_limit_gib=a.max_rss_gib,stop_reason=stop_reason,requested_decode_tokens=a.decode_tokens)
   post=[];stable=0
   for _ in range(30):
    value=gpu();post.append(value);stable=stable+1 if value is not None and value<30 else 0
    if stable==3:break
    time.sleep(1)
   row.update(post_gpu=post,post_gpu_gate_passed=stable==3)
   if stable!=3:
    row['status']='GPU_CONTENTION_STOPPED';rows.append(row);report['status']='GPU_CONTENTION_STOPPED';(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');raise RuntimeError('Post-run GPU gate: timing is not an accepted measurement')
   usage_after=resource.getrusage(resource.RUSAGE_CHILDREN)
   row['child_resource_delta']={field:getattr(usage_after,field)-getattr(usage_before,field) for field in ['ru_utime','ru_stime','ru_minflt','ru_majflt','ru_inblock','ru_oublock']}
   ttft=re.search(r'TTFT:\s+([\d.]+) ms',text);generation=re.search(r'Generation:\s+([\d.]+) s \(([\d.]+) tok/s\)',text)
   if ttft:row['ttft_ms']=float(ttft[1])
   if generation:row.update(warm_decode_ms_rounded=float(generation[1])*1000,warm_decode_tokens_per_second=float(generation[2]))
   cache=re.search(r'Expert cache:\s+(?:malloc )?(\d+) hits, (\d+) misses .*?(\d+)/(\d+) entries used',text)
   row['expert_cache_stats']=dict(hits=int(cache[1]),misses=int(cache[2]),entries=int(cache[3]),capacity=int(cache[4])) if cache else None
   row['expert_cache_stats_available']=cache is not None
   row['prefill_tokens_per_second']=row['prefill_tokens']*1000/row['prefill_ms'];rows.append(row)
   (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 med={}
 for label,_,_ in modes:
  vals=[x['prefill_ms'] for x in rows if x['mode']==label];med[label]=dict(median_ms=statistics.median(vals),min_ms=min(vals),max_ms=max(vals),stdev_ms=statistics.stdev(vals))
  for field in ['process_wall_ms','ttft_ms','warm_decode_ms_rounded','warm_decode_tokens_per_second']:
   vals=[x[field] for x in rows if x['mode']==label and field in x]
   if vals:med[label][field]=dict(median=statistics.median(vals),min=min(vals),max=max(vals))
 report.update(ended=stamp(),status='COMPLETED_EXPLORATORY',summary=med,candidate_to_control_median_ratio=med['candidate']['median_ms']/med['control']['median_ms'],reported_decode_ids_match=len({tuple(x['reported_generated_ids']) for x in rows})==1,temperature=0,seed=73941)
 (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)
if __name__=='__main__':main()
