#!/usr/bin/env python3
"""Alternating fresh-process FE-027/control prefill timings; private logs/fixture.
Includes first N128 workspace setup, excludes loading and final scalar token.
Not a resident steady-state throughput or uncontended-GPU qualification claim.
"""
import argparse,json,os,pathlib,re,signal,statistics,struct,subprocess,time
from run_session_state_mission import MODEL,gpu,stamp,sha
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['control','candidate','fixture','out']:p.add_argument('--'+name,type=P,required=True)
 p.add_argument('--count',type=int,default=1025);p.add_argument('--repeats',type=int,default=3);a=p.parse_args()
 assert a.count>128 and 2<=a.repeats<=5;a.out.mkdir(parents=True,exist_ok=False)
 values=struct.unpack('<'+'I'*(a.fixture.stat().st_size//4),a.fixture.read_bytes());assert values[0]==len(values)-1 and a.count<=values[0]
 inp=a.out/'prompt.bin';inp.write_bytes(struct.pack('<I',a.count)+struct.pack('<'+'I'*a.count,*values[1:1+a.count]))
 rows=[];report=dict(started=stamp(),scope=__doc__,fixture_sha256=sha(a.fixture),input_tokens=a.count,rows=rows)
 for trial in range(a.repeats):
  for label,binary,mask in ([('control',a.control,0),('candidate',a.candidate,15)] if trial%2==0 else [('candidate',a.candidate,15),('control',a.control,0)]):
   stable=0;readings=[]
   for _ in range(60):
    g=gpu();readings.append(g);stable=stable+1 if g is not None and g<30 else 0
    if stable==3:break
    time.sleep(1)
   if stable<3:raise RuntimeError('GPU gate: no model launched')
   for port in [11241,11243]:assert not subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout
   binary=binary.resolve();cmd=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow','--prompt-tokens',str(inp),'--tokens','8']
   env=dict(os.environ,FLASH_FE027_NUMERICS=str(mask));env.pop('FLASH_SESSION_TOKEN_TRACE_DIR',None)
   log=a.out/f'{trial}-{label}.log';start=stamp();print('BENCH_START',start,label,trial,flush=True)
   with log.open('w') as f:
    proc=subprocess.Popen(cmd,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=proc.wait(timeout=180)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=15);raise
   end=stamp();print('BENCH_STOP',end,label,trial,'exit',code,flush=True);assert code==0
   text=log.read_text();m=re.search(r'\[prefill\] (\d+)/(\d+) tokens: ([\d.]+) ms',text);assert m,'Missing prefill timing'
   row=dict(trial=trial,mode=label,started=start,ended=end,command=cmd,binary_sha256=sha(binary),pre_gpu=readings,prefill_tokens=int(m[1]),prompt_tokens=int(m[2]),prefill_ms=float(m[3]),reported_generated_ids=[int(x) for x in re.findall(r'\[gen \d+/\d+\] token_id=(\d+)',text)])
   row['prefill_tokens_per_second']=row['prefill_tokens']*1000/row['prefill_ms'];rows.append(row)
   (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 med={}
 for label in ['control','candidate']:
  vals=[x['prefill_ms'] for x in rows if x['mode']==label];med[label]=dict(median_ms=statistics.median(vals),min_ms=min(vals),max_ms=max(vals))
 report.update(ended=stamp(),status='COMPLETED_EXPLORATORY',summary=med,candidate_to_control_median_ratio=med['candidate']['median_ms']/med['control']['median_ms'])
 (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)
if __name__=='__main__':main()
