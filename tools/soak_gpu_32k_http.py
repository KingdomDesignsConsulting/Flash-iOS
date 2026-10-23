#!/usr/bin/env python3
"""Real HTTP qualification, normal malloc cache/prefetch, guarded memory use."""
import argparse, copy, datetime, hashlib, json, os, pathlib, signal, socket, subprocess, threading, time, shutil, urllib.request, urllib.error
from benchmark_gpu_16k import samples
P=pathlib.Path
MODEL='/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def request(url,payload=None,timeout=180):
 req=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
def payload(messages,session=None,max_tokens=24,stream=False):
 d=dict(model='qwen3.5',messages=copy.deepcopy(messages),max_tokens=max_tokens,temperature=0,reasoning_effort='off',stream=stream)
 if session:d['session_id']=session
 if stream:d['stream_options']={'include_usage':True}
 return d
def canonical(body):
 m=body['choices'][0]['message']
 return {k:m.get(k,'') for k in ('content','reasoning_content')}
def stream_request(url,body,timeout):
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 chunks=[];text={'content':'','reasoning_content':''};done=False
 with urllib.request.urlopen(req,timeout=timeout) as r:
  assert r.headers.get_content_type()=='text/event-stream'
  for raw in r:
   line=raw.decode().strip()
   if not line.startswith('data:'):continue
   value=line[5:].strip()
   assert not done,'SSE data after DONE'
   if value=='[DONE]':done=True;continue
   c=json.loads(value);assert 'error' not in c,c;chunks.append(c)
   for choice in c.get('choices',[]):
    for k in text:text[k]+=choice.get('delta',{}).get(k,'')
 assert done and chunks and chunks[-1].get('usage'),'Missing usage before DONE'
 assert any(c.get('choices') and c['choices'][0].get('finish_reason') for c in chunks)
 return dict(choices=[dict(message=text)],usage=chunks[-1]['usage'],flash_timings=next(c['flash_timings'] for c in reversed(chunks) if 'flash_timings' in c),sse_chunks=chunks)
