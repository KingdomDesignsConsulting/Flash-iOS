#!/usr/bin/env python3
"""Sequential 16K then 32K release oracle with conservative measured preflight.
This does not establish production admission or authorize deployment.
"""
import argparse,json,os,pathlib,subprocess,sys
from run_session_state_mission import stamp,sha
P=pathlib.Path
GIB=1024**3

def estimate(samples,target):
 last=samples[-1];position=last['position'];assert position>0
 per_token=last['active_kv_bytes']/position
 # One active shared KV plus two full independent oracle banks. Existing N128
 # workspace/expert cache is included in the measured baseline after a slab.
 base=max(max(x['physical_footprint_peak_bytes'],x['resident_bytes'],x['metal_current_allocated_bytes']+x['two_oracle_snapshots_malloc_bytes']+x['cpu_gdn_malloc_bytes']+x['cpu_convolution_malloc_bytes']) for x in samples)
 assert base>0 and all(x['task_info_status']==0 for x in samples)
 growth=max(0,target-position)*per_token*3
 return dict(observed_conservative_base_bytes=base,from_position=position,target=target,kv_growth_three_copies_bytes=int(growth),unattributed_margin_bytes=2*GIB,estimated_process_bound_bytes=int(base+growth+2*GIB),process_ceiling_bytes=18*GIB,system_reserve_bytes=6*GIB)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--corpus',required=True,type=P);p.add_argument('--preflight',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--timeout',type=int,default=4200);p.add_argument('--start-at',type=int,choices=[16384,32768],default=16384);p.add_argument('--validated-16k',type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 manifest=json.loads(a.corpus.read_text());samples=json.loads(a.preflight.read_text())['samples'];report=dict(status='RUNNING',started=stamp(),cases=[]);repo=P(__file__).resolve().parents[1]
 if a.start_at==32768:
  assert a.validated_16k and a.preflight.resolve().parent==a.validated_16k.resolve().parent
  saved=json.loads(a.validated_16k.read_text());native=json.loads(a.validated_16k.with_name('nrow-oracle.json').read_text())
  assert saved['status']=='PASS' and saved['completed_position']==16384 and saved['numerics_mask']==63 and saved['binary_sha256']==sha(a.binary)
  assert saved['fixture_sha256']==next(x['fixture_sha256'] for x in manifest['cases'] if x['count']==16384)
  assert native['rows'] and all(x['pass'] and x['candidate_digest']==x['reference_digest'] for x in native['rows'])
  report['validated_16k_resume']=True
 for target in ([16384,32768] if a.start_at==16384 else [32768]):
  bound=estimate(samples,target);case=dict(target=target,preflight=bound,status='NOT_RUN');report['cases'].append(case)
  if bound['estimated_process_bound_bytes']>bound['process_ceiling_bytes']:
   case.update(status='BLOCKED',reason='Conservative measured growth bound leaves insufficient 24GiB system margin');report['status']='BLOCKED';break
  pressure=subprocess.run(['memory_pressure','-Q'],capture_output=True,text=True,timeout=10);case['host_pressure_before']=pressure.stdout
  import re
  m=re.search(r'free percentage: (\d+)%',pressure.stdout)
  if pressure.returncode or not m or int(m[1])<35:
   case.update(status='BLOCKED',reason='Host memory availability below conservative launch threshold');report['status']='BLOCKED';break
  fixture=next(x for x in manifest['cases'] if x['count']==target);dest=a.out/str(target)
  cmd=[sys.executable,str(repo/'tools/qualify_session_accumulation.py'),'--binary',str(a.binary.resolve()),'--fixture',fixture['fixture'],'--count',str(target),'--full-final-slab','--numerics','63','--gpu-wait','120','--timeout',str(a.timeout),'--max-rss-gib','16','--out',str(dest)]
  case['command']=cmd;case['started']=stamp();print('LONG_START',stamp(),target,'COMMAND',json.dumps(cmd),flush=True)
  env=dict(os.environ,FLASH_TRACE_GPU_KV_BOUNDARY='1')
  with (a.out/(str(target)+'-driver.log')).open('w') as log:r=subprocess.run(cmd,cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=a.timeout+150)
  case.update(ended=stamp(),exit=r.returncode,status='PASS' if r.returncode==0 else 'FAIL');print('LONG_STOP',stamp(),target,'exit',r.returncode,flush=True)
  if r.returncode:report['status']='STOPPED';break
  native=json.loads((dest/'nrow-oracle.json').read_text())
  if native['completed_position']!=target or not native['rows'] or not all(x.get('candidate_digest') and x['candidate_digest']==x.get('reference_digest') for x in native['rows']):
   case.update(status='FAIL',reason='Exact active fingerprints required for mask 63');report['status']='STOPPED';break
  samples=json.loads((dest/'memory-observations.json').read_text())['samples'];(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 else:report['status']='PASS'
 report['ended']=stamp();(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
