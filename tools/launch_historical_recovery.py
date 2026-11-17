#!/usr/bin/env python3
"""Owner-supervised launch of the explicitly selected historical rollback runtime.
No production port without a separate bound operator authorization record.
Legacy binary is not relabeled as having modern native context admission.
"""
import argparse,json,os,pathlib,signal,stat,threading,time
from recovery_tree import sha
from supervise_qualified_serve import supervise,telemetry
from qualify_mask63_missing import wait_gpu
P=pathlib.Path

def prepare(selection_path,expected_sha,probe):
 if sha(selection_path)!=expected_sha:raise ValueError('selection manifest hash mismatch')
 m=json.loads(selection_path.read_text());root=P(m['runtime_root']).resolve()
 if m['executable_sha256']!='497ccfb734e17a7fa7f3369265b739dedf51e8b2cde55fed07e8a77d50db1909':raise ValueError('unapproved historical binary')
 needed={'metal_infer/infer-candidate-lazy32k','metal_infer/shaders.metal','metal_infer/gguf_iq_shared.h','metal_infer/prefill_probe/chunk_kernels.metal'}
 if not needed<=set(m['files']):raise ValueError('missing recovery dependency role')
 for name,want in m['files'].items():
  p=P(name)
  if p.is_absolute() or '..' in p.parts or sha(root/p)!=want:raise ValueError('runtime dependency mismatch '+name)
 if sha(P(m['zstd_path']))!=m['zstd_sha256']:raise ValueError('Zstd mismatch')
 if sha(P(m['model_manifest_path']))!=m['model_manifest_sha256']:raise ValueError('model manifest mismatch')
 for name,expected in m['model_stat'].items():
  if P(name).is_absolute() or '..' in P(name).parts:raise ValueError('model dependency traversal')
  s=(P(m['model_root'])/name).stat()
  if (s.st_size,s.st_ino,s.st_mtime_ns)!=(expected['bytes'],expected['inode'],expected['mtime_ns']):raise ValueError('model changed after checksum '+name)
 if not probe.is_file():raise ValueError('probe missing')
 return m,root

def authorize_production(path,selection_sha,selection,now=None):
 now=time.time() if now is None else now;s=path.lstat()
 if path.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_mode&0o022:raise ValueError('unsafe authorization record')
 d=json.loads(path.read_text())
 for key in ['production_cutover_authorized','software_rollback_only','fallback_native_context_guard_acknowledged']:
  if d.get(key) is not True:raise ValueError('missing explicit authorization '+key)
 if d.get('purpose')!='historical-rollback' or d.get('operator_uid')!=os.getuid() or d.get('port')!=11241:raise ValueError('wrong authorization purpose/owner/port')
 if d.get('selection_sha256')!=selection_sha or d.get('archive_sha256')!=selection['archive_sha256'] or d.get('model_path')!=selection['model_root']:raise ValueError('authorization identity mismatch')
 expiry=d.get('expires_unix')
 if type(expiry) not in [float,int] or not now<expiry<=now+21600:raise ValueError('expired/unbounded authorization')
 return d

def run(selection_path,selection_sha,probe,out,port,stop,*,max_seconds=21600):
 m,root=prepare(selection_path,selection_sha,probe)
 readings=wait_gpu()
 # All variables explicit. In particular no inherited model/FE027/debug flags.
 command=[str(root/'metal_infer/infer-candidate-lazy32k'),'--model',m['model_root'],'--tiered','--serve',str(port),'--prefill-nrow','--timing']
 env=dict(m['environment']);env['PYTHONPYCACHEPREFIX']='/private/tmp/mask63-pycache'
 print('RECOVERY_SERVER_START',time.strftime('%Y-%m-%dT%H:%M:%S%z'),json.dumps(command),flush=True)
 result=supervise(command,env,out,lambda pid:telemetry(probe,pid),max_seconds=max_seconds,stop=stop,cwd=root/'metal_infer')
 result.update(prelaunch_gpu=readings,selection_sha256=selection_sha,historical_native_context_policy=m['native_context_guard'])
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print('RECOVERY_SERVER_STOP',time.strftime('%Y-%m-%dT%H:%M:%S%z'),result.get('exit'),result.get('stop_reason'),flush=True)
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--selection',type=P,required=True);p.add_argument('--selection-sha256',required=True);p.add_argument('--probe',type=P,required=True);p.add_argument('--out',type=P,required=True);p.add_argument('--port',type=int,default=11250);p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('--production-rollback-plan',type=P);p.add_argument('--authorize-production-rollback',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive model window required')
 m,_=prepare(a.selection,a.selection_sha256,a.probe)
 if a.port==11241:
  if not a.authorize_production_rollback or not a.production_rollback_plan:p.error('production rollback requires explicit authorized bound plan')
  authorize_production(a.production_rollback_plan,a.selection_sha256,m)
 elif a.port!=11250 or a.production_rollback_plan or a.authorize_production_rollback:p.error('only isolated11250 or separately authorized11241 allowed')
 stop=threading.Event()
 for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:stop.set())
 result=run(a.selection,a.selection_sha256,a.probe,a.out,a.port,stop)
 return 0 if result.get('exit')==0 else 1
if __name__=='__main__':raise SystemExit(main())
