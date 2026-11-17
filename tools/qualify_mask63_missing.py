#!/usr/bin/env python3
"""Only missing short live release cases; frozen binary, no product changes.
Two sequential supervised processes. Never port11241 or external tool execution.
"""
import argparse,contextlib,datetime,hashlib,json,os,pathlib,re,socket,struct,threading,time,urllib.request,urllib.error,uuid
from supervise_qualified_serve import supervise,telemetry,HOST_MIN,RSS_MAX
from run_session_state_mission import MODEL,gpu
R=pathlib.Path(__file__).resolve().parents[1]
def stamp():return datetime.datetime.now().astimezone().isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(x,why):
 if not x:raise RuntimeError(why)
SYS={'role':'system','content':'You are a helpful assistant.'}
MODERATE=[SYS,{'role':'user','content':('Background labels: '+ ' amber birch cobalt delta'*40)+'. Ignore the labels. Reply exactly READY.'}]
TOOLS=[{'type':'function','function':{'name':'echo','description':'Echo the supplied synthetic payload.','parameters':{'type':'object','properties':{'payload':{'type':'string'}},'required':['payload'],'additionalProperties':False}}}]
def body(messages,sid=None,**kw):
 d=dict(model='qwen3.5',messages=messages,max_tokens=32,temperature=0,reasoning_effort='off')
 if sid:d.update(session_id=sid,flash_session_create=True)
 d.update(kw);return d
def wait_gpu(read_gpu=gpu,pause=time.sleep,limit=60):
 readings=[]
 for _ in range(limit):
  readings.append(read_gpu())
  if len(readings)>=3 and all(x is not None and 0<=x<30 for x in readings[-3:]):return readings
  pause(1)
 raise RuntimeError('GPU admission '+str(readings))

