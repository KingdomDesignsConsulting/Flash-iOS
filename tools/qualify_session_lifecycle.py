#!/usr/bin/env python3
"""Real TCP-reset cancellation at observed engine phases, then exact recovery."""
import argparse,json,os,pathlib,socket,struct,subprocess,time,urllib.request,urllib.error,uuid
from run_session_state_mission import gpu,stamp,MODEL,sha
P=pathlib.Path

def read(p):return json.loads(p.read_text())
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def request(body):
 req=urllib.request.Request('http://127.0.0.1:11243/v1/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=120) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def waitfile(p,timeout=30,predicate=lambda x:True):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   x=read(p)
   if predicate(x):return x
  except (OSError,json.JSONDecodeError):pass
  time.sleep(.005)
 raise TimeoutError(str(p))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 repo=P(__file__).resolve().parents[1];binary=repo/'metal_infer/infer-session-state-experiment';trace=a.out/'http';trace.mkdir();stable=0;loads=[]
 for _ in range(10):
  g=gpu();loads.append(g);stable=stable+1 if g is not None and g<30 else 0
  if stable==3:break
  time.sleep(1)
 if stable<3:write(a.out/'result.json',{'status':'GPU_GATE_NOT_RUN','pre_gpu':loads});return 4
 assert not subprocess.run(['lsof','-t','-nP','-iTCP:11243','-sTCP:LISTEN'],capture_output=True).stdout
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(trace),FLASH_SESSION_STATE_PROGRESS='1')
 command=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow','--serve','11243'];log=(a.out/'server.log').open('w');print('SERVER_START',stamp(),flush=True)
 proc=subprocess.Popen(command,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);cases=[];recoveries=[]
 try:
  end=time.monotonic()+120
  while time.monotonic()<end:
   if proc.poll() is not None:raise RuntimeError('server exited')
   try:
    with urllib.request.urlopen('http://127.0.0.1:11243/health',timeout=1):break
   except OSError:time.sleep(.1)
  else:raise TimeoutError('ready')
  for phase in ['prefill','decode']:
   sid='cancel-'+uuid.uuid4().hex;tag='cancel-'+uuid.uuid4().hex
   prompt=(' x'*128+'\nReply with a very long list of numbers.') if phase=='prefill' else 'Write a long detailed list of the integers from one to one hundred.'
   body=dict(model='qwen3.5',messages=[dict(role='user',content=prompt)],session_id=sid,flash_session_create=True,stream=True,temperature=0,reasoning_effort='off',max_tokens=256,flash_trace_id=tag)
   payload=json.dumps(body).encode();sock=socket.create_connection(('127.0.0.1',11243));sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(payload)).encode()+b'\r\n\r\n'+payload)
   try:
    observed=waitfile(trace/(tag+'-progress.json'),120,lambda x:(x['phase']=='prefill_nrow_poll' and x['polls']>=4) if phase=='prefill' else x['phase']=='decode')
   finally:
    sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));sock.close()
   closed=time.monotonic();abort=waitfile(trace/(tag+'-abort.json'),30);state=waitfile(trace/(tag+'-state.json'));aborted_ms=(time.monotonic()-closed)*1000
   assert state['end_position']==0 and not state['accepted'] and state['failed'],state
   start=time.monotonic()
   with urllib.request.urlopen('http://127.0.0.1:11243/health',timeout=3) as r:assert r.status==200
   health_ms=(time.monotonic()-start)*1000
   status,missing=request(dict(model='qwen3.5',session_id=sid,messages=[dict(role='user',content='Continue.')],max_tokens=1,reasoning_effort='off'))
   stale_status=status
   assert status==409 and missing.get('session_invalidated') and missing.get('resend_full_history'),(status,missing)
   recovery_tag='recover-'+uuid.uuid4().hex
   status,reply=request(dict(model='qwen3.5',session_id='fresh-'+uuid.uuid4().hex,flash_session_create=True,messages=[dict(role='user',content='Remember identifier STATE-73941. Reply exactly READY.')],max_tokens=24,temperature=0,reasoning_effort='off',flash_trace_id=recovery_tag))
   assert status==200,(status,reply)
   recovery=waitfile(trace/(recovery_tag+'-state.json'));assert recovery['accepted'] and recovery['history_complete']
   recoveries.append(recovery);cases.append(dict(phase=phase,observed=observed,abort=abort,invalidated=True,stale_status=stale_status,health_ms=health_ms,cancellation_ms=aborted_ms,recovery_end=recovery['end_position']))
  assert recoveries[0]['effective_token_ids']==recoveries[1]['effective_token_ids']
  assert [x['digest'] for x in recoveries[0]['steps']]==[x['digest'] for x in recoveries[1]['steps']]
 finally:
  proc.terminate();proc.wait(timeout=15);log.close();print('SERVER_STOP',stamp(),'exit',proc.returncode,flush=True)
 control=a.out/'control';control.mkdir();inputfile=a.out/'replay.json';write(inputfile,dict(token_ids=recoveries[-1]['effective_token_ids'],expected_digests={str(x['position']):x['digest'] for x in recoveries[-1]['steps']}))
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(control),FLASH_SESSION_REPLAY_INPUT=str(inputfile));print('RECOVERY_CONTROL_START',stamp(),flush=True)
 with (a.out/'control.log').open('w') as f:r=subprocess.run([str(binary),'--model',MODEL,'--tiered','--no-prefill-nrow'],cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 print('RECOVERY_CONTROL_STOP',stamp(),'exit',r.returncode,flush=True)
 write(a.out/'result.json',dict(status='PASS' if r.returncode==0 else 'FAIL',cases=cases,recovery_exact=r.returncode==0,pre_gpu=loads,binary_sha256=sha(binary),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()))
 return r.returncode
if __name__=='__main__':raise SystemExit(main())
