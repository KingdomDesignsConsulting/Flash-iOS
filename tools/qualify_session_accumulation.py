#!/usr/bin/env python3
"""Private saved-token N128 accumulation, stop at first failed measured endpoint.
No HTTP workload or performance claim. One model process, bounded native oracle.
"""
import argparse,csv,hashlib,json,os,pathlib,resource,signal,struct,subprocess,time
from run_session_state_mission import MODEL,gpu,stamp,sha
P=pathlib.Path
FIXTURE='/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=P,required=True);p.add_argument('--fixture',type=P,default=P(FIXTURE));p.add_argument('--count',type=int,default=2057);p.add_argument('--full-final-slab',action='store_true');p.add_argument('--scalar-slab',type=int,action='append',default=[]);p.add_argument('--timeout',type=int,default=600);p.add_argument('--gpu-wait',type=int,default=10);p.add_argument('--binary',type=P);p.add_argument('--source-ref');p.add_argument('--operations',action='store_true');p.add_argument('--numerics',type=int,default=0);p.add_argument('--route-probe-layers',type=int,default=12);p.add_argument('--route-probe-start',type=int);a=p.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);raw=a.fixture.read_bytes();assert len(raw)%4==0
 values=list(struct.unpack('<'+'I'*(len(raw)//4),raw));assert values[0]==len(values)-1
 ids=values[1:];assert 0<a.count<=len(ids) and a.count<=32768
 assert not a.full_final_slab or a.count%128==0
 starts=list(range(0,(a.count//128 if a.full_final_slab else (a.count-1)//128)*128,128));assert all(x in starts for x in a.scalar_slab)
 for x in a.scalar_slab:starts.remove(x)
 payload=dict(token_ids=ids[:a.count],batch_starts=starts,scalar_slab_starts=a.scalar_slab)
 if a.route_probe_start is not None:
  assert 0<=a.route_probe_start and a.route_probe_start+128<=a.count and 1<=a.route_probe_layers<=40
  payload.update(route_probe_start=a.route_probe_start,route_probe_layers=a.route_probe_layers)
 inputfile=a.out/'input.json';inputfile.write_text(json.dumps(payload))
 repo=P(__file__).resolve().parents[1];binary=(a.binary or repo/'metal_infer/infer-session-state-experiment').resolve()
 report=dict(started=stamp(),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),source_sha256={n:(hashlib.sha256(subprocess.check_output(['git','show',a.source_ref+':'+n],cwd=repo)).hexdigest() if a.source_ref else sha(repo/n)) for n in ['metal_infer/infer.m','metal_infer/session_state_diag.inc','metal_infer/session_nrow_oracle.inc','metal_infer/warm_state_cache.inc','metal_infer/prefill_nrow_grouped_async.inc','metal_infer/Makefile']},binary_sha256=sha(binary),fixture=str(a.fixture),fixture_sha256=sha(a.fixture),fixture_tokens=len(ids),input_tokens=a.count,batch_starts=starts,scalar_slab_starts=a.scalar_slab,pre_gpu=[],status='INCOMPLETE',sampling='Completed slabs and scalar tail only; greedy deterministic, identical supplied IDs; not long HTTP qualification')
 for extra in ['metal_infer/fe027_alignment.inc','metal_infer/fe027_q4.inc','metal_infer/fe027_attention_reference.inc','metal_infer/fe027_full_attention_diag.inc']:
  if not a.source_ref and (repo/extra).exists():report['source_sha256'][extra]=sha(repo/extra)
 report['source_ref']=a.source_ref;report['numerics_mask']=a.numerics;report['full_final_slab']=a.full_final_slab
 stable=0
 for attempt in range(max(10,a.gpu_wait)):
  g=gpu();report['pre_gpu'].append(g);stable=stable+1 if g is not None and g<30 else 0
  if stable==3:break
  if attempt and attempt%30==0:print('GPU_WAIT',stamp(),'last',g,flush=True)
  time.sleep(1)
 if stable<3:report['status']='GPU_GATE_NOT_RUN';(a.out/'result.json').write_text(json.dumps(report,indent=2));return 4
 for port in [11241,11243]:
  if subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout:
   report.update(status='MODEL_PORT_BUSY_NOT_RUN',busy_port=port);(a.out/'result.json').write_text(json.dumps(report,indent=2));return 4
 command=[str(binary),'--model',MODEL,'--tiered','--no-prefill-nrow'];report['command']=command
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(a.out),FLASH_SESSION_NROW_ORACLE_INPUT=str(inputfile))
 if a.operations:env['FLASH_FE027_OPERATIONS']='1'
 if a.numerics:env['FLASH_FE027_NUMERICS']=str(a.numerics)
 print('ACCUMULATION_START',stamp(),'tokens',a.count,flush=True)
 with (a.out/'engine.log').open('w') as f:
  proc=subprocess.Popen(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=proc.wait(timeout=a.timeout)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=15);code=124
 print('ACCUMULATION_STOP',stamp(),'exit',code,flush=True)
 report.update(ended=stamp(),exit=code,peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,status='PASS' if code==0 else 'FAIL' if code==3 else 'EXECUTION_ERROR')
 native=a.out/'nrow-oracle.json'
 if native.exists():
  r=json.loads(native.read_text());rows=r['rows'];report.update(completed_position=r['completed_position'],batches=r['batches'],bit_exact=bool(r['bit_exact']))
  failures=[x for x in rows if not x['pass']]
  if failures:report['first_failure']=failures[0];report['last_passing_position']=max((x['position'] for x in rows if x['pass']),default=0)
  report['max_errors']={key:max((row[field]['max_abs'] if field else row['state_max_abs'] for row in rows),default=0) for key,field in [('state',None),('hidden','hidden'),('logits','logits')]}
  with (a.out/'error-curve.csv').open('w') as f:
   writer=csv.writer(f);writer.writerow(['position','step_rows','batch_rows','state_max_abs','hidden_max_abs','logits_max_abs','greedy_equal','finite','kv_lengths_and_mirrors','pass'])
   for x in rows:writer.writerow([x['position'],x['step_rows'],x['batch_rows'],x['state_max_abs'],x['hidden']['max_abs'],x['logits']['max_abs'],x['greedy_equal'],x['finite'],x['kv_lengths_and_mirrors'],x['pass']])
 (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report.get(k) for k in ['status','completed_position','last_passing_position','max_errors','peak_child_rss_bytes']}),flush=True)
 return code
if __name__=='__main__':raise SystemExit(main())
