#!/usr/bin/env python3
"""Manifest-bound repaired native qualification; no reference-state rebasing."""
import argparse,json,os,pathlib,subprocess,sys
from run_session_state_mission import sha,stamp
from qualify_release_long import estimate
from qualify_session_accumulation import host_free_percent
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True,type=P);p.add_argument('--binary',required=True,type=P);p.add_argument('--preflight',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--count',type=int,choices=[16384,32768],default=32768);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 repo=P(__file__).resolve().parents[1];manifest=json.loads(a.manifest.read_text());assert sha(a.binary)==manifest['binary_sha256']
 for name,digest in manifest['source_sha256'].items():assert sha(repo/name)==digest,'Frozen runtime changed: '+name
 fixture=P(manifest['fixtures'][str(a.count)]['path']);assert sha(fixture)==manifest['fixtures'][str(a.count)]['sha256']
 pre=json.loads(a.preflight.read_text());meta=json.loads(a.preflight.with_name('result.json').read_text());assert meta['status']=='PASS' and meta['binary_sha256']==sha(a.binary)
 bound=estimate(pre['samples'],a.count);free=host_free_percent();report=dict(status='NOT_RUN',started=stamp(),release_manifest_sha256=sha(a.manifest),binary_sha256=sha(a.binary),source_head=manifest['head'],count=a.count,preflight=bound,host_free_before=free)
 def save(): (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 if bound['estimated_process_bound_bytes']>bound['process_ceiling_bytes'] or free is None or free<35:
  report.update(status='BLOCKED',reason='Memory preflight or monitor');save();return 4
 processes=subprocess.check_output(['ps','-ww','-axo','pid=,command='],text=True)
 if any(' --model ' in line and ('/infer-' in line or '/infer ' in line) for line in processes.splitlines()):
  report.update(status='BLOCKED',reason='Other model process active');save();return 4
 cmd=[sys.executable,str(repo/'tools/qualify_session_accumulation.py'),'--binary',str(a.binary.resolve()),'--fixture',str(fixture),'--count',str(a.count),'--full-final-slab','--numerics','63','--gpu-wait','60','--timeout','10800','--max-rss-gib','16','--min-host-free-percent','15','--out',str(a.out/'native')]
 report.update(status='RUNNING',command=cmd);save();print('WORK_A_NATIVE_START',stamp(),json.dumps(cmd),flush=True)
 result=subprocess.run(cmd,cwd=repo,env=dict(os.environ,FLASH_TRACE_GPU_KV_BOUNDARY='1'),stdin=subprocess.DEVNULL)
 report.update(exit=result.returncode,ended=stamp(),status='FAIL' if result.returncode else 'PASS')
 if result.returncode==0:
  native=json.loads((a.out/'native/nrow-oracle.json').read_text());rows=native['rows'];assert native['completed_position']==a.count and len(rows)==a.count//128
  assert all(x['pass'] and x['finite'] and x['greedy_equal'] and x['kv_lengths_and_mirrors'] and x['candidate_digest']==x['reference_digest'] and x['state_max_abs']<1e-3 and x['hidden']['max_abs']<=1e-3 and x['logits']['max_abs']<=1e-2 for x in rows)
  report.update(observed_endpoints=len(rows),persistent_fingerprints_exact=True,max_errors={key:max(x[field]['max_abs'] if field else x['state_max_abs'] for x in rows) for key,field in [('state',None),('hidden','hidden'),('logits','logits')]})
 save();print('WORK_A_NATIVE_STOP',stamp(),report['status'],flush=True);return result.returncode
if __name__=='__main__':raise SystemExit(main())
