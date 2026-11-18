#!/usr/bin/env python3
"""Fail-closed renewal preflight and deterministic coordinator prototype.
Frozen native runtime has no admission-close barrier: --run cannot launch it.
No one-time cutover authorization is read, copied or refreshed.
"""
import argparse,contextlib,fcntl,hashlib,json,math,os,pathlib,stat,time,uuid
P=pathlib.Path
SOURCE='e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83'
BINARY='9f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4'
NATIVE_DRAIN_SUPPORTED=False
class Blocked(RuntimeError):pass
def need(v,msg):
 if not v:raise Blocked(msg)
def digest(p):
 h=hashlib.sha256()
 with P(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def owned_json(path):
 path=P(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd) as f:
  s=os.fstat(f.fileno());need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600,'policy must be owner-held regular0600')
  raw=f.read();d=json.loads(raw);need(os.fstat(f.fileno()).st_mtime_ns==s.st_mtime_ns,'policy edited during read')
 return d,hashlib.sha256(raw.encode()).hexdigest()
def validate(d,now=None):
 now=time.time() if now is None else now
 need(isinstance(d,dict) and set(d)==set(example()),'unexpected/missing policy fields')
 need(d.get('kind')=='flash-recurring-operations-v1','not recurring operations policy')
 need(d.get('approved') is True,'recurring operations not explicitly approved')
 need(type(d.get('operator_uid')) is int and d['operator_uid']==os.getuid(),'wrong operator')
 for k in ['valid_from','valid_until','renew_after_seconds','minimum_cycle_seconds']:
  need(type(d.get(k)) in (int,float) and math.isfinite(d[k]),'invalid '+k)
 need(d['valid_from']<=now<d['valid_until'] and 0<d['valid_until']-d['valid_from']<=86400,'expired/unbounded policy')
 need(d.get('source_sha')==SOURCE and d.get('binary_sha256')==BINARY,'frozen identity mismatch')
 need(type(d.get('port')) is int and d['port'] in (11241,11251),'unapproved port')
 need(type(d.get('max_launches')) is int and 1<=d['max_launches']<=4,'launch count bound')
 need(60<=d['minimum_cycle_seconds']<=d['renew_after_seconds']<=19800,'renewal rate bound')
 need(d.get('max_process_seconds')==21600 and type(d['max_process_seconds']) is int,'six-hour cap changed')
 need(d.get('host_reserve_bytes')==6*1024**3 and d.get('rss_limit_bytes')==16*1024**3,'resource contract changed')
 need(d.get('profile')=='main-agent','unapproved profile')
 for k in ['runtime_root','binary','model_manifest','candidate_manifest','model_root']:
  need(isinstance(d.get(k),str) and P(d[k]).is_absolute(),'absolute path required '+k)
 for k in ['model_manifest_sha256','candidate_manifest_sha256']:
  need(isinstance(d.get(k),str) and len(d[k])==64,'manifest binding missing')
 need(isinstance(d.get('assets'),dict) and all(k in d['assets'] for k in ['recovery_archive','recovery_selection','profile_source','supervisor','resource_probe']),'missing asset roles')
 return d
def artifacts(d):
 root=P(d['runtime_root']).resolve();binary=P(d['binary'])
 need(binary.resolve()==root/'metal_infer/infer-mask63-supervised-20261117','binary location mismatch')
 need(digest(binary)==BINARY,'binary checksum')
 for role in ['candidate','model']:
  need(digest(d[role+'_manifest'])==d[role+'_manifest_sha256'],role+' manifest changed')
 m=json.loads(P(d['candidate_manifest']).read_text());need(m.get('candidate_source_sha')==SOURCE and m.get('binary_sha256')==BINARY,'source manifest identity')
 sources=m.get('source_sha256',{});need(len(sources)==47,'expected47runtime bindings')
 for name,h in sources.items():
  rel=P(name);need(not rel.is_absolute() and '..' not in rel.parts and (root/rel).resolve().is_relative_to(root),'source traversal')
  need(digest(root/rel)==h,'runtime changed '+name)
 model=json.loads(P(d['model_manifest']).read_text());need(model.get('root')==d['model_root'] and len(model.get('files',{}))==49,'model identity/count')
 for name,row in model['files'].items():
  rel=P(name);need(not rel.is_absolute() and '..' not in rel.parts,'model traversal');p=P(d['model_root'])/rel
  s=p.stat();need(s.st_size==row['bytes'] and digest(p)==row['sha256'],'model changed '+name)
  t=p.stat();need((s.st_ino,s.st_size,s.st_mtime_ns)==(t.st_ino,t.st_size,t.st_mtime_ns),'model changed during verification')
 for role,a in d['assets'].items():
  need(isinstance(a,dict) and P(a.get('path','')).is_absolute(),'asset path '+role)
  need(digest(a['path'])==a.get('sha256'),'asset changed '+role)
 return True
