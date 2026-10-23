#!/usr/bin/env python3
"""Production-validated profile recovery and real HTTP long-session qualification.
No standalone qualification fixture is imported. Progress is a client transcript;
after server loss, resuming replays it through normal HTTP, not a KV back door.
"""
import argparse,json,os,pathlib,re,shutil,tempfile,time
from soak_gpu_32k_http import Server,request,payload,canonical
P=pathlib.Path
SYSTEM='Answer briefly. Do not explain your reasoning.'
def save(path,value):
 tmp=path.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
 fd=os.open(path.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def observe(s,sid=None,hash_state=False):
 b=payload([dict(role='user',content='Count only.')],sid,max_tokens=4)
 b.update(flash_qual_count_only=True,flash_qual_hash=hash_state)
 code,d=request(s.url+'/v1/chat/completions',b)
 assert code==200 and 'kv_lengths' in d,d
 assert len(d['kv_lengths'])==10 and all(n==d['resident_pos'] for n in d['kv_lengths'].values()),d
 return d
def cache_and_state(repo,out,project,name):
 base=[dict(role='system',content=SYSTEM),dict(role='user',content='Reply exactly ORBIT.')]
 body=payload(base,'state-A');body['flash_profile']=name
 evidence={}
 with Server(repo,out/'cache-capture','lazy32k',work_project=project) as s:
  first=s.chat('capture',body)
  before=observe(s,'state-A',True)
  assert request(s.url+'/v1/chat/completions',dict(body,session_id=123))[0]==400
  assert observe(s,'state-A',True)['state_hash']==before['state_hash']
  turn=dict(role='user',content='Reply exactly MOON.')
  original=s.chat('delta',payload([turn],'state-A'));state=observe(s,'state-A',True)
  s.chat('interspersed-stateless',payload(base))
  replay=s.chat('replay-anchor',body);assert canonical(replay)==canonical(first)
  again=s.chat('replay-delta',payload([turn],'state-A'));restored=observe(s,'state-A',True)
  assert canonical(again)==canonical(original) and restored['state_hash']==state['state_hash'],(state,restored)
  evidence['resident_replay']=dict(before=state,after=restored,exact=True)
  for i in range(6):
   m=[dict(role='system',content=SYSTEM+f' Reference number {i}.'),base[1]]
   b=payload(m);b['flash_profile']=name+f'-evict{i}';s.chat('prefix-eviction-'+str(i),b)
  recovered=s.chat('profile-reload-after-eviction',body)
  assert canonical(recovered)==canonical(first) and recovered['flash_timings']['warm_prefix_reused']
 pattern=re.compile(r'.*flash-'+re.escape(name)+r'-[0-9a-f]{16}\.state(?:\.zstd)?$')
 files=[p for p in (project/'warm-state').iterdir() if pattern.fullmatch(p.name)]
 assert files,'No production checkpoint created'
 selected=next((p for p in files if p.name.endswith('.zstd')),files[0])
 backup=project/'valid-checkpoint-backup';shutil.copy2(selected,backup)
 evidence['checkpoint']=dict(path=str(selected),bytes=selected.stat().st_size)
 with selected.open('r+b') as f:f.write(b'BROKEN!!');f.flush();os.fsync(f.fileno())
 with Server(repo,out/'cache-invalid-recovery','lazy32k',extra=('--flash-profile',name),work_project=project) as s:
  b=s.chat('recovered-after-corruption',dict(payload(base),flash_profile=name));assert canonical(b)==canonical(first)
 assert 'cache invalid' in (out/'cache-invalid-recovery/server.log').read_text(),'Invalid checkpoint not rejected'
 with Server(repo,out/'cache-valid-restore','lazy32k',extra=('--flash-profile',name),work_project=project) as s:
  b=s.chat('valid-restart',dict(payload(base),flash_profile=name));assert canonical(b)==canonical(first)
  assert b['flash_timings']['warm_prefix_reused']
 log=(out/'cache-valid-restore/server.log').read_text()
 assert '[warm-state] valid snapshot:' in log,'No normal persistent-state restore observed'
 evidence['invalid_recovery']=True;evidence['valid_restore']=True
 (out/'cache-state-report.json').write_text(json.dumps(evidence,indent=2))
def fit(s,history,sid,target):
 # Real reference text, with single-token padding to obtain exact active lengths.
 def make(lines,pad):
  content=('Reference record: the mission code is ORBIT.\n'*lines)+(' x'*pad)+'\nReply exactly OK.'
  msg=dict(role='user',content=content)
  return history+[msg],msg
 def count(lines,pad):
  messages,msg=make(lines,pad);b=payload(messages,sid,max_tokens=4)
  b['flash_qual_count_only']=True
  code,d=request(s.url+'/v1/chat/completions',b);assert code==200,d
  return d['context_tokens']
 lo,hi=0,max(0,target//5)
 assert count(0,0)<=target,('target too close',target,count(0,0))
 while lo<hi:
  mid=(lo+hi+1)//2
  if count(mid,0)<=target:lo=mid
  else:hi=mid-1
 lines=lo;lo,hi=0,128
 while lo<hi:
  mid=(lo+hi)//2
  if count(lines,mid)<target:lo=mid+1
  else:hi=mid
 assert count(lines,lo)==target,('cannot fit exact target',target,count(lines,lo))
 return make(lines,lo)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=P,required=True);ap.add_argument('--repo',type=P,default=P(__file__).resolve().parents[1]);ap.add_argument('--target',type=int,default=32767);ap.add_argument('--chunk',type=int,default=2048);ap.add_argument('--resume',action='store_true');ap.add_argument('--skip-cache-tests',action='store_true');a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=a.resume);progress=a.out/'progress.json'
 if a.resume:
  journal=json.loads(progress.read_text());project=P(journal['project']);name=journal['profile'];history=journal['history']
 else:
  project=P(tempfile.mkdtemp(prefix='flash-http32k-'));name='http-qual-'+str(os.getpid());history=[dict(role='system',content=SYSTEM)]
  journal=dict(project=str(project),profile=name,history=history,completed=[],status='INCOMPLETE')
  save(progress,journal)
 if not a.skip_cache_tests and not (a.out/'cache-state-report.json').exists():cache_and_state(a.repo,a.out,project,name)
 extra=('--flash-profile',name) if (project/'warm-tools-cache'/('flash-'+name+'-warm.json')).exists() else ()
 session='http-long-session';phase='long-resume-'+str(int(time.time())) if a.resume else 'long-session'
 with Server(a.repo,a.out/phase,'lazy32k',extra=extra,work_project=project) as s:
  short_body=payload([dict(role='system',content=SYSTEM),dict(role='user',content='Reply exactly ORBIT.')],'http-short-reset')
  s.chat('short-baseline',short_body);short_state=observe(s,'http-short-reset',True)
  if a.resume:
   journal.setdefault('resumptions',[]).append(dict(context=max([x['context_tokens'] for x in journal['completed']],default=0),normal_history_replay=True))
   save(progress,journal)
  resident=0;need_replay=a.resume
  targets=[x for x in (8191,16383,24576,32767) if x<=a.target]
  if a.target not in targets:targets.append(a.target)
  completed=max([x['context_tokens'] for x in journal['completed']],default=0)
  for boundary in targets:
   if boundary<=completed:continue
   while True:
    goal=min(boundary,max(completed,resident)+a.chunk)
    if boundary-goal<64:goal=boundary
    incoming=history if resident==0 or need_replay else []
    # The initial system-only transcript is a new request; subsequent requests
    # contain only a new user turn and use the actual resident session protocol.
    messages,msg=fit(s,incoming,session,goal)
    b=payload(messages,session,max_tokens=4,stream=True)
    response=s.chat('context-'+str(goal),b,timeout=1800)
    assert response['flash_timings']['context_tokens']==goal,response
    if resident:assert response['flash_timings']['session_reused']
    if incoming and len(incoming)>1:history=incoming
    history.append(msg);history.append(dict(role='assistant',content=canonical(response)['content']))
    state=observe(s,session);resident=state['resident_pos'];completed=goal;need_replay=False
    row=dict(context_tokens=goal,resident_pos=resident,kv_lengths=state['kv_lengths'],usage=response['usage'],timings=response['flash_timings'])
    journal['completed'].append(row);journal['history']=history;save(progress,journal)
    print('LONG_CONTEXT',goal,'resident',resident,'kv',state['kv_lengths'],flush=True)
    if goal==boundary:break
  # A resumed transcript may have crossed an earlier boundary in a previous
  # server lifetime. Preserve that evidence instead of requiring it to recur.
  log='\n'.join(p.read_text() for p in sorted(a.out.glob('long*/server.log')))
  routes={}
  for length in (8192,8193,16384,16385,24576,32767,32768,32769):
   if length>a.target+4:continue
   rows=[(int(l),backend) for seq,l,backend in re.findall(r'\[gpu-kv-boundary\] seq=(\d+) layer=(\d+) cap=32768 backend=(GPU|CPU)',log) if int(seq)==length]
   assert set(l for l,b in rows)==set(range(3,40,4)),(length,rows)
   assert all(b==('GPU' if length<=32768 else 'CPU') for l,b in rows),(length,rows)
   routes[length]=rows
  if resident>=32769:
   before=observe(s,session)
   code,error=request(s.url+'/v1/chat/completions',payload([dict(role='user',content='Reply exactly OK.')],session,max_tokens=32768))
   assert code==400,(code,error)
   after=observe(s,session);assert before['resident_pos']==after['resident_pos'] and before['kv_lengths']==after['kv_lengths']
   journal['capacity_rejection']=dict(status=code,error=error,before=before,after=after)
   b=s.chat('continuation-after-capacity-rejection',payload([dict(role='user',content='Reply exactly OK.')],session,max_tokens=4));assert b['flash_timings']['session_reused']
  s.chat('post-long-short-reset',short_body);short_after=observe(s,'http-short-reset',True)
  assert short_after['state_hash']==short_state['state_hash'],(short_state,short_after)
  journal['post_long_reset']=dict(before=short_state,after=short_after,exact=True)
  journal['routes']=routes;journal['status']='PASS';save(progress,journal)
 print('PASS',a.out,flush=True)
if __name__=='__main__':main()
