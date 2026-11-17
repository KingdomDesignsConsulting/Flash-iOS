#!/usr/bin/env python3
"""Short isolated restored-binary operational check; no production transition."""
import argparse,json,pathlib,threading,time,urllib.request
from launch_historical_recovery import run,prepare
from recovery_tree import sha
P=pathlib.Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--selection',type=P,required=True);p.add_argument('--selection-sha256',required=True);p.add_argument('--probe',type=P,required=True);p.add_argument('--out',type=P,required=True);p.add_argument('--operator-exclusive-model',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive window required')
 a.out.mkdir(parents=True,exist_ok=False);m,root=prepare(a.selection,a.selection_sha256,a.probe);stop=threading.Event();state={}
 def serve():
  try:state.update(run(a.selection,a.selection_sha256,a.probe,a.out/'server',11250,stop,max_seconds=300))
  except Exception as e:state.update(status='BLOCKED',detail=str(e))
 thread=threading.Thread(target=serve);thread.start();report={'status':'INCOMPLETE','selection_sha256':a.selection_sha256,'binary_sha256':sha(root/'metal_infer/infer-candidate-lazy32k'),'production_access':False,'scope':'Freshly extracted historical runtime with original model/dependency identities; one short buffered request, not modern numerical/session qualification.'}
 try:
  end=time.monotonic()+120
  while time.monotonic()<end:
   log=a.out/'server/child.log'
   if log.exists() and '[serve] Ready' in log.read_text(errors='replace'):break
   if not thread.is_alive():raise RuntimeError('restored runtime not ready '+str(state))
   time.sleep(.1)
  else:raise RuntimeError('readiness timeout')
  with urllib.request.urlopen('http://127.0.0.1:11250/health',timeout=5) as res:
   if res.status!=200:raise RuntimeError('health failed')
  body={'model':'qwen3.5','messages':[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':'Reply exactly READY.'}],'max_tokens':8,'temperature':0}
  req=urllib.request.Request('http://127.0.0.1:11250/v1/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=60) as res:reply=json.load(res)
  (a.out/'short-response.json').write_text(json.dumps(reply,indent=2)+'\n')
  choice=reply['choices'][0]
  if choice['message'].get('content')!='READY' or choice['finish_reason']!='stop':raise RuntimeError('restored completion mismatch')
  report.update(status='PASS_SHORT_OPERATIONAL_RESTORE',health=200,content='READY',finish_reason='stop',usage=reply.get('usage'))
 except Exception as e:report.update(status='FAIL',error=str(e))
 finally:
  stop.set();thread.join(15);report['supervisor']=state
  if thread.is_alive():report.update(status='FAIL',error='owned recovery cleanup did not finish')
  if state.get('status')=='BLOCKED' or state.get('stop_reason') not in [None,'operator_cancel']:report['status']='BLOCKED_RESOURCE'
  (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('OPERATIONAL_RESTORE',report['status'],report.get('error'),flush=True)
 return 0 if report['status']=='PASS_SHORT_OPERATIONAL_RESTORE' else 3
if __name__=='__main__':raise SystemExit(main())
