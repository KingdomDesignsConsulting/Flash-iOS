#!/usr/bin/env python3
"""Bounded, private matched-token state comparison. One model process at a time.
HTTP resident execution first; stop it; replay EXACT completed tokens from zero.
Stops control at earliest divergent fingerprint. Never modifies Qwen rendering.
"""
import argparse,datetime,hashlib,json,os,pathlib,signal,socket,subprocess,time,urllib.request,uuid
from experiment_session_token_exact import collect
P=pathlib.Path
MODEL='/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE'
def stamp():return datetime.datetime.now().astimezone().isoformat()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def gpu():
 import re
 s=subprocess.check_output(['ioreg','-r','-c','AGXAccelerator','-d','1']).decode();m=re.search(r'"Device Utilization %"\s*=\s*(\d+)',s);return int(m.group(1)) if m else None
def compare_parts(a,b):
 other={(p['component'],p['layer']):p for p in b.get('components',[])};differences=[]
 for part in a.get('components',[]):
  key=(part['component'],part['layer']);reference=other.get(key)
  if reference is None or reference['sha256']!=part['sha256']:
   differences.append(dict(component=key[0],layer=key[1],bytes=part['bytes'],active=part['active']))
 return differences
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=P,required=True);ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1]);ap.add_argument('--model',default=MODEL);ap.add_argument('--replace-pid',type=int);ap.add_argument('--case',choices=['implicit','explicit','thinking','length','tools','warmtools','canonical'],default='implicit');ap.add_argument('--dump-component');ap.add_argument('--dump-position',type=int,default=13);a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);http=a.out/'http';http.mkdir();control=a.out/'continuous';control.mkdir()
 binary=a.repo/'metal_infer/infer-session-state-experiment'
 report=dict(case=a.case,started=stamp(),binary_sha256=sha(binary),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip(),model=a.model,acceptance='Exact component SHA256, all KV lengths equal position, no nonfinite; no tolerance relaxation',status='INCOMPLETE',template_modified=False)
 report['source_sha256']={name:sha(a.repo/name) for name in ['metal_infer/infer.m','metal_infer/session_state_diag.inc','metal_infer/warm_state_cache.inc','metal_infer/Makefile']}
 write(a.out/'result.json',report)
 readings=[]
 for _ in range(3):readings.append(gpu());time.sleep(.3)
 assert all(n is not None and n<30 for n in readings),readings
 report['pre_gpu']=readings
 if a.replace_pid:
  owners=subprocess.run(['lsof','-t','-nP','-iTCP:11243','-sTCP:LISTEN'],capture_output=True,text=True).stdout.split()
  assert owners==[str(a.replace_pid)],'Refusing to stop an unverified listener'
  print('SERVER_STOP_EXISTING',stamp(),a.replace_pid,flush=True);os.kill(a.replace_pid,signal.SIGTERM)
  for _ in range(100):
   if subprocess.run(['lsof','-t','-nP','-iTCP:11243','-sTCP:LISTEN'],capture_output=True).returncode:break
   time.sleep(.1)
  else:raise RuntimeError('Existing server did not stop; no new model started')
 free=0
 for _ in range(30):
  with socket.socket() as sock:
   sock.settimeout(.3);free=free+1 if sock.connect_ex(('127.0.0.1',11243))!=0 else 0
  if free>=3:break
  time.sleep(.2)
 else:raise RuntimeError('Isolated port remains busy; no model started')
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(http))
 if a.dump_component:env.update(FLASH_SESSION_STATE_DUMP_COMPONENT=a.dump_component,FLASH_SESSION_STATE_DUMP_POSITION=str(a.dump_position))
 command=[str(binary),'--model',a.model,'--tiered','--no-prefill-nrow','--serve','11243']
 report['server_command']=command
 log=(a.out/'server.log').open('w');print('SERVER_START',stamp(),flush=True)
 proc=subprocess.Popen(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 traces=[];responses=[]
 try:
  deadline=time.monotonic()+120
  while time.monotonic()<deadline:
   if proc.poll() is not None:raise RuntimeError('Server startup failed')
   try:
    with urllib.request.urlopen('http://127.0.0.1:11243/health',timeout=1) as r:
     if r.status==200:break
   except OSError:pass
   time.sleep(.2)
  else:raise TimeoutError('Server ready timeout')
  manifest=load(http/'server.json');assert manifest['server_pid']==proc.pid and manifest['scalar_qualification']
  sid='state-'+uuid.uuid4().hex
  first=[{'role':'user','content':'Remember identifier STATE-73941. Reply exactly READY.'}]
  if a.case=='explicit':first.insert(0,{'role':'system','content':'You are a helpful assistant.'})
  if a.case=='thinking':first=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':'Think step by step about 17 times 23, then reply with the product.'}]
  turns=[first,[{'role':'user','content':'What identifier did I give? Reply only the identifier.'}]]
  if a.case=='warmtools':turns=turns+turns
  if a.case=='canonical':turns=turns+[turns[1]]
  for n,messages in enumerate(turns):
   if n==2 or (a.case=='canonical' and n):sid='state-'+uuid.uuid4().hex
   if a.case=='canonical' and n:messages=first+[{'role':'assistant','content':responses[0]['choices'][0]['message'].get('content','')},turns[1][0]]
   if a.case=='thinking' and n:break
   tag='state-'+uuid.uuid4().hex
   body=dict(model='qwen3.5',messages=messages,session_id=sid,stream=False,temperature=0,reasoning_effort='off',max_tokens=24,flash_trace_id=tag)
   if n%2==0 or a.case=='canonical':body['flash_session_create']=True
   if a.case in ('tools','warmtools'):body['tools']=[{'type':'function','function':{'name':'noop','description':'Never call this tool.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}]
   if a.case=='thinking':body.update(reasoning_effort='high',thinking_token_budget=1,max_tokens=72)
   if a.case=='length':body['max_tokens']=1
   req=urllib.request.Request('http://127.0.0.1:11243/v1/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=240) as r:reply=json.load(r)
   responses.append(reply);assert 'error' not in reply,reply
   _,prompt=collect(http,{},reply['id'],tag,'prompt');_,generated=collect(http,{},reply['id'],tag,'generated')
   statepath=http/(tag+'-state.json');deadline=time.monotonic()+10
   while not statepath.exists() and time.monotonic()<deadline:time.sleep(.05)
   state=load(statepath);assert state['history_complete'] and state['accepted'] and not state['failed'],state
   assert len(generated['forwarded_token_ids'])==len(generated['completed_token_ids'])
   assert generated['completed_positions']==list(range(generated['completed_positions'][0],state['end_position']))
   assert generated['end_pos']==len(state['effective_token_ids'])
   traces.append(dict(prompt=prompt,generated=generated,state=state));print('HTTP_COMPLETED',n,'position',state['end_position'],flush=True)
  write(a.out/'http-records.json',dict(traces=traces,responses=responses))
 finally:
  proc.terminate();proc.wait(timeout=15);log.close();print('SERVER_STOP',stamp(),'exit',proc.returncode,flush=True)
 expected={};boundary_mismatch=[]
 compared_traces=traces[1:] if a.case=='canonical' else traces
 for t in compared_traces:
  for row in t['state']['steps']:
   assert row.get('kv_lengths_match') and not any(c['nonfinite'] for c in row['components']),row
   pos=str(row['position'])
   if pos in expected and expected[pos]!=row['digest']:boundary_mismatch.append(int(pos))
   expected[pos]=row['digest']
 if a.case=='canonical':
  report['canonical_recreated_tokens_identical']=traces[1]['state']['effective_token_ids']==traces[2]['state']['effective_token_ids']
  report['canonical_recreated_answers_identical']=responses[1]['choices']==responses[2]['choices']
  assert report['canonical_recreated_tokens_identical'] and report['canonical_recreated_answers_identical']
 report['boundary_mismatch_positions']=boundary_mismatch
 report['requests']=[dict(end_position=t['state']['end_position'],ended_with_eos=t['generated']['ended_with_eos'],sampled_count=len(t['generated']['sampled_token_ids']),forwarded_count=len(t['generated']['forwarded_token_ids']),sampled_forwarded_differences=sum(x!=y for x,y in zip(t['generated']['sampled_token_ids'],t['generated']['forwarded_token_ids'])),timings=r.get('flash_timings',{}),finish_reason=r['choices'][0]['finish_reason']) for t,r in zip(traces,responses)]
 report['behavioral_identifier_retained']=(None if a.case=='thinking' else all('STATE-73941' in r['choices'][0]['message'].get('content','') for r in responses[1::2]))
 assert not boundary_mismatch,'Actual state changed at a request boundary'
 ids=traces[-1]['state']['effective_token_ids'];assert len(ids)<=512
 write(a.out/'replay-input.json',dict(token_ids=ids,expected_digests=expected))
 cmd=[str(binary),'--model',a.model,'--tiered','--no-prefill-nrow']
 replay_env=dict(env,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(a.out/'replay-input.json'))
 print('CONTINUOUS_START',stamp(),'tokens',len(ids),flush=True)
 with (a.out/'continuous.log').open('w') as f:
  result=subprocess.run(cmd,cwd=binary.parent,env=replay_env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=240)
 print('CONTINUOUS_STOP',stamp(),'exit',result.returncode,flush=True)
 actual=load(control/'continuous-replay-state.json');control_rows={str(r['position']):r for r in actual['steps']}
 earliest=None;differences=[]
 for t in compared_traces:
  for row in t['state']['steps']:
   reference=control_rows.get(str(row['position']))
   if reference and reference.get('digest')!=row['digest'] and (earliest is None or row['position']<earliest):earliest=row['position'];differences=compare_parts(row,reference)
 before=load(http/'startup-before-sync.json');after=load(http/'startup-after-sync.json');prefix=control_rows.get(str(before['position']))
 report.update(status='EXACT_FINGERPRINT_PASS' if result.returncode==0 and earliest is None else 'DIVERGENCE',control_exit=result.returncode,completed_http_tokens=len(ids),completed_control_tokens=actual['end_position'],first_divergent_position=earliest,components=differences,startup=dict(position=before['position'],changed_components=compare_parts(before,after),before_matches_control=prefix is not None and before['digest']==prefix['digest'],after_matches_control=prefix is not None and after['digest']==prefix['digest']),trace_count=len(traces),ended=stamp())
 write(a.out/'result.json',report);print(json.dumps({k:report[k] for k in ('status','first_divergent_position','completed_control_tokens')}),flush=True)
 return 0 if report['status']=='EXACT_FINGERPRINT_PASS' else 3
if __name__=='__main__':raise SystemExit(main())
