#!/usr/bin/env python3
"""Repeat already-qualified substantial responses without state-hash observers.
Reports full-generation wall throughput, not TTFT-excluded kernel-only decode.
"""
import argparse,threading
from session_gate_support import *
from work_a_manifest import verify_bound_build
from qualify_session_accumulation import wait_bounded_process
ACTIVE_OUT=None

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['binary','manifest','native_gate','qualification','probe','out']:p.add_argument('--'+key.replace('_','-'),required=True,type=P)
 a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;verify_bound_build(a.manifest,a.binary,a.native_gate);assert load(a.qualification/'result.json')['status']=='PASS','Substantial output must actually be qualified first'
 source=load(a.qualification/'mask63-records.json')['rows'];rows=[];memory=[];budget=[];report=dict(status='RUNNING',release_manifest_sha256=sha(a.manifest),binary_sha256=sha(a.binary),runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),qualification_sha256=sha(a.qualification/'result.json'),timing_scope='Uninstrumented state path; full-generation wall TPS includes first LM head and EOS; not kernel-only or TTFT-excluded steady-state',rows=rows);write(a.out/'result.json',report)
 with server(a.out/'server',binary=a.binary.resolve(),args=['--prefill-nrow'],env_extra={'FLASH_FE027_NUMERICS':'63'},diagnostic_trace=False) as s:
  def observe(label):
   r=subprocess.run([str(a.probe.resolve()),str(s['pid'])],capture_output=True,text=True,timeout=5);assert r.returncode==0;data=dict(at=stamp(),label=label,**json.loads(r.stdout));assert data['start_abstime']>0;memory.append(data);write(a.out/'memory.json',memory)
  def monitor():
   code,peak,reason=wait_bounded_process(s['process'],1800,16*1024**3,host_free_floor=15);budget.append(dict(exit=code,peak_rss_bytes=peak,stop_reason=reason))
  thread=threading.Thread(target=monitor,daemon=True);thread.start();observe('ready')
  for original in source:
   request=dict(original['request']);request.pop('flash_trace_id',None);result=stream_request(request,timeout=600);assert result['visible']==original['response']['visible'] and result['timings']['generated_tokens']==original['response']['timings']['generated_tokens'];assert result['timings']['generated_tokens']>=192
   row=dict(index=original['index'],timings=result['timings'],usage=result['usage'],wall_ms=result['wall_ms'],wire_ttft_ms=result['wire_ttft_ms'],normalized_visible_matches_qualified=True);rows.append(row);write(a.out/'result.json',report);observe('turn-'+str(original['index']));print('SUSTAINED_TIMING',stamp(),original['index'],'generated',result['timings']['generated_tokens'],'full_generation_tps',result['timings']['decode_tokens_per_second'],flush=True)
 thread.join(20);assert budget and budget[0]['stop_reason'] is None;report.update(status='PASS',ended=stamp(),budget=budget[0],physical_memory_observations=memory);write(a.out/'result.json',report);return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   file=ACTIVE_OUT/'result.json';report=load(file) if file.exists() else {};report.update(status='FAIL',error_type=type(error).__name__,error=str(error));write(file,report)
  raise