class Arm:
 def __init__(self,out,scalar=False,profile=None):
  self.out=out;self.scalar=scalar;self.profile=profile;self.stop=threading.Event();self.fault=threading.Event();self.result={};self.port=11249;self.thread=None
 def __enter__(self):
  readings=wait_gpu()
  self.readings=readings;(self.out.parent/(self.out.name+'-gpu-preflight.json')).write_text(json.dumps({'at':stamp(),'readings':readings})+'\n');env=os.environ.copy()
  for k in list(env):
   if k.startswith('FLASH_SESSION_TEST_') or k.startswith('FLASH_HTTP_QUALIFICATION'):env.pop(k)
  env.update(FLASH_SERVE_QUALIFIED_GPU_ONLY='1',FLASH_FE027_NUMERICS='63')
  command=[str(R/'metal_infer/infer-mask63-supervised-20261117'),'--model',MODEL,'--tiered','--no-prefill-nrow' if self.scalar else '--prefill-nrow','--serve',str(self.port)]
  if self.profile:command+=['--flash-profile',self.profile]
  def sample(pid):
   d=telemetry(R/'metal_infer/flash-serve-resource-probe',pid)
   # Do not mask genuine pressure behind the controlled test classification.
   if self.fault.is_set() and d['host_available_bytes']>=HOST_MIN and d['rss_bytes']<RSS_MAX:raise RuntimeError('CONTROLLED_EXTERNAL_TELEMETRY_LOSS')
   return d
  def run():self.result.update(supervise(command,env,self.out,sample,max_seconds=600,stop=self.stop))
  self.thread=threading.Thread(target=run);print('SERVER_START',stamp(),json.dumps(command),flush=True);self.thread.start()
  try:
   end=time.monotonic()+150
   while time.monotonic()<end:
    if (self.out/'child.log').exists() and '[serve] Ready' in self.log():return self
    require(self.thread.is_alive(),'supervisor stopped before ready '+str(self.result));time.sleep(.2)
   raise RuntimeError('ready timeout')
  except BaseException:
   self.__exit__(None,None,None);raise
 def log(self):return (self.out/'child.log').read_text(errors='replace')
 def __exit__(self,*args):
  self.stop.set();self.thread.join(15)
  print('SERVER_STOP',stamp(),self.result.get('exit'),self.result.get('stop_reason'),flush=True)
  require(not self.thread.is_alive(),'owned cleanup did not finish')
 def request(self,b):
  req=urllib.request.Request(f'http://127.0.0.1:{self.port}/v1/chat/completions',json.dumps(b).encode(),{'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=120) as res:code,reply=res.status,json.load(res)
  except urllib.error.HTTPError as e:code,reply=e.code,json.load(e)
  with (self.out/'responses.jsonl').open('a') as f:f.write(json.dumps({'request':b,'http_status':code,'response':reply})+'\n')
  return code,reply
 def health(self):
  with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health',timeout=5) as res:require(res.status==200,'health')
 def interrupt(self,b,external=False):
  b=dict(b,stream=True);data=json.dumps(b).encode();sock=socket.create_connection(('127.0.0.1',self.port),timeout=5);sock.settimeout(120)
  sock.sendall(b'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data)
  f=sock.makefile('rb');events=[];seen=False;start=None
  try:
   for line in f:
    if not line.startswith(b'data:'):continue
    raw=line[5:].strip()
    if raw==b'[DONE]':events.append('DONE');break
    e=json.loads(raw);events.append(e)
    if any(c.get('delta',{}).get('content') or c.get('delta',{}).get('reasoning_content') for c in e.get('choices',[])) and not seen:
     seen=True;start=time.monotonic()
     if external:self.fault.set()
     else:break
  finally:
   f.close()
   if not external:sock.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('ii',1,0))
   sock.close()
  require(seen,'did not enter decode')
  if external:
   self.thread.join(10);require(not self.thread.is_alive(),'external stop not prompt')
   require('DONE' not in events and not any(c.get('finish_reason') for e in events if isinstance(e,dict) for c in e.get('choices',[])),'external loss falsely finished')
   require(self.result.get('detail')=='CONTROLLED_EXTERNAL_TELEMETRY_LOSS','not a controlled telemetry interruption '+str(self.result))
  return {'visible_decode_observed':True,'elapsed_after_first_delta_seconds':time.monotonic()-start,'events':events,'done_seen':'DONE' in events}

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('--resume-report',type=pathlib.Path);a=p.parse_args();require(a.operator_exclusive_model,'exclusive window required');a.out.mkdir(parents=True,exist_ok=False)
 m=json.loads((a.out.parent/'candidate-manifest.json').read_text());binary=R/'metal_infer/infer-mask63-supervised-20261117';require(sha(binary)==m['binary_sha256'],'binary changed')
 for name,h in m['source_sha256'].items():require(sha(R/name)==h,'runtime source changed '+name)
 report={'status':'INCOMPLETE','started':stamp(),'binary_sha256':m['binary_sha256'],'source_sha':m['candidate_source_sha'],'cases':[],'production_access':False,'external_tools_executed':False,'arms':[]}
 def save():(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 def record(name,**fields):report['cases'].append(dict(case=name,status='PASS',**fields));save();print('CASE_PASS',name,flush=True)
 profile='release-final-canary';cp=list((R/'warm-state').glob('*flash-'+profile+'-*.state'));source=R/'warm-tools-cache'/('flash-'+profile+'-warm.json');require(cp and source.exists(),'canary02 profile evidence absent')
 old={str(x):sha(x) for x in [source,*cp]};report['profile_hashes_before']=old;interrupted_id=None
 previous=json.loads(a.resume_report.read_text()) if a.resume_report else None
 if previous:
  require(previous['source_sha']==m['candidate_source_sha'] and previous['binary_sha256']==m['binary_sha256'],'resume identity mismatch')
  known={x['case']:x for x in previous['cases'] if x['status']=='PASS'}
  require('persistent_restore_EOS_followup_exact32769_reject' in known and 'bounded_N128_prefill' in known,'resume lacks required passed cases')
  report['retained_report_sha256']=sha(a.resume_report)
 try:
  with Arm(a.out/'n128',profile=profile) as s:
   if previous:
    moderate=known['bounded_N128_prefill']['response']
   else:
    s.health();require('valid snapshot:' in s.log(),'persistent snapshot not restored')
    sid='missing-eos-'+uuid.uuid4().hex;initial=[SYS,{'role':'user','content':'Reply exactly READY.'}]
    code,first=s.request(body(initial,sid,flash_profile=profile));require(code==200 and first['choices'][0]['finish_reason']=='stop' and first['usage']['completion_tokens']<32,'natural EOS')
    require(first['flash_timings']['warm_prefix_reused'],'restored prefix not reused');logical=first['usage']['prompt_tokens']
    code,rejected=s.request(body(initial,'missing-over-'+uuid.uuid4().hex,flash_profile=profile,max_tokens=32769-logical));require(code==400,'exact32769 not rejected')
    code,follow=s.request(body([{'role':'user','content':'Reply exactly OK.'}],sid,flash_session_create=False,flash_profile=profile));require(code==200 and follow['flash_timings']['session_reused'] and follow['choices'][0]['finish_reason']=='stop','EOS subsequent turn/rejection preservation')
    require(all(sha(pathlib.Path(n))==h for n,h in old.items()),'profile source/checkpoint overwritten')
    record('persistent_restore_EOS_followup_exact32769_reject',logical_prompt_tokens=logical,reserved_generation=32769-logical,first=first,follow=follow,profile_files_unchanged=True)
    code,moderate=s.request(body(MODERATE,'missing-moderate-'+uuid.uuid4().hex));require(code==200 and moderate['usage']['prompt_tokens']>=128,'moderate prompt too small')
    require(any(int(x)>0 for x in re.findall(r'nrow_chunks=(\d+)',s.log())),'N128 path not exercised')
    record('bounded_N128_prefill',response=moderate)
   tool_sid='missing-tools-'+uuid.uuid4().hex;tool_messages=[SYS,{'role':'user','content':'Use echo once with payload exactly alpha. Do not answer without the tool.'}]
   code,tool=s.request(body(tool_messages,tool_sid,tools=TOOLS,max_tokens=96));require(code==200 and tool['choices'][0]['finish_reason']=='tool_calls','complete tool call missing')
   calls=tool['choices'][0]['message']['tool_calls'];require(len(calls)==1 and calls[0]['function']['name']=='echo' and json.loads(calls[0]['function']['arguments'])=={'payload':'alpha'},'invalid completed tool args')
   code,answer=s.request(body([{'role':'tool','tool_call_id':calls[0]['id'],'content':'Synthetic echo result: alpha. No external action executed.'}],tool_sid,flash_session_create=False,tools=TOOLS));require(code==200 and answer['flash_timings']['session_reused'],'tool result continuation')
   record('complete_tool_and_resident_result_followup',tool=tool,followup=answer)
   code,partial=s.request(body(tool_messages,'missing-partial-'+uuid.uuid4().hex,tools=TOOLS,max_tokens=1));require(code==200,'partial recovery transport')
   require(not partial['choices'][0]['message'].get('tool_calls'),'executable partial call returned')
   require(partial.get('session_invalidated') and partial.get('resend_full_history'),'partial tool recovery did not notify invalidation')
   record('partial_tool_not_executable_and_session_invalidated',response=partial)
   cancel_sid='missing-cancel-'+uuid.uuid4().hex;count=[SYS,{'role':'user','content':'Count from 1 to 1000, one number per line. Do not stop early.'}]
   log_offset=len(s.log());cut=s.interrupt(body(count,cancel_sid,max_tokens=128));begin=time.monotonic();s.health();code,_=s.request(body([{'role':'user','content':'Continue.'}],cancel_sid,flash_session_create=False));require(code==409,'cancelled session reusable')
   require(time.monotonic()-begin<5,'server not responsive after cancellation')
   cancel_log=s.log()[log_offset:]
   require('client disconnected during decode' in cancel_log or 'client disconnected, invalidating session' in cancel_log,'no active-decode cancellation evidence')
   generated=[int(n) for n in re.findall(r'generated=(\d+) tokens',cancel_log)]
   require(generated and generated[-1]<128,'decode did not stop before token limit')
   record('long_decode_disconnect_prompt_health_and_stale409',interrupt=cut,health_and_stale_seconds=time.monotonic()-begin)
   interrupted_id='missing-resource-'+uuid.uuid4().hex
   fault=s.interrupt(body(count,interrupted_id,max_tokens=128),external=True)
   record('external_controlled_telemetry_loss_during_decode',interrupt=fault,scope='External supervisor only; no real memory pressure; native fault-arm remains disabled')
  report['arms'].append(s.result);save()
  # A controlled test stop is intentional; any actual resource failure aborts here.
  require(s.result.get('detail')=='CONTROLLED_EXTERNAL_TELEMETRY_LOSS','refusing restart after actual resource failure')
  with Arm(a.out/'scalar',scalar=True) as control:
   code,_=control.request(body([{'role':'user','content':'Continue.'}],interrupted_id,flash_session_create=False));require(code==409,'old process session survived restart')
   code,scalar=control.request(body(MODERATE,'missing-scalar-'+uuid.uuid4().hex));require(code==200,'scalar control request')
   def normalized(x):return (x['choices'][0]['message'],x['choices'][0]['finish_reason'],x['usage'])
   require(normalized(moderate)==normalized(scalar),'scalar/N128 visible result or token counts differ')
   require(all(int(x)==0 for x in re.findall(r'nrow_chunks=(\d+)',control.log())),'scalar flag did not select scalar prefill')
   record('clean_new_process_stale409_scalar_N128_visible_agreement',scalar=scalar,scope='Same exact input messages and greedy controls; visible output/usage agreement, not new hidden/logit/state tensor comparison')
  report['arms'].append(control.result);report['status']='PASS'
 except Exception as e:
  report.update(status='FAIL',error=str(e))
  if 's' in locals() and s.result and s.result not in report['arms']:report['arms'].append(s.result)
  if 'control' in locals() and control.result and control.result not in report['arms']:report['arms'].append(control.result)
  for phase in ['n128','scalar']:
   result_path=a.out/phase/'result.json'
   if result_path.exists():
    arm_result=json.loads(result_path.read_text())
    if arm_result not in report['arms']:report['arms'].append(arm_result)
  native_resource_abort=any(path.exists() and '[serve-resource] request aborted reason=' in path.read_text(errors='replace') for path in [a.out/'n128/child.log',a.out/'scalar/child.log'])
  if native_resource_abort or any(x.get('stop_reason') in ['host_reserve','process_rss'] or x.get('status')=='BLOCKED' for x in report['arms']):report['status']='BLOCKED_RESOURCE'
 finally:report['ended']=stamp();save();print('MISSING_RESULT',report['status'],report.get('error'),flush=True)
 return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
