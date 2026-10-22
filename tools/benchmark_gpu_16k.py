#!/usr/bin/env python3
"""Matched checkpoint-assisted GPU-KV performance runner; fresh output required."""
import argparse,datetime,json,os,pathlib,re,statistics,subprocess,time,threading
from qualify_gpu_16k import sha,MODEL
P=pathlib.Path
LOW=P('/Users/Shared/Main Hard Drive/AI Storage/Apps/gqa-qual-20261018/cache/explanation')
UP=P('/Users/knagel/My Drive/Flash-iOS/Testing/gpu-16k-attention/boundary-16384/seed-cache/explanation/16382/anchor.state')
def samples(n=3):
 vals=[]
 for i in range(n):
  r=subprocess.run(['ioreg','-r','-c','AGXAccelerator','-d','1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=10)
  found=re.search(r'"Device Utilization %"\s*=\s*(\d+)',r.stdout)
  vals.append(int(found.group(1)) if found else None)
  if i+1<n:time.sleep(.25)
 return vals
def idle(vals):return all(x is not None for x in vals) and statistics.median(vals)<=10 and max(vals)<30
def stats(xs):
 xs=sorted(xs);n=len(xs)
 if not n:return None
 median=statistics.median(xs)
 return dict(n=n,median=median,min=xs[0],max=xs[-1],p10=xs[int((n-1)*.1)],p90=xs[int((n-1)*.9)],cv=statistics.pstdev(xs)/median if median else 0)
def parse(log):
 groups={}
 for line in log.read_text(errors='replace').splitlines():
  m=re.match(r'\[kv-perf-([^]]+)\] (\{.*\})',line)
  if m:groups.setdefault(m[1],[]).append(json.loads(m[2]))
 if '[kv-perf] RESULT=PASS' not in log.read_text(errors='replace'):raise RuntimeError('Incomplete benchmark '+str(log))
 return groups
def summarize(records):
 table=[];boundary=[]
 for pos in sorted(set(r['pos'] for r in records)):
  for arm in ['8k','16k','lazy16k','lazy32k']:
   runs=[r for r in records if r['pos']==pos and r['arm']==arm and r['accepted']]
   if not runs:continue
   selected=pos+2 if pos in (16382,24574,32766) else pos+1
   steps=[s for r in runs for s in r['data']['step'] if s['observer']==0 and s['len']==selected]
   prof=[s for r in runs for s in r['data']['step'] if s['observer']==1 and s['len']==selected]
   pre=[p for r in runs for p in r['data']['prefill']]
   timing=stats([s['wall_ms'] for s in steps]);attngpu=stats([s['attention_gpu_ms']/10 for s in prof]);attncpu=stats([s['attention_cpu_ms']/10 for s in prof])
   row=dict(context=selected,arm=arm,token_ms=timing,decode_tps=1000/timing['median'],
    attention_gpu_ms_per_layer=attngpu,attention_cpu_ms_per_layer=attncpu,full_layer_host_ms=stats([s['full_layer_host_ms']/10 for s in steps]),
    physical_bytes=stats([s['physical_bytes'] for s in steps]),peak_physical_bytes=max(s['peak_physical_bytes'] for s in steps),peak_rss_bytes=max(s['peak_rss_bytes'] for s in steps),
    metal_allocated_bytes=stats([r['data']['meta'][0]['metal_allocated_bytes'] for r in runs]),suffix_prefill_tps=stats([p['suffix_tokens']*1000/p['prefill_ms'] for p in pre]),
    checkpoint_assisted_ttft_ms=stats([p['ttft_ms'] for p in pre]),restore_ms=stats([p['restore_ms'] for p in pre]),gpu_layers=steps[0]['gpu_layers'],
    confidence='moderate' if timing['cv']<=.05 and (attngpu if steps[0]['gpu_layers'] else attncpu)['cv']<=.05 and len(runs)>=2 else 'low: variable or single process')
   table.append(row)
   for length in (8192,8193,16384,16385,24576,32768,32769):
    ss=[s for r in runs for s in r['data']['step'] if s['observer']==0 and s['len']==length]
    pp=[s for r in runs for s in r['data']['step'] if s['observer']==1 and s['len']==length]
    if ss:boundary.append(dict(length=length,arm=arm,wall_ms=stats([s['wall_ms'] for s in ss]),gpu_layers=ss[0]['gpu_layers'],attention_gpu_ms=stats([s['attention_gpu_ms']/10 for s in pp]),attention_cpu_ms=stats([s['attention_cpu_ms']/10 for s in pp])))
 return dict(table=table,boundaries=boundary,excluded_runs=[{k:r[k] for k in ('arm','pos','round','pre_gpu','post_gpu','accepted')} for r in records if not r['accepted']])
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=P,required=True);ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1]);ap.add_argument('--anchor-root',type=P);ap.add_argument('--contexts',default='2047,4095,8191,16382');ap.add_argument('--rounds',type=int,default=2);ap.add_argument('--repeats',type=int,default=3);ap.add_argument('--steps',type=int,default=4);ap.add_argument('--suffix',type=int,default=8);ap.add_argument('--arms',default='8k,16k,lazy16k');ap.add_argument('--idle-wait',type=int,default=60);ap.add_argument('--post-settle',type=float,default=2.0);ap.add_argument('--build',action='store_true');ap.add_argument('--exploratory',action='store_true',help='Execute during contention but exclude timings from accepted results');a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);records=[]
 if a.build:
  with (a.out/'build.log').open('w') as f:subprocess.run(['make','-C','metal_infer','gpu-kv-performance']+(['gpu-kv-performance-32k'] if 'lazy32k' in a.arms.split(',') else []),cwd=a.repo,stdout=f,stderr=subprocess.STDOUT,check=True)
 manifest={'base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip(),'started':datetime.datetime.now().astimezone().isoformat(),'driver_sha256':sha(P(__file__)),
  'sources':{str(p.relative_to(a.repo)):sha(p) for p in (a.repo/'metal_infer').iterdir() if p.suffix in ('.m','.inc','.metal','.h') or p.name=='Makefile'},
  'machine':subprocess.check_output(['sw_vers'],text=True).strip(),
  'settings':{'rounds':a.rounds,'repeats':a.repeats,'steps':a.steps,'suffix':a.suffix,'post_settle_seconds':a.post_settle,'expert_cache':'disabled; OS pages warmed by an untimed pass for each mode','cold_prefill':'not measured; suffix prefill from exact saved state','idle_gate':'median<=10%, maximum<30% before and after process; during-run utilization includes own work'},'runs':records}
 for round_id in range(a.rounds):
  for ci,pos in enumerate(map(int,a.contexts.split(','))):
   fixture=(a.anchor_root/str(pos)/'anchor.state') if a.anchor_root and (a.anchor_root/str(pos)/'anchor.state').exists() else (UP if pos==16382 else LOW/str(pos)/'anchor.state')
   arms=a.arms.split(',');offset=(round_id+ci)%len(arms);arms=arms[offset:]+arms[:offset]
   if round_id%2:arms.reverse()
   for arm in arms:
    pre=samples();deadline=time.monotonic()+a.idle_wait
    while not a.exploratory and not idle(pre) and time.monotonic()<deadline:
     print('WAIT GPU',pre,flush=True);time.sleep(2);pre=samples()
    if not idle(pre) and not a.exploratory:
     (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2));raise RuntimeError('GPU contention: bounded idle wait expired')
    name=f'round{round_id}-{pos}-{arm}';log=a.out/(name+'.log')
    binary=a.repo/'metal_infer'/('infer-perf-'+arm)
    cmd=[str(binary),'--model',MODEL,'--tiered','--no-malloc-cache','--no-expert-prefetch']
    env=os.environ.copy();env.update(FLASH_QUAL_ANCHOR=str(fixture),FLASH_QUAL_HIDDEN=str(fixture.with_name('hidden.bin')),FLASH_QUAL_POS=str(pos),FLASH_PERF_RUN='1',FLASH_PERF_REPEATS=str(a.repeats),FLASH_PERF_STEPS=str(a.steps),FLASH_PERF_SUFFIX=str(a.suffix))
    during=[];done=threading.Event()
    def watch():
     while not done.wait(2):during.extend(samples(1))
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    print('RUN',name,'idle',pre,flush=True)
    try:
     with log.open('w') as f:r=subprocess.run(cmd,cwd=a.repo/'metal_infer',env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=300)
    finally:done.set();thread.join(timeout=10)
    time.sleep(a.post_settle);post=samples()
    if r.returncode:raise RuntimeError(f'{name} exit={r.returncode}; see {log}')
    data=parse(log);cap=8192 if arm=='8k' else (32768 if arm=='lazy32k' else 16384)
    for row in data['step']:
     if row['gpu_layers']!=(10 if row['len']<=cap else 0):raise RuntimeError(f'Bad route {name} {row}')
     if row['observer']==1 and row['gpu_layers'] and (not data['meta'][0]['counters'] or row['attention_gpu_ms']<=0):raise RuntimeError(f'Missing GPU counter samples: {name}')
    accepted=idle(pre) and idle(post)
    record=dict(name=name,arm=arm,pos=pos,round=round_id,pre_gpu=pre,post_gpu=post,during_gpu= during,accepted=accepted,command=cmd,binary_sha256=sha(binary),fixture_sha256=sha(fixture),hidden_sha256=sha(fixture.with_name('hidden.bin')),data=data)
    records.append(record)
    # Sampling and expert routes must remain matched across arms and repeats.
    matched=[x for x in records if x['pos']==pos]
    for step in range(a.steps):
     ids={s['token'] for run in matched for s in run['data']['step'] if s['step']==step}
     if len(ids)!=1:raise RuntimeError(f'Token mismatch pos={pos} step={step}: {ids}')
    next_ids={p['next_token'] for run in matched for p in run['data']['prefill']}
    if len(next_ids)!=1:raise RuntimeError(f'Suffix token mismatch pos={pos}: {next_ids}')
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    summary=summarize(records);summary['exploratory']=summarize([{**x,'accepted':True} for x in records]);
    for row in summary['exploratory']['table']:row['confidence']='exploratory: contention or single-process screening; not a promotion result'
    (a.out/'results.json').write_text(json.dumps(summary,indent=2))
    print('DONE',name,'accepted',accepted,'post',post,'decode tps',data['decode'][0]['tokens_per_second'],flush=True)
 manifest['finished']=datetime.datetime.now().astimezone().isoformat();(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('COMPLETE',a.out,flush=True)
if __name__=='__main__':main()
