#!/usr/bin/env python3
"""Real LM Studio adapter/SDK Chat to Flash, mocked UI, no user documents."""
import argparse
from experiment_session_token_exact import collect
from session_gate_support import *
ACTIVE_OUT=None
def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;write(a.out/'result.json',dict(status='RUNNING'));sdk=a.out/'sdk.json'
 with server(a.out/'server',args=['--prefill-nrow']) as s:
  cmd=['node',str(REPO/'clients/lmstudio-documents/test/live-flash-release.cjs'),'--out',str(sdk)]
  with (a.out/'adapter.log').open('w') as log:r=subprocess.run(cmd,cwd=REPO/'clients/lmstudio-documents',stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  assert r.returncode==0,r.returncode;data=load(sdk);cases=[];prompts=[]
  for i,(req,rid) in enumerate(zip(data['requests'],data['request_ids'])):
   _,pt=collect(s['trace'],{},rid);prompts.append(pt)
   for thinking in [False,True]:cases.append(dict(name=f'{i}-{thinking}',messages=req['messages'],tools=req.get('tools'),thinking=thinking))
  source=a.out/'render-input.json';dest=a.out/'render-output.json';write(source,dict(cases=cases));env=dict(os.environ,FLASH_SESSION_RENDER_INPUT=str(source),FLASH_SESSION_RENDER_OUTPUT=str(dest))
  with (a.out/'render.log').open('w') as log:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  assert r.returncode==0;rendered=load(dest);assert not rendered['model_loaded'] and not rendered['metal_initialized']
  matches=[]
  for i,pt in enumerate(prompts):
   rows=[x for x in rendered['cases'] if x['name'].startswith(str(i)+'-') and x['token_ids']==pt['token_ids']];assert len(rows)==1;matches.append(dict(request=i,native_prompt_tokens=pt['prompt_tokens'],native_render_ids_exact=True,matched_thinking_mode=rows[0]['name'].split('-')[1]))
 write(a.out/'result.json',dict(status='PASS',requests=len(data['requests']),real_flash_inference=True,real_sdk_chat=True,mock_prediction_controller=True,GUI_tested=False,user_documents_accessed=False,external_tools_executed=False,stateless_full_history=True,native_prompts=matches))
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:write(ACTIVE_OUT/'result.json',dict(status='FAIL',error_type=type(error).__name__,error=str(error)))
  raise
