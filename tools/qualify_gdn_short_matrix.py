#!/usr/bin/env python3
"""Short actual-model scalar/batched state oracle. No production/service inventory."""
import argparse,hashlib,importlib.util,json,os,pathlib,struct,subprocess,sys,time,datetime
R=pathlib.Path(__file__).resolve().parents[1]
def stamp():return datetime.datetime.now().astimezone().isoformat()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--supervisor-tools',required=True,type=pathlib.Path);p.add_argument('--probe',required=True,type=pathlib.Path);p.add_argument('--fixture',required=True,type=pathlib.Path);p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('--start-case',type=int,default=0);p.add_argument('--case-limit',type=int,default=0);p.add_argument('--engine-arg',action='append',default=[]);p.add_argument('--routes',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive model window required')
 sys.path.insert(0,str(a.supervisor_tools.resolve()));from supervise_qualified_serve import supervise,telemetry
 from run_session_state_mission import MODEL,gpu
 a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);raw=a.fixture.read_bytes();count=struct.unpack_from('<I',raw)[0]
 if len(raw)!=4*(count+1) or count<257:raise ValueError('invalid saved fixture')
 ids=list(struct.unpack_from('<257I',raw,4));cases=[(32,33),(64,65),(128,128),(128,129),(32,129),(64,129),(128,257)]
 if not 0<=a.start_case<len(cases):raise ValueError('invalid case offset')
 cases=cases[a.start_case:]
 if a.case_limit:cases=cases[:a.case_limit]
 report=dict(engine_args=a.engine_arg,route_capture=a.routes,case_offset=a.start_case,status='INCOMPLETE',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),fixture_sha256=hashlib.sha256(raw).hexdigest(),cases=[],started=stamp(),production_access=False)
 common={}
 for width,n in cases:
  readings=[]
  stable=0
  for _ in range(60):
   value=gpu();readings.append(value);stable=stable+1 if value is not None and value<30 else 0
   if stable==3:break
   time.sleep(1)
  if stable<3:report.update(status='BLOCKED_GPU',readings=readings);break
  folder=a.out/f'n{width}-t{n}';folder.mkdir();inputfile=folder/'input.json';inputdata=dict(token_ids=ids[:n],batch_starts=list(range(0,n-width+1,width)))
  if a.routes:inputdata.update(route_probe_start=0,route_probe_count=width,route_probe_layers=40)
  inputfile.write_text(json.dumps(inputdata))
  binary=R/'metal_infer'/f'infer-gdn-shape-{width}';env=os.environ.copy();env.update(FLASH_SESSION_TOKEN_TRACE_DIR=str(folder),FLASH_SESSION_NROW_ORACLE_INPUT=str(inputfile),FLASH_FE027_NUMERICS='63');env.pop('FLASH_SERVE_QUALIFIED_GPU_ONLY',None)
  command=[str(binary),'--model',MODEL,'--tiered','--no-prefill-nrow',*a.engine_arg];print('GDN_MODEL_START',stamp(),width,n,flush=True)
  budget=supervise(command,env,folder/'supervision',lambda pid:telemetry(a.probe,pid),max_seconds=300)
  print('GDN_MODEL_STOP',stamp(),width,n,budget.get('exit'),budget.get('stop_reason'),flush=True)
  case=dict(width=width,tokens=n,gpu=readings,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),supervision=budget,status='INCOMPLETE')
  oracle=folder/'nrow-oracle.json'
  if budget['status']!='EXITED' or not oracle.exists():
   case['status']='BLOCKED_RESOURCE' if budget.get('stop_reason') or budget['status']=='BLOCKED' else 'EXECUTION_ERROR';report['cases'].append(case);report['status']=case['status'];break
  data=json.loads(oracle.read_text());rows=data['rows'];ok=data['status']=='NUMERICAL_PASS' and data['completed_position']==n and rows
  for row in rows:
   ok=ok and row['pass'] and row['finite'] and row['greedy_equal'] and row['kv_lengths_and_mirrors'] and row['state_max_abs']<1e-3 and row['hidden']['max_abs']<=1e-3 and row['logits']['max_abs']<=1e-2
   # Same effective fixture prefix and scalar reference must agree across cases.
   pos=row['position'];digest=row['reference_digest']
   if pos in common and common[pos]!=digest:ok=False
   common[pos]=digest
  case.update(status='PASS' if ok else 'FAIL',endpoints=len(rows),persistent_exact=all(x['candidate_digest']==x['reference_digest'] and x['state_different']==0 for x in rows),max_errors={k:max(x[f]['max_abs'] if f else x['state_max_abs'] for x in rows) for k,f in [('state',None),('hidden','hidden'),('logits','logits')]},raw_oracle_sha256=hashlib.sha256(oracle.read_bytes()).hexdigest())
  report['cases'].append(case);(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
  if not ok:report['status']='FAIL';break
 else:report['status']='PASS_BOUNDED_FULL_MODEL_MATRIX'
 report['ended']=stamp();(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('GDN_MATRIX_RESULT',report['status'],flush=True);return 0 if report['status']=='PASS_BOUNDED_FULL_MODEL_MATRIX' else 3
if __name__=='__main__':raise SystemExit(main())
