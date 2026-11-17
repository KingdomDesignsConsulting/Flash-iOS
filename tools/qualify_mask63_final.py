#!/usr/bin/env python3
"""Short production-binary canary. No diagnostic overrides, no production port."""
import argparse,datetime,json,os,pathlib,subprocess,threading,time,urllib.request,urllib.error,uuid,hashlib,socket,struct
from supervise_qualified_serve import supervise,telemetry
from run_session_state_mission import MODEL,gpu
R=pathlib.Path(__file__).resolve().parents[1]
def stamp():return datetime.datetime.now().astimezone().isoformat()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--operator-exclusive-model',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive window required')
 a.out.mkdir(parents=True,exist_ok=False);binary=R/'metal_infer/infer-mask63-supervised-20261117';probe=R/'metal_infer/flash-serve-resource-probe';port=11248
 manifest=json.loads((a.out.parent/'candidate-manifest.json').read_text())
 if hashlib.sha256(binary.read_bytes()).hexdigest()!=manifest['binary_sha256']:raise RuntimeError('binary identity changed')
 for name,expected in manifest['source_sha256'].items():
  path=pathlib.Path(name)
  if path.is_absolute() or '..' in path.parts or hashlib.sha256((R/path).read_bytes()).hexdigest()!=expected:raise RuntimeError('runtime source/dependency changed: '+name)
 readings=[]
 for _ in range(3):readings.append(gpu());time.sleep(1)
 if any(x is None or not 0<=x<30 for x in readings):raise RuntimeError('GPU gate '+str(readings))
 env=os.environ.copy()
 for k in list(env):
  if k.startswith('FLASH_SESSION_TEST_') or k.startswith('FLASH_HTTP_QUALIFICATION'):env.pop(k)
 env.update(FLASH_SERVE_QUALIFIED_GPU_ONLY='1',FLASH_FE027_NUMERICS='63')
 report={'status':'INCOMPLETE','started':stamp(),'gpu':readings,'binary_sha256':manifest['binary_sha256'],'source_sha':manifest['candidate_source_sha'],'cases':[],'production_access':False}
 stop=threading.Event();result={};command=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow','--serve',str(port)]
 def serve():result.update(supervise(command,env,a.out/'server',lambda pid:telemetry(probe,pid),max_seconds=600,stop=stop))
 t=threading.Thread(target=serve);print('SERVER_START',stamp(),command,flush=True);t.start()
 def check(condition,why):
  if not condition:raise RuntimeError(why)
 def request(body):
  req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=90) as res:return res.status,json.load(res)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 sid='release-'+uuid.uuid4().hex;profile='release-final-canary'
 initial=[{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':'Reply exactly READY.'}]
 def body(messages,create=False):return dict(model='qwen3.5',messages=messages,session_id=sid,flash_session_create=create,flash_profile=profile,max_tokens=8,temperature=0)
 try:
  end=time.monotonic()+150
  while time.monotonic()<end:
   log=a.out/'server/child.log'
   if log.exists() and '[serve] Ready' in log.read_text(errors='replace'):break
   if not t.is_alive():raise RuntimeError('server did not become ready: '+str(result))
   time.sleep(.2)
  else:raise RuntimeError('readiness timeout')
  with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as h:check(h.status==200,'health')
  report['ready']=stamp();report['cases'].append({'case':'cold_start_health','status':'PASS'})
  code,first=request(body(initial,True));check(code==200 and all(k in first.get('usage',{}) for k in ['prompt_tokens','completion_tokens','total_tokens']),'buffered usage')
  logical=first['usage']['prompt_tokens'];report['cases'].append({'case':'buffered_usage','status':'PASS','usage':first['usage'],'timings':first.get('flash_timings')})
  # Rejection must leave the existing completed resident session reusable.
  follow=body([{'role':'user','content':'Reply exactly OK.'}]);code,_=request(dict(follow,max_tokens=32769));check(code==400,'32769 reject')
  req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',json.dumps(dict(follow,stream=True,stream_options={'include_usage':True})).encode(),{'Content-Type':'application/json'})
  events=[]
  with urllib.request.urlopen(req,timeout=90) as res:
   for line in res:
    if not line.startswith(b'data:'):continue
    raw=line[5:].strip()
    if raw==b'[DONE]':events.append('DONE');break
    events.append(json.loads(raw))
  check(events and events[-1]=='DONE','stream DONE missing')
  usage=[(i,e['usage']) for i,e in enumerate(events[:-1]) if isinstance(e,dict) and e.get('usage')]
  check(bool(usage) and usage[-1][0]<len(events)-1,'usage must precede DONE')
  timings=[e['flash_timings'] for e in events[:-1] if e.get('flash_timings')]
  check(timings and timings[-1]['session_reused'],'resident survived rejection')
  report['cases'].append({'case':'resident_after_rejection_stream_usage_before_DONE','status':'PASS','usage':usage[-1][1],'timings':timings[-1]})
  # Reserve exactly32K and cancel only after a real decode delta; bounded output.
  sid='release-budget-'+uuid.uuid4().hex
  payload=dict(body(initial,True),max_tokens=32768-logical,stream=True);data=json.dumps(payload).encode()
  sock=socket.create_connection(('127.0.0.1',port),timeout=5);sock.settimeout(90)
  sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)
  f=sock.makefile('rb');entered=False
  for line in f:
   if line.startswith(b'data:') and line[5:].strip()!=b'[DONE]':
    e=json.loads(line[5:])
    if any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in e.get('choices',[])):entered=True;break
  f.close();sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));sock.close();check(entered,'exact32K admission did not decode')
  time.sleep(.5);code,_=request(body([{'role':'user','content':'Continue.'}]))
  check(code==409,'cancelled session reusable')
  sid='release-recovery-'+uuid.uuid4().hex;code,recovered=request(body(initial,True));check(code==200,'fresh recovery')
  report['cases'].append({'case':'exact32768_budget_decode_cancel_stale409_fresh_recovery','status':'PASS','logical_prompt_tokens':logical,'reserved_generation':32768-logical,'usage':recovered['usage']})
  report['status']='PASS'
 except Exception as e:
  report['status']='FAIL';report['error']=str(e)
 finally:
  stop.set();t.join(15);report['supervisor']=result;report['ended']=stamp()
  if t.is_alive():report['status']='FAIL';report['error']='owned supervisor cleanup did not finish'
  if result.get('stop_reason') not in [None,'operator_cancel'] or result.get('status')=='BLOCKED':report['status']='BLOCKED_RESOURCE'
  (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('SERVER_STOP',report['ended'],result.get('exit'),result.get('stop_reason'),flush=True);print('CANARY_RESULT',report['status'],report.get('error'),flush=True)
 return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
