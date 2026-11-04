#!/usr/bin/env python3
"""Sequential Work A queue: never escalates past unqualified native state.
No deployment, no production requests, no automatic retry after stage failure.
"""
import argparse,json,os,pathlib,shutil,subprocess,sys,time
from run_session_state_mission import stamp,sha
from work_a_manifest import verify_bound_build
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=P);p.add_argument('--corpus-root',required=True,type=P);p.add_argument('--repeats16',type=int,choices=[1,2,3],default=3);p.add_argument('--repeats32',type=int,choices=[1,2,3],default=3);p.add_argument('--max-hours',type=float,default=14);a=p.parse_args();assert 1<=a.max_hours<=18
 repo=P(__file__).resolve().parents[1];root=a.root.resolve();out=root/'sequence';out.mkdir(exist_ok=False);manifest=root/'release-manifest.json';gate=root/'repaired-32768/result.json';binary=repo/'metal_infer/infer-work-a-http';control=repo/'metal_infer/infer-work-a-control';candidate=repo/'metal_infer/infer-work-a-performance';probe=root/'physical-probe';deadline=time.monotonic()+a.max_hours*3600
 report=dict(status='WAIT_NATIVE_GATE',started=stamp(),release_manifest_sha256=sha(manifest),runner_sha256=sha(P(__file__)),cases=[],production_modified=False)
 def save(): (out/'suite.json').write_text(json.dumps(report,indent=2)+'\n')
 save();print('WORK_A_QUEUE_WAIT',stamp(),str(gate),flush=True)
 while True:
  native=json.loads(gate.read_text())
  if native['status']!='RUNNING':break
  if time.monotonic()>=deadline:report.update(status='BLOCKED',reason='Queue wall budget while waiting for native gate');save();return 4
  time.sleep(10)
 if native['status']!='PASS':report.update(status='STOPPED',reason='Native gate did not pass',native_status=native['status']);save();return 3
 report['native_verification']=verify_bound_build(manifest,binary,gate);report['status']='RUNNING';save()
 for count in [16384,32768]:
  for kind in ['input','render']:
   dst=root/f'long-{count}-{kind}.json';assert not dst.exists();shutil.copy2(a.corpus_root/f'long-{count}-1-{kind}.json',dst)
 common=['--manifest',str(manifest),'--native-gate',str(gate)];cases=[
  ('literal',['tools/qualify_work_a_literal.py','--binary',str(binary),'--sdk-record',str(root/'original-sdk-record.json'),*common]),
  ('sustained',['tools/qualify_work_a_sustained.py','--binary',str(binary),*common]),
  ('decode-timing',['tools/benchmark_work_a_decode.py','--binary',str(candidate),'--qualification',str(root/'sustained'),'--probe',str(probe),*common]),
  ('profile',['tools/qualify_named_profile_http.py','--engine-arg=--prefill-nrow','--prefix-words','128','--turns','3']),
  ('cancellation',['tools/qualify_session_lifecycle.py'])]
 for count,repeats in [(16384,a.repeats16),(32768,a.repeats32)]:
  cases.append((f'performance-{count}',['tools/benchmark_work_a_long.py','--control',str(control),'--candidate',str(candidate),'--variants',str(root/'build-variants.json'),'--render-input',str(root/f'long-{count}-input.json'),'--render-output',str(root/f'long-{count}-render.json'),'--probe',str(probe),'--count',str(count),'--repeats',str(repeats),*common]))
 report['cases']=[dict(name=name,status='NOT_RUN') for name,args in cases];save();logs=P('/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/benchmark-logs');env=dict(os.environ,FLASH_FE027_NUMERICS='63',FLASH_QUALIFICATION_BINARY=str(binary))
 for index,(name,args) in enumerate(cases):
  remaining=int(deadline-time.monotonic())
  if remaining<300:report.update(status='STOPPED',reason='Queue budget: no new stage');break
  verify_bound_build(manifest,binary,gate)
  if name.startswith('performance-'):args=args+['--max-seconds',str(min(21600,remaining))]
  cmd=[sys.executable,*args,'--out',str(root/name)];logpath=logs/f'work-a-{root.name}-{name}.log';assert not logpath.exists();row=report['cases'][index];row.update(status='RUNNING',started=stamp(),command=cmd,entry_sha256=sha(repo/args[0]),authenticated_binary_sha256=sha(binary));save();print('WORK_A_STAGE_START',stamp(),name,'COMMAND',json.dumps(cmd),flush=True)
  with logpath.open('x') as log:
   process=subprocess.Popen(cmd,cwd=repo,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
   for line in process.stdout:
    log.write(line);log.flush()
    if any(tag in line for tag in ['SERVER_START','SERVER_STOP','CONTROL_START','CONTROL_STOP','CLI_START','CLI_STOP','LITERAL_CASE','SUSTAINED_TURN','SUSTAINED_TIMING','LONG_PERF_CASE']):print(line.strip(),flush=True)
   code=process.wait()
  row.update(exit=code,ended=stamp(),status='PASS' if code==0 else 'STOPPED',log_sha256=sha(logpath))
  result=root/name/'result.json'
  if result.exists():row.update(result_sha256=sha(result),reported_status=json.loads(result.read_text()).get('status'))
  save();print('WORK_A_STAGE_STOP',stamp(),name,'exit',code,flush=True)
  if code:report.update(status='STOPPED',reason='Stage failed; no automatic retry',stopped_stage=name);break
 else:report['status']='COMPLETED'
 report['ended']=stamp();save();return 0 if report['status']=='COMPLETED' else 3
if __name__=='__main__':raise SystemExit(main())