@contextlib.contextmanager
def coordinator_lock(path):
 fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
 try:
  s=os.fstat(fd);need(s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600 and stat.S_ISREG(s.st_mode),'unsafe coordinator lock')
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
 finally:os.close(fd) # Never unlink; no PID-file signaling.
class Cycle:
 """Testable transition kernel. No native process adapter is enabled.
 backend.close_admission must atomically prevent new work before idle is checked.
 Monotonic cycle timing never extends a process deadline. Faults are latched.
 """
 def __init__(self,backend,verify,clock,wall,launches=3,renew=19800,minimum=60):
  self.b=backend;self.verify=verify;self.clock=clock;self.wall=wall;self.limit=launches;self.renew=renew;self.minimum=minimum;self.count=0;self.state='PREPARED';self.identity=None
 def block(self,msg):self.state='BLOCKED';raise Blocked(msg)
 def launch(self):
  if self.state not in ('PREPARED','STOPPED'):self.block('not launchable')
  if self.count>=self.limit:self.block('launch budget exhausted')
  try:
   self.verify(self.wall());self.identity=self.b.start(max_seconds=21600);self.count+=1;self.b.ready(self.identity)
  except Exception as e:self.block(str(e))
  self.started=self.clock();self.state='RUNNING'
 def tick(self):
  if self.state=='BLOCKED':raise Blocked('fault latched; operator required')
  try:
   self.verify(self.wall());need(self.b.identity()==self.identity,'birth/PID mismatch');need(self.b.alive(),'unexpected child exit');self.b.resources()
   elapsed=self.clock()-self.started
   if elapsed<self.renew:return
   need(elapsed<21600,'hard deadline; no renewal')
   need(elapsed>=self.minimum,'restart frequency exceeded')
   self.state='DRAINING';need(self.b.close_admission(self.identity),'no admission-close barrier')
   if not self.b.idle(self.identity):return # No signal/restart across active request.
   self.b.stop_owned(self.identity);need(self.b.exited(self.identity),'child not reaped')
   need(self.b.port_free() and self.b.lock_released(),'port/lock still owned')
   self.state='STOPPED';self.launch()
  except Exception as e:self.block(str(e))
def example():
 return dict(kind='flash-recurring-operations-v1',approved=False,operator_uid=os.getuid(),valid_from=0,valid_until=0,source_sha=SOURCE,binary_sha256=BINARY,port=11251,max_launches=3,renew_after_seconds=19800,minimum_cycle_seconds=60,max_process_seconds=21600,host_reserve_bytes=6*1024**3,rss_limit_bytes=16*1024**3,profile='main-agent',runtime_root='/REVIEW/runtime',binary='/REVIEW/runtime/metal_infer/infer-mask63-supervised-20261117',model_root='/REVIEW/model',candidate_manifest='/REVIEW/candidate.json',candidate_manifest_sha256='REQUIRED',model_manifest='/REVIEW/model.json',model_manifest_sha256='REQUIRED',assets={k:{'path':'/REVIEW/'+k,'sha256':'REQUIRED'} for k in ['recovery_archive','recovery_selection','profile_source','supervisor','resource_probe']})
def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
 for name in ['check-only','simulate','run','stop-owned','build-policy']:g.add_argument('--'+name,action='store_true')
 p.add_argument('--policy',type=P);p.add_argument('--out',type=P,required=True);a=p.parse_args();os.umask(0o077);a.out.mkdir(parents=True,exist_ok=False,mode=0o700)
 result={'status':'BLOCKED','native_drain_supported':False,'native_model_started':False,'production_modified':False,'at':time.time()}
 try:
  if a.build_policy:
   (a.out/'policy.unapproved.json').write_text(json.dumps(example(),indent=2)+'\n');result['status']='UNAPPROVED_TEMPLATE_CREATED'
  elif a.simulate:
   # Only deterministic model-free tests; no sockets or native launches.
   import subprocess,sys
   r=subprocess.run([sys.executable,'-m','unittest','test_supervised_renewal'],cwd=P(__file__).parent,capture_output=True,text=True)
   (a.out/'simulation.txt').write_text(r.stdout+r.stderr);need(r.returncode==0,'simulation failed');result['status']='SIMULATION_PASS_NOT_NATIVE_QUALIFICATION'
  else:
   need(a.policy is not None,'policy required');d,h=owned_json(a.policy);validate(d);result['policy_sha256']=h
   with coordinator_lock(a.out.parent/'renewal-coordinator.lock'):
    artifacts(d);need(owned_json(a.policy)[1]==h,'concurrent policy edit')
    if a.run or a.stop_owned:raise Blocked('NO RELIABLE NATIVE DRAIN/IDLE BARRIER; no model start/stop permitted')
    result['status']='IDENTITIES_PASS_NATIVE_RENEWAL_BLOCKED'
 except Exception as e:result['reason']=str(e)
 finally:(a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2));return 0 if result['status']!='BLOCKED' else 3
if __name__=='__main__':raise SystemExit(main())
