"""Shared isolated HTTP qualification helpers; no production requests."""
import contextlib,json,os,pathlib,socket,struct,subprocess,time,urllib.request,urllib.error,uuid
from run_session_state_mission import MODEL,gpu,stamp,sha
P=pathlib.Path
REPO=P(__file__).resolve().parents[1]
BINARY=REPO/'metal_infer/infer-session-state-experiment'
SYS={'role':'system','content':'You are a helpful assistant.'}
USER={'role':'user','content':'Remember identifier STATE-73941. Reply exactly READY.'}
FOLLOW={'role':'user','content':'What identifier did I give? Reply only the identifier.'}
def write(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n')
def load(p):return json.loads(p.read_text())
def waitfile(p,timeout=20):
 end=time.monotonic()+timeout
 while not p.exists() and time.monotonic()<end:time.sleep(.02)
 return load(p)
def gate():
 stable=0;values=[]
 for _ in range(10):
  n=gpu();values.append(n);stable=stable+1 if n is not None and n<30 else 0
  if stable==3:return values
  time.sleep(1)
 raise RuntimeError('GPU_GATE_NOT_RUN '+str(values))
def body(messages,sid,create=False,profile=None):
 b=dict(model='qwen3.5',messages=messages,session_id=sid,stream=False,max_tokens=24,temperature=0,reasoning_effort='off',flash_trace_id='gate-'+uuid.uuid4().hex)
 if create:b['flash_session_create']=True
 if profile:b['flash_profile']=profile
 return b
def call(b,half_close=False):
 if half_close:
  data=json.dumps(b).encode();s=socket.create_connection(('127.0.0.1',11243));s.settimeout(120)
  s.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data);s.shutdown(socket.SHUT_WR);raw=b''
  while True:
   chunk=s.recv(65536)
   if not chunk:break
   raw+=chunk
  s.close();head,payload=raw.split(b'\r\n\r\n',1);status=int(head.split()[1]);return status,json.loads(payload)
 req=urllib.request.Request('http://127.0.0.1:11243/v1/chat/completions',json.dumps(b).encode(),{'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=120) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def state(server,b):return waitfile(server['trace']/(b['flash_trace_id']+'-state.json'))
def equal(a,b):
 assert a['effective_token_ids']==b['effective_token_ids']
 assert a['end_position']==b['end_position']
 start=max(a['initial_position'],b['initial_position'])
 left={x['position']:x['digest'] for x in a['steps'] if x['position']>=start}
 right={x['position']:x['digest'] for x in b['steps'] if x['position']>=start}
 assert left==right and a['end_position'] in left
 assert a['accepted'] and b['accepted']
@contextlib.contextmanager
def server(out,cache=None,args=(),env_extra=None,binary=BINARY):
 out.mkdir(parents=True,exist_ok=False);trace=out/'trace';trace.mkdir();loads=gate()
 for port in [11241,11243]:assert not subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True).stdout,'MODEL_PORT_BUSY_NOT_RUN'
 env=dict(os.environ,FLASH_SESSION_TOKEN_TRACE_DIR=str(trace),**(env_extra or {}))
 if cache:env['FLASH_SESSION_TEST_CACHE_ROOT']=str(cache)
 cmd=[str(binary),'--model',MODEL,'--tiered','--no-prefill-nrow','--serve','11243',*args]
 write(out/'launch.json',dict(started=stamp(),command=cmd,pre_gpu=loads,binary_sha256=sha(binary),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),test_environment={k:v for k,v in env.items() if k.startswith('FLASH_SESSION_')}))
 print('SERVER_START',stamp(),out.name,flush=True);log=(out/'server.log').open('w');proc=subprocess.Popen(cmd,cwd=binary.parent,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 try:
  end=time.monotonic()+120
  while time.monotonic()<end:
   if proc.poll() is not None:raise RuntimeError('server exited '+str(proc.returncode))
   try:
    with urllib.request.urlopen('http://127.0.0.1:11243/health',timeout=1):break
   except OSError:time.sleep(.1)
  else:raise TimeoutError('server ready')
  yield dict(out=out,trace=trace)
 finally:
  proc.terminate();proc.wait(timeout=15);log.close();print('SERVER_STOP',stamp(),out.name,'exit',proc.returncode,flush=True)
