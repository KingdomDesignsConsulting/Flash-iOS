#!/usr/bin/env python3
"""Private bounded N128/scalar oracle. Never launches overlapping models or servers."""
import argparse,json,os,pathlib,subprocess,time
from run_session_state_mission import gpu,stamp,sha,MODEL
P=pathlib.Path
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--history',type=P,required=True);p.add_argument('--out',type=P,required=True);p.add_argument('--count',type=int);p.add_argument('--starts',default='13');p.add_argument('--model',default=MODEL);a=p.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);repo=P(__file__).resolve().parents[1];binary=repo/'metal_infer/infer-session-state-experiment'
 history=json.loads(a.history.read_text());ids=history['traces'][-1]['state']['effective_token_ids'];count=a.count if a.count is not None else len(ids)
 assert 0<count<=len(ids) and count<=512
 starts=[int(n) for n in a.starts.split(',') if n];assert all(0<=n and n+128<=count for n in starts)
 for n,m in zip(starts,starts[1:]):assert m>=n+128
 inputfile=a.out/'input.json';inputfile.write_text(json.dumps(dict(token_ids=ids[:count],batch_starts=starts)))
 manifest=dict(started=stamp(),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),source_sha256={n:sha(repo/n) for n in ['metal_infer/infer.m','metal_infer/session_state_diag.inc','metal_infer/session_nrow_oracle.inc','metal_infer/prefill_nrow_grouped_async.inc']},binary_sha256=sha(binary),input_tokens=count,batch_starts=starts,history_source=str(a.history),pre_gpu=[],status='INCOMPLETE')
 stable=0
 for _ in range(10):
  value=gpu();manifest['pre_gpu'].append(value);stable=stable+1 if value is not None and value<30 else 0
  if stable==3:break
  time.sleep(1)
 if stable<3:
  manifest['status']='GPU_GATE_NOT_RUN';(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2));return 4
 # Any resident inference server consumes the same model memory; refuse overlap.
 for port in [11243]:
  assert not subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout,'Isolated server is running'
 command=[str(binary),'--model',a.model,'--tiered','--no-prefill-nrow'];manifest['command']=command
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(a.out),FLASH_SESSION_NROW_ORACLE_INPUT=str(inputfile))
 print('ORACLE_START',stamp(),flush=True)
 with (a.out/'oracle.log').open('w') as f:r=subprocess.run(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=300)
 print('ORACLE_STOP',stamp(),'exit',r.returncode,flush=True)
 manifest.update(ended=stamp(),exit=r.returncode,status='COMPLETED' if r.returncode==0 else 'FAIL');(a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 if (a.out/'nrow-oracle.json').exists():
  result=json.loads((a.out/'nrow-oracle.json').read_text())
  if r.returncode==0:
   bypos={row['position']:row['candidate_digest'] for row in result['rows']};bypos[0]=result['initial_digest'];linked=[]
   for trace in history['traces']:
    for row in trace['state']['steps']:
     if row['position']>count:continue
     assert bypos.get(row['position'])==row['digest'],('HTTP/native candidate mismatch',row['position'])
     linked.append(row['position'])
   controlfile=a.history.parent/'continuous/continuous-replay-state.json'
   ref={row['position']:row['reference_digest'] for row in result['rows']}
   if controlfile.exists():
    for row in json.loads(controlfile.read_text())['steps']:
     if row['position'] in ref:assert row['digest']==ref[row['position']],('scalar reference mismatch',row['position'])
   manifest['http_candidate_positions_exact']=sorted(set(linked));manifest['http_candidate_exact']=True
   (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  print(json.dumps({k:result[k] for k in ['status','bit_exact','completed_position','batches']}),flush=True)
 return r.returncode
if __name__=='__main__':raise SystemExit(main())
