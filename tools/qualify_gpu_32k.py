#!/usr/bin/env python3
"""Qualify experimental GPU32K arms from immutable historical checkpoint fixtures."""
import argparse, datetime, hashlib, json, os, pathlib, re, shutil, subprocess
import numpy as np
P=pathlib.Path
MODEL='/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE'
FIELDS=('hidden','logits','kv','cpu-recurrent','gpu-recurrent')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def compare(a,b):
 assert a.stat().st_size==b.stat().st_size and a.stat().st_size%4==0
 x=np.memmap(a,dtype='<f4',mode='r');y=np.memmap(b,dtype='<f4',mode='r')
 maximum=0.;sse=0.;ref2=0.;refmax=0.;different=0;nonfinite=0
 for start in range(0,len(x),262144):
  xx=np.asarray(x[start:start+262144],dtype=np.float64);yy=np.asarray(y[start:start+262144],dtype=np.float64)
  nonfinite+=int(np.count_nonzero(~np.isfinite(xx)|~np.isfinite(yy)))
  d=np.abs(xx-yy);maximum=max(maximum,float(d.max(initial=0)))
  different+=int(np.count_nonzero(xx.view(np.uint64)!=yy.view(np.uint64)))
  sse+=float(d@d);ref2+=float(xx@xx);refmax=max(refmax,float(np.abs(xx).max(initial=0)))
 return dict(elements=len(x),different=different,nonfinite=nonfinite,max_abs=maximum,
   rms=float(np.sqrt(sse/max(1,len(x)))),relative_l2=float(np.sqrt(sse/max(ref2,1e-30))),reference_max=refmax,
   control_sha256=sha(a),candidate_sha256=sha(b))
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1]);ap.add_argument('--out',type=P,required=True)
 ap.add_argument('--anchor',type=P,required=True);ap.add_argument('--pos',type=int,required=True)
 ap.add_argument('--arms',default='8k,16k,lazy16k,lazy32k,lazy32k-nochain');ap.add_argument('--timeout',type=int,default=240)
 ap.add_argument('--keep-arrays',action='store_true');a=ap.parse_args()
 assert a.pos in (8191,16382,32766)
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 report={'started':datetime.datetime.now().astimezone().isoformat(),'pos':a.pos,'fixture':str(a.anchor),'fixture_sha256':sha(a.anchor),
   'hidden_sha256':sha(a.anchor.with_name('hidden.bin')),'driver_sha256':sha(P(__file__)), 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip(),
   'criteria':{'legacy_vs_lazy':'bitwise for 16K arms; numerical for 32K arm','8k_vs_16k':'tokens identical, finite; relative_l2<=1e-4 and max_abs<=1e-3+1e-4*reference_max per field'},'arms':{},'comparisons':[]}
 report['sources']={str(p.relative_to(a.repo)):sha(p) for p in (a.repo/'metal_infer').iterdir() if p.suffix in ('.m','.inc','.metal','.h') or p.name=='Makefile'}
 (out/'manifest.json').write_text(json.dumps(report,indent=2))
 rows={}
 for arm in a.arms.split(','):
  dest=out/arm;dest.mkdir();binary=a.repo/'metal_infer'/('infer-qual-'+('lazy32k' if arm == 'lazy32k-nochain' else arm))
  command=[str(binary),'--model',MODEL,'--tiered','--no-malloc-cache','--no-expert-prefetch']
  if arm.endswith('nochain'):command.append('--no-cmd12-full-chain')
  env=os.environ.copy();env.update(FLASH_QUAL_ANCHOR=str(a.anchor.resolve()),FLASH_QUAL_HIDDEN=str(a.anchor.with_name('hidden.bin').resolve()),FLASH_QUAL_POS=str(a.pos),FLASH_QUAL_OUT=str(dest))
  log=out/(arm+'.log');print('RUN',arm,flush=True)
  with log.open('w') as f:
   try:r=subprocess.run(command,cwd=a.repo/'metal_infer',env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=a.timeout)
   except subprocess.TimeoutExpired:
    report['failure']=f'{arm} timeout';(out/'report.json').write_text(json.dumps(report,indent=2));raise
  text=log.read_text(errors='replace');records=[json.loads(line.split('] ',1)[1]) for line in text.splitlines() if line.startswith('[qual-step] ')]
  report['arms'][arm]={'command':command,'binary_sha256':sha(binary),'exit':r.returncode,'steps':records}
  (out/'report.json').write_text(json.dumps(report,indent=2))
  if r.returncode or '[qual] RESULT=PASS' not in text or len(records)!=5:raise RuntimeError(f'{arm} failed: exit={r.returncode}; see {log}')
  cap=8192 if arm=='8k' else (32768 if arm.startswith('lazy32k') else 16384)
  for row in records:
   routes=[tuple(map(int,m)) for m in re.findall(r'\[qual-route\] pos=(\d+) layer=(\d+) len=(\d+) gpu=(\d+) chain=(\d+)',text) if int(m[0])==row['pos']]
   # Step zero is deliberately replayed once after rollback.
   expected=20 if row['step']==0 else 10
   if len(routes)!=expected or set(x[1] for x in routes)!=set(range(3,40,4)) or any(bool(x[3])!=(32<=row['len']<=cap) for x in routes):raise RuntimeError(f'route mismatch {arm} {row}: {routes}')
  rows[arm]=records;print('PASS',arm,flush=True)
 pairs=[]
 if '16k' in rows and 'lazy16k' in rows:pairs.append(('16k','lazy16k',True))
 if 'lazy16k' in rows and 'lazy32k' in rows:pairs.append(('lazy16k','lazy32k',False))
 if '8k' in rows and 'lazy32k' in rows:pairs.append(('8k','lazy32k',False))
 if 'lazy32k-nochain' in rows and 'lazy32k' in rows:pairs.append(('lazy32k','lazy32k-nochain',False))
 if '8k' in rows and '16k' in rows:pairs.append(('8k','16k',False))
 if 'lazy16k-nochain' in rows and 'lazy16k' in rows:pairs.append(('lazy16k','lazy16k-nochain',False))
 passed=True
 for control,candidate,exact in pairs:
  for step in range(5):
   result={'control':control,'candidate':candidate,'step':step,'token_equal':rows[control][step]['token']==rows[candidate][step]['token'],'fields':{}}
   passed &= result['token_equal']
   for field in FIELDS:
    stats=compare(out/control/f'step-{step}-{field}.f32',out/candidate/f'step-{step}-{field}.f32')
    ok=not stats['nonfinite'] and (stats['control_sha256']==stats['candidate_sha256'] if exact else stats['relative_l2']<=1e-4 and stats['max_abs']<=1e-3+1e-4*stats['reference_max'])
    stats['pass']=ok;passed &= ok;result['fields'][field]=stats
   report['comparisons'].append(result)
   print('COMPARE',control,candidate,step,'token',result['token_equal'],'max_abs', {k:v['max_abs'] for k,v in result['fields'].items()},flush=True)
 report['result']='PASS' if passed else 'FAIL';report['finished']=datetime.datetime.now().astimezone().isoformat()
 (out/'report.json').write_text(json.dumps(report,indent=2))
 if not a.keep_arrays:
  for arm in rows:shutil.rmtree(out/arm)
 print(report['result'],str(out),flush=True)
 if not passed:raise SystemExit(1)
if __name__=='__main__':main()
