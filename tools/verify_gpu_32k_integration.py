#!/usr/bin/env python3
"""Build and smoke opt-in 16K/32K integration binaries without touching production."""
import argparse, hashlib, json, pathlib, subprocess, sys
P=pathlib.Path
def sha(p):
 if not p.is_file():return None
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1<<20),b''):h.update(block)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1])
 ap.add_argument('--out',type=P,required=True)
 a=ap.parse_args();repo=a.repo.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 prod=repo/'metal_infer/infer'
 before=sha(prod)
 result={'status':'INCOMPLETE','production_infer_before_sha256':before,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()}
 def save(): (out/'report.json').write_text(json.dumps(result,indent=2))
 save()
 try:
  branch=subprocess.check_output(['git','branch','--show-current'],cwd=repo,text=True).strip()
  if branch!='experiment/gqa-32k-lazy-kv-20261022':raise RuntimeError('Wrong branch: '+branch)
  changes=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
  if changes:raise RuntimeError('Local Git worktree is not clean; refusing build')
  command=[sys.executable,str(repo/'tools/soak_gpu_32k_http.py'),'--repo',str(repo),'--build','--integration-candidates','--rounds','2','--out',str(out/'http')]
  result['command']=command;save()
  with (out/'runner.log').open('w') as log:
   try:process=subprocess.run(command,cwd=repo,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
   except subprocess.TimeoutExpired:raise RuntimeError('HTTP smoke exceeded 30-minute timeout')
  result['smoke_exit']=process.returncode
  if process.returncode:raise RuntimeError('HTTP smoke failure; examine runner.log and http per-arm logs')
  summary=json.loads((out/'http/summary.json').read_text())
  if summary.get('result')!='PASS':raise RuntimeError('HTTP summary not PASS')
  result['summary']=summary
  result['candidate_sha256']={name:sha(repo/'metal_infer'/name) for name in ('infer-candidate-lazy16k','infer-candidate-lazy32k')}
  if None in result['candidate_sha256'].values():raise RuntimeError('Missing integration binary')
  result['status']='PASS'
 except Exception as error:
  result['status']='FAIL';result['error']=str(error)
 finally:
  result['production_infer_after_sha256']=sha(prod)
  if result['production_infer_before_sha256']!=result['production_infer_after_sha256']:
   result['status']='FAIL';result['error']='Production infer changed during test'
  save()
 print(result['status'],out)
 if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