class Server:
 def __init__(self,repo,out,arm,model=MODEL,extra=(),memory_gib=12,work_project=None):
  self.repo,self.out,self.arm,self.model,self.extra,self.memory_gib=repo,out,arm,model,extra,memory_gib
  self.work_project=work_project
  self.records=[];self.memory=[];self.stop=threading.Event();self.failure=None
 def __enter__(self):
  self.out.mkdir(parents=True,exist_ok=True)
  readings=samples();deadline=time.monotonic()+90
  while any(x is None or x>=30 for x in readings) and time.monotonic()<deadline:time.sleep(2);readings=samples()
  assert all(x is not None and x<30 for x in readings),readings
  self.probe=self.out/'memory-probe'
  subprocess.run(['clang','-O2',str(self.repo/'tools/http_memory_probe.c'),'-lproc','-o',str(self.probe)],check=True)
  with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
  self.url=f'http://127.0.0.1:{self.port}'
  exe_dir=self.repo/'metal_infer'
  if self.work_project:
   exe_dir=self.work_project/'metal_infer';exe_dir.mkdir(parents=True,exist_ok=True)
   shutil.copy2(self.repo/'metal_infer'/f'infer-{self.arm}-experiment',exe_dir/f'infer-{self.arm}-experiment')
   for name in ('shaders.metal','gguf_iq_shared.h','prefill_probe'):
    if not (exe_dir/name).exists():(exe_dir/name).symlink_to(self.repo/'metal_infer'/name,target_is_directory=name=='prefill_probe')
  self.command=[str(exe_dir/f'infer-{self.arm}-experiment'),'--model',self.model,'--tiered','--cache-telemetry','--serve',str(self.port),*self.extra]
  self.log=(self.out/'server.log').open('w');self.started=datetime.datetime.now().astimezone().isoformat()
  print('SERVER_START',self.started,self.arm,' '.join(self.command),flush=True)
  self.proc=subprocess.Popen(self.command,cwd=exe_dir,stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,FLASH_TRACE_GPU_KV_BOUNDARY='1',FLASH_HTTP_QUALIFICATION='1'))
  def monitor():
   while not self.stop.wait(1):
    r=subprocess.run([str(self.probe),str(self.proc.pid)],capture_output=True,text=True)
    if r.returncode:continue
    m=json.loads(r.stdout);m['time']=time.time();self.memory.append(m)
    if m['physical_bytes']>self.memory_gib*2**30 or m['rss_bytes']>16*2**30:
     self.failure='memory stop threshold exceeded';os.killpg(self.proc.pid,signal.SIGTERM);return
  self.thread=threading.Thread(target=monitor,daemon=True);self.thread.start()
  try:
   deadline=time.monotonic()+180
   while time.monotonic()<deadline:
    if self.proc.poll() is not None:raise RuntimeError(f'Startup exit={self.proc.returncode}, {self.failure}')
    try:
     code,b=request(self.url+'/health',timeout=2)
     if code==200:break
    except (OSError,ValueError):pass
    time.sleep(.5)
   else:raise TimeoutError('startup timeout')
   return self
  except BaseException as exc:
   self.__exit__(type(exc),exc,exc.__traceback__);raise
 def chat(self,label,body,timeout=240):
  begin=time.monotonic()
  if body.get('stream'):code,b=200,stream_request(self.url+'/v1/chat/completions',body,timeout)
  else:code,b=request(self.url+'/v1/chat/completions',body,timeout)
  row=dict(label=label,status=code,seconds=time.monotonic()-begin,request=body,response=b);self.records.append(row)
  (self.out/'requests.json').write_text(json.dumps(self.records,indent=2))
  assert code==200,(label,code,b)
  assert b.get('choices') and b.get('usage') and b.get('flash_timings'),b
  assert b['usage']['total_tokens']==b['usage']['prompt_tokens']+b['usage']['completion_tokens']
  assert b['usage']['completion_tokens']>0
  assert not canonical(b)['reasoning_content'],f'reasoning_effort off ignored: {canonical(b)}'
  assert canonical(b)['content'],f'Vacuous empty completion: {b}'
  print(self.arm,label,'%.2fs'%row['seconds'],repr(canonical(b)),flush=True)
  return b
 def __exit__(self,*args):
  self.stop.set();self.thread.join(timeout=3)
  if self.proc.poll() is None:
   os.killpg(self.proc.pid,signal.SIGTERM)
   try:self.proc.wait(timeout=15)
   except subprocess.TimeoutExpired:os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait();self.failure='forced SIGKILL'
  self.log.close();self.ended=datetime.datetime.now().astimezone().isoformat()
  result=dict(command=self.command,started=self.started,ended=self.ended,exit=self.proc.returncode,memory=self.memory,failure=self.failure,requests=self.records,binary_sha256=sha(P(self.command[0])))
  (self.out/'report.json').write_text(json.dumps(result,indent=2))
  print('SERVER_STOP',self.ended,self.arm,'exit',self.proc.returncode,flush=True)
  if not args or args[0] is None:assert self.proc.returncode in (0,-signal.SIGTERM) and not self.failure,result
  with socket.socket() as s:assert s.connect_ex(('127.0.0.1',self.port))!=0,'orphan listener'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1]);ap.add_argument('--out',type=P,required=True);ap.add_argument('--rounds',type=int,default=3);ap.add_argument('--build',action='store_true');a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=False)
 if a.build:
  with (a.out/'build.log').open('w') as f:subprocess.run(['make','-C','metal_infer','lazy16k-experiment','lazy32k-experiment'],cwd=a.repo,stdout=f,stderr=subprocess.STDOUT,check=True)
 outputs={}
 for arm in ('lazy16k','lazy32k'):
  with Server(a.repo,a.out/arm,arm) as server:
   assert request(server.url+'/v1/models')[1]['data'][0]['id']=='qwen3.5'
   base=[dict(role='system',content='Answer briefly. Do not explain your reasoning.'),dict(role='user',content='Reply with exactly ORBIT.')]
   first=server.chat('nonstream',payload(base));outputs[arm]=[canonical(first)]
   streamed=server.chat('stream',payload(base,stream=True));assert canonical(streamed)==canonical(first)
   for cycle in range(a.rounds):
    histories={key:[dict(role='system',content='Answer briefly.'),dict(role='user',content=f'Remember my code word is {word}. Reply with that word only.')] for key,word in [('A','SATURN'),('B','NEPTUNE'),('C','VENUS')]}
    for key in ('A','B','A','C','B','A'):
     history=histories[key]
     if history[-1]['role']!='user':history.append(dict(role='user',content='Reply with my code word only.'))
     body=payload(history,'http-soak-'+key)
     b=server.chat(f'{cycle}-switch-{key}',body)
     assert not b['flash_timings']['session_reused']
     history.append(dict(role='assistant',content=canonical(b)['content']))
     turn=dict(role='user',content='What is my code word? Reply with that word only.')
     c=server.chat(f'{cycle}-continue-{key}',payload([turn],'http-soak-'+key))
     assert c['flash_timings']['session_reused']
     # Invalid request must not corrupt the resident session.
     assert request(server.url+'/v1/chat/completions',dict(body,session_id=123))[0]==400
     history.append(turn)
     ref=server.chat(f'{cycle}-stateless-reference-{key}',payload(history))
     # Canonical history strips historical thinking markers; its raw token
     # transcript differs from resident KV. Compare exact resident replays instead.
     rb=server.chat(f'{cycle}-replay-start-{key}',body);assert canonical(rb)==canonical(b)
     rc=server.chat(f'{cycle}-replay-delta-{key}',payload([turn],'http-soak-'+key))
     assert canonical(rc)==canonical(c),(canonical(rc),canonical(c))
     outputs[arm].append(canonical(c));history.append(dict(role='assistant',content=canonical(c)['content']))
   # Replayed full history must be deterministic after stateless replacement.
   replay=server.chat('full-replay',payload(base,'http-replay'));assert canonical(replay)==canonical(first)
  memories=server.memory
  assert memories and max(x['physical_bytes'] for x in memories)<12*2**30
 assert outputs['lazy16k']==outputs['lazy32k'],'16K/32K short greedy output mismatch'
 (a.out/'summary.json').write_text(json.dumps(dict(result='PASS',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.repo,text=True).strip(),cross_arm_greedy_equal=True,rounds=a.rounds),indent=2))
 print('PASS',a.out,flush=True)
if __name__=='__main__':main()
