#!/usr/bin/env python3
"""Short isolated live admission/resident/cancellation check under the owned supervisor."""
import argparse,datetime,hashlib,json,os,pathlib,re,socket,struct,subprocess,threading,time,urllib.request,urllib.error,uuid
from supervise_qualified_serve import supervise,telemetry
from run_session_state_mission import MODEL,gpu
R=pathlib.Path(__file__).resolve().parents[1]
def stamp():return datetime.datetime.now().astimezone().isoformat()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--operator-exclusive-model',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive model window required')
 a.out.mkdir(parents=True,exist_ok=False);port=11248;binary=R/'metal_infer/infer-c11-live-resource-fault';probe=R/'metal_infer/flash-serve-resource-probe';stop=threading.Event();result={};env=os.environ.copy();env.update(FLASH_SERVE_QUALIFIED_GPU_ONLY='1',FLASH_FE027_NUMERICS='63',FLASH_HTTP_QUALIFICATION='1',FLASH_SESSION_TEST_SYSTEM_TEXT='You are a helpful assistant. /think',FLASH_SESSION_TEST_CACHE_ROOT=str(a.out/'cache'),FLASH_SESSION_TEST_RESOURCE_ARM=str(a.out/'resource.arm'))
 readings=[]
 for _ in range(3):readings.append(gpu());time.sleep(1)
 if any(x is None or x>=30 for x in readings):raise RuntimeError('GPU gate '+str(readings))
 report=dict(started=stamp(),gpu=readings,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),cases=[],status='INCOMPLETE',production_access=False)
 command=[str(binary),'--model',MODEL,'--tiered','--prefill-nrow','--serve',str(port)]
 def run():result.update(supervise(command,env,a.out/'server',lambda pid:telemetry(probe,pid),max_seconds=300,stop=stop))
 print('SERVER_START',stamp(),command,flush=True);thread=threading.Thread(target=run);thread.start()
 def request(body):
  req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',json.dumps(body).encode(),{'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=30) as res:return res.status,json.load(res)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def require(x,why):
  if not x:raise RuntimeError(why)
 sid='c11-'+uuid.uuid4().hex
 def body(msg,create=False):return dict(model='qwen3.5',messages=msg,session_id=sid,flash_session_create=create,max_tokens=8,temperature=0,reasoning_effort='off')
 initial=[dict(role='system',content='You are a helpful assistant.'),dict(role='user',content='Reply exactly READY.')]
 try:
  end=time.monotonic()+120
  while time.monotonic()<end:
   log=a.out/'server/child.log'
   if log.exists() and '[serve] Ready' in log.read_text(errors='replace'):break
   if not thread.is_alive():raise RuntimeError('supervisor stopped before ready: '+str(result))
   time.sleep(.1)
  else:raise RuntimeError('ready timeout')
  report['ready']=stamp();print('SERVER_READY',report['ready'],flush=True)
  fresh=body(initial,True);code,count=request(dict(fresh,flash_qual_count_only=True,flash_qual_hash=True));require(code==200,'count fresh')
  total=count['context_tokens'];code,rejected=request(dict(fresh,max_tokens=32769-total));require(code==400,'fresh32769 reject')
  code,reply=request(dict(fresh,max_tokens=32768-total));require(code==200,'fresh32768 accept');report['cases'].append(dict(case='fresh32768_accept_32769_reject',status='PASS',logical_prompt_tokens=total,completion_tokens=reply['usage']['completion_tokens']))
  follow=body([dict(role='user',content='Reply exactly READY.')]);code,before=request(dict(follow,flash_qual_count_only=True,flash_qual_hash=True));require(code==200 and before['session_reused'],'resident count')
  for _ in range(3):
   code,_=request(dict(follow,max_tokens=32769-before['context_tokens']));require(code==400,'resident overlimit')
  code,after=request(dict(follow,flash_qual_count_only=True,flash_qual_hash=True));require(code==200,'post rejection count')
  require(all(before[k]==after[k] for k in ['resident_pos','kv_lengths','state_hash']),'resident state changed after rejected request')
  require(before['state_hash']!='not_requested','real state hash unavailable')
  code,_=request(dict(follow,max_tokens=32768-before['context_tokens']));require(code==200,'resident32768 acceptance')
  report['cases'].append(dict(case='resident_rejections_and_boundary_recovery',status='PASS',before=before,after=after))
  # Start a genuinely generating SSE turn, then reset its owned client socket.
  payload=body([dict(role='user',content='Count from 1 to 1000, one number per line. Do not stop early.')]);payload.update(stream=True,max_tokens=128)
  data=json.dumps(payload).encode();sock=socket.create_connection(('127.0.0.1',port));sock.settimeout(30);sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)
  file=sock.makefile('rb');entered=False
  for line in file:
   if line.startswith(b'data:'):
    raw=line[5:].strip()
    if raw==b'[DONE]':break
    e=json.loads(raw)
    if any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in e.get('choices',[])):entered=True;break
  require(entered,'did not enter decode');file.close();sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0));sock.close();time.sleep(.5)
  code,_=request(follow);require(code==409,'cancelled resident session reusable')
  sid='c11-recovery-'+uuid.uuid4().hex;code,_=request(body(initial,True));require(code==200,'fresh recovery failed')
  report['cases'].append(dict(case='decode_disconnect_stale409_fresh_recovery',status='PASS'))
  # Controlled telemetry failure after visible decode; no real memory pressure.
  fault=body([dict(role='user',content=('Background context. '*100)+'Count from 1 to 1000, one number per line. Do not stop early.')]);fault.update(stream=True,max_tokens=128)
  req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',json.dumps(fault).encode(),{'Content-Type':'application/json'})
  armed=False;error_seen=False;done=False;successful_finish=False
  with urllib.request.urlopen(req,timeout=30) as response:
   for line in response:
    if not line.startswith(b'data:'):continue
    raw=line[5:].strip()
    if raw==b'[DONE]':done=True;break
    event=json.loads(raw)
    if event.get('error'):
     error_seen=bool(event.get('session_invalidated') and event.get('resend_full_history'))
    for choice in event.get('choices',[]):
     if choice.get('finish_reason') is not None:successful_finish=True
     if not armed and (choice.get('delta',{}).get('content') or choice.get('delta',{}).get('reasoning_content')):
      (a.out/'resource.arm').write_text('one controlled telemetry fault');armed=True
  require(armed and error_seen and done and not successful_finish,'resource fault must end in error/DONE without success')
  code,_=request(follow);require(code==409,'resource-aborted resident reusable')
  sid='c11-resource-recovery-'+uuid.uuid4().hex;code,_=request(body(initial,True));require(code==200,'resource failure fresh recovery')
  report['cases'].append(dict(case='controlled_telemetry_failure_during_decode_error_DONE_stale409_recovery',status='PASS',actual_pressure_induced=False))
  report['status']='PASS'
 except Exception as e:report['error']=str(e);report['status']='BLOCKED_RESOURCE' if result.get('stop_reason') or result.get('status')=='BLOCKED' else 'FAIL'
 finally:
  stop.set();thread.join(10);report['supervisor']=result;report['ended']=stamp();(a.out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print('SERVER_STOP',report['ended'],result.get('exit'),result.get('stop_reason'),flush=True);print('LIVE_RESULT',report['status'],report.get('error'),flush=True)
 return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
