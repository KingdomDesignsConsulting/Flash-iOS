#!/usr/bin/env python3
"""Real LM Studio adapter/SDK Chat to Flash, mocked UI, no user documents."""
import argparse
from experiment_session_token_exact import collect
from session_gate_support import *
ACTIVE_OUT=None
def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);p.add_argument('--scalar-reference',action='store_true');p.add_argument('--protocol-only',action='store_true');p.add_argument('--state-reference',type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;write(a.out/'result.json',dict(status='RUNNING'));sdk=a.out/'sdk.json'
 if a.protocol_only:assert a.state_reference and load(a.state_reference/'result.json')['status']=='PASS','Protocol-only mode requires independently validated state reference'
 with server(a.out/'server',args=['--no-prefill-nrow' if a.scalar_reference else '--prefill-nrow']) as s:
  cmd=['node',str(REPO/'clients/lmstudio-documents/test/live-flash-release.cjs'),'--out',str(sdk)]+(['--protocol-only'] if a.protocol_only else [])
  with (a.out/'adapter.log').open('w') as log:r=subprocess.run(cmd,cwd=REPO/'clients/lmstudio-documents',stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  adapter_exit=r.returncode;data=load(sdk);cases=[];prompts=[];states=[]
  request_ids=data.get('request_ids') or [next(event['id'] for event in events if event.get('id')) for events in data['events']]
  assert len(data['requests'])==len(request_ids)==2
  for i,(req,rid) in enumerate(zip(data['requests'],request_ids)):
   matches=[load(path) for path in s['trace'].glob('*-prompt.json') if load(path).get('request_id')==rid];assert len(matches)==1
   _,pt=collect(s['trace'],{},rid,matches[0]['trace_identity']);prompts.append(pt);states.append(waitfile(s['trace']/(pt['trace_identity']+'-state.json')))
   for thinking in [False,True]:
    case=dict(name=f'{i}-{thinking}',messages=req['messages'],thinking=thinking)
    if 'tools' in req:case['tools']=req['tools']
    cases.append(case)
  source=a.out/'render-input.json';dest=a.out/'render-output.json';write(source,dict(cases=cases));env=dict(os.environ,FLASH_SESSION_RENDER_INPUT=str(source),FLASH_SESSION_RENDER_OUTPUT=str(dest))
  with (a.out/'render.log').open('w') as log:r=subprocess.run([str(BINARY),'--model',MODEL,'--tiered'],cwd=BINARY.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=60)
  assert r.returncode==0;rendered=load(dest);assert not rendered['model_loaded'] and not rendered['metal_initialized']
  matches=[]
  for i,pt in enumerate(prompts):
   rows=[x for x in rendered['cases'] if x['name'].startswith(str(i)+'-') and x['token_ids']==pt['token_ids']];assert len(rows)==1;matches.append(dict(request=i,native_prompt_tokens=pt['prompt_tokens'],native_render_ids_exact=True,matched_thinking_mode=rows[0]['name'].split('-')[1]))
 native_states_exact=None;reference_binary=None
 if a.state_reference:
  meta=load(a.state_reference/'result.json');assert meta['status']=='PASS' and all(row['exit']==0 and row['exact'] for row in meta['references'])
  golden=load(a.state_reference/'records.json')['records'];assert len(golden)>=len(states)
  for state,gold in zip(states,golden):
   ref=gold['state'];assert state['accepted'] and state['history_complete'] and not state['failed'] and state['effective_token_ids']==ref['effective_token_ids']
   points={point['position']:point['digest'] for point in ref['steps']};assert state['end_position'] in points and all(points.get(point['position'])==point['digest'] for point in state['steps'])
  native_states_exact=True;reference_binary=meta['binary_sha256']
 behavioral=data.get('behavioral_assertions',{});literal_ok=bool(behavioral) and all(behavioral.values())
 write(a.out/'result.json',dict(status='PASS' if adapter_exit==0 else 'FAIL',qualification_scope='Actual SDK/adapter protocol and native token/state preservation; model literal assertions reported separately',protocol_only=a.protocol_only,native_state_fingerprints_exact=native_states_exact,state_reference_binary_sha256=reference_binary,binary_sha256=sha(BINARY),adapter_exit=adapter_exit,scalar_reference=a.scalar_reference,behavioral_assertion_passed=literal_ok,native_request_ids_exact=True,requests=len(data['requests']),real_flash_inference=True,real_sdk_chat=True,mock_prediction_controller=True,GUI_tested=False,user_documents_accessed=False,external_tools_executed=False,stateless_full_history=True,native_prompts=matches))
 return 0 if adapter_exit==0 else 3
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:write(ACTIVE_OUT/'result.json',dict(status='FAIL',error_type=type(error).__name__,error=str(error)))
  raise
