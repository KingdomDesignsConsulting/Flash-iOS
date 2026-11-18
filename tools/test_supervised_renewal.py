import copy,json,os,pathlib,tempfile,unittest
from supervised_renewal import *
class PolicyTests(unittest.TestCase):
 def setUp(self):
  self.d=example();self.d.update(approved=True,valid_from=100,valid_until=1000,candidate_manifest_sha256='a'*64,model_manifest_sha256='b'*64)
 def test_valid_recurring(self):validate(self.d,now=200)
 def test_policy_fault_matrix(self):
  changes=[('approved',False),('kind','cutover'),('operator_uid',os.getuid()+1),('valid_until',199),('valid_from',201),('valid_until',90000),('valid_until',float('nan')),('source_sha','x'),('binary_sha256','x'),('port',80),('port',True),('max_launches',0),('max_launches',5),('max_launches',True),('max_process_seconds',21601),('host_reserve_bytes',1),('rss_limit_bytes',999999999999),('minimum_cycle_seconds',0),('renew_after_seconds',21600),('profile','arbitrary'),('model_root','relative'),('assets',{})]
  for k,v in changes:
   with self.subTest(k=k,v=v):
    d=copy.deepcopy(self.d);d[k]=v
    with self.assertRaises(Blocked):validate(d,now=200)
 def test_same_record_after_expiry(self):
  validate(self.d,now=999)
  with self.assertRaises(Blocked):validate(self.d,now=1000)
 def test_owner_mode_symlink_and_lock(self):
  with tempfile.TemporaryDirectory() as t:
   p=P(t)/'p';p.write_text(json.dumps(self.d));p.chmod(0o600);owned_json(p)
   p.chmod(0o640)
   with self.assertRaises(Blocked):owned_json(p)
   link=P(t)/'link';link.symlink_to(p)
   with self.assertRaises(OSError):owned_json(link)
   with coordinator_lock(P(t)/'lock'):
    with self.assertRaises(BlockingIOError):
     with coordinator_lock(P(t)/'lock'):pass
 def test_wrong_artifacts(self):
  # Rejected before any subprocess creation or model access.
  with tempfile.TemporaryDirectory() as t:
   self.d['runtime_root']=t;self.d['binary']=str(P(t)/'foreign')
   with self.assertRaises(Blocked):artifacts(self.d)
 def test_no_native_adapter(self):self.assertFalse(NATIVE_DRAIN_SUPPORTED)
class Mock:
 def __init__(self):self.gen=0;self.live=False;self.active=0;self.closed=False;self.calls=[];self.fault=None;self.pid=100;self.birth=1
 def start(self,max_seconds):self.calls.append(('start',max_seconds));self.gen+=1;self.birth+=1;self.live=True;self.closed=False;return self.identity()
 def identity(self):return (self.pid,self.birth,self.gen)
 def ready(self,i):
  if self.fault in ('health','partial_stream','checkpoint'):raise Blocked(self.fault)
 def alive(self):return self.live
 def resources(self):
  if self.fault in ('low_memory','rss','telemetry'):raise Blocked(self.fault)
 def close_admission(self,i):self.closed=True;return self.fault!='no_barrier'
 def idle(self,i):return self.active==0
 def stop_owned(self,i):
  need(i==self.identity(),'stale PID');need(not self.active and self.closed,'unsafe stop');self.live=False;self.calls.append(('stop',i))
 def exited(self,i):return not self.live and self.fault!='unreaped'
 def port_free(self):return self.fault!='foreign_listener'
 def lock_released(self):return self.fault!='orphan_lock'
class CycleTests(unittest.TestCase):
 def setUp(self):
  self.t=0;self.wall=200;self.b=Mock();self.verifications=0
  def verify(w):self.verifications+=1;need(w<1000,'expired policy')
  self.c=Cycle(self.b,verify,lambda:self.t,lambda:self.wall,renew=60,minimum=60)
 def test_clean_two_renewals(self):
  self.c.launch()
  for t in [60,120]:self.t=t;self.c.tick()
  self.assertEqual(self.c.count,3);self.assertEqual([x[1] for x in self.b.calls if x[0]=='start'],[21600]*3)
 def test_request_spans_boundary(self):
  self.c.launch();old=self.c.identity;self.b.active=1;self.t=65;self.c.tick();self.assertEqual(self.c.count,1);self.assertTrue(self.b.live);self.assertTrue(self.b.closed)
  self.b.active=0;self.t=80;self.c.tick();self.assertEqual(self.c.count,2);self.assertNotEqual(self.c.identity,old)
 def test_idle_cannot_be_inferred_without_barrier(self):
  self.c.launch();self.b.fault='no_barrier';self.t=60
  with self.assertRaises(Blocked):self.c.tick()
  self.assertTrue(self.b.live);self.assertEqual(self.c.count,1)
 def test_stale_pid_birth(self):
  self.c.launch();self.b.birth+=1;self.t=60
  with self.assertRaises(Blocked):self.c.tick()
  self.assertFalse(any(x[0]=='stop' for x in self.b.calls))
 def test_unexpected_exit(self):
  self.c.launch();self.b.live=False
  with self.assertRaises(Blocked):self.c.tick()
  self.assertEqual(self.c.count,1)
 def test_failure_matrix_latched(self):
  for fault in ['low_memory','rss','telemetry','foreign_listener','orphan_lock','unreaped']:
   with self.subTest(fault=fault):
    self.setUp();self.c.launch();self.b.fault=fault;self.t=60
    with self.assertRaises(Blocked):self.c.tick()
    with self.assertRaises(Blocked):self.c.tick()
    self.assertEqual(self.c.count,1)
 def test_readiness_faults_no_retry(self):
  for fault in ['health','partial_stream','checkpoint']:
   with self.subTest(fault=fault):
    self.setUp();self.b.fault=fault
    with self.assertRaises(Blocked):self.c.launch()
    with self.assertRaises(Blocked):self.c.launch()
    self.assertEqual(self.c.count,1)
 def test_expiry_before_next_launch(self):
  self.c.launch();self.wall=1000;self.t=60
  with self.assertRaises(Blocked):self.c.tick()
  self.assertEqual(self.c.count,1)
 def test_no_idle_at_hard_deadline(self):
  self.c.launch();self.b.active=1;self.t=21600
  with self.assertRaises(Blocked):self.c.tick()
  self.assertEqual(self.c.count,1);self.assertTrue(self.b.live) # supervisor, not kernel, owns hard termination
 def test_restart_budget(self):
  self.test_clean_two_renewals();self.t=180
  with self.assertRaises(Blocked):self.c.tick()
  self.assertEqual(self.c.count,3)
 def test_concurrent_policy_edit_before_relaunch(self):
  self.c.launch();self.t=60
  def fail(w):raise Blocked('changed policy')
  self.c.verify=fail
  with self.assertRaises(Blocked):self.c.tick()
  self.assertEqual(self.c.count,1)

class ArtifactTests(unittest.TestCase):
 def setUp(self):
  import supervised_renewal as m
  from unittest.mock import patch
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=P(self.tmp.name);self.d=example();self.d['runtime_root']=str(self.root)
  binary=self.root/'metal_infer/infer-mask63-supervised-20261117';binary.parent.mkdir();binary.write_bytes(b'SYNTHETIC NOT EXECUTABLE')
  self.patch=patch.object(m,'BINARY',digest(binary));self.patch.start();self.addCleanup(self.patch.stop)
  self.d['binary']=str(binary);self.d['binary_sha256']=digest(binary)
  sources={}
  for i in range(47):
   p=self.root/('source'+str(i));p.write_text(str(i));sources[p.name]=digest(p)
  c=self.root/'candidate.json';c.write_text(json.dumps(dict(candidate_source_sha=SOURCE,binary_sha256=digest(binary),source_sha256=sources)))
  model=self.root/'model';model.mkdir();files={}
  for i in range(49):
   p=model/str(i);p.write_text(str(i));files[p.name]={'bytes':p.stat().st_size,'sha256':digest(p)}
  manifest=self.root/'model.json';manifest.write_text(json.dumps(dict(root=str(model),files=files)))
  self.d.update(candidate_manifest=str(c),candidate_manifest_sha256=digest(c),model_root=str(model),model_manifest=str(manifest),model_manifest_sha256=digest(manifest))
  for role in self.d['assets']:
   p=self.root/role;p.write_text('synthetic '+role);self.d['assets'][role]={'path':str(p),'sha256':digest(p)}
 def test_all_synthetic_bindings(self):self.assertTrue(artifacts(self.d))
 def test_wrong_binary_bytes(self):
  P(self.d['binary']).write_text('changed')
  with self.assertRaises(Blocked):artifacts(self.d)
 def test_wrong_source_bytes(self):
  (self.root/'source0').write_text('changed')
  with self.assertRaises(Blocked):artifacts(self.d)
 def test_wrong_manifest(self):
  P(self.d['candidate_manifest']).write_text('{}')
  with self.assertRaises(Blocked):artifacts(self.d)
 def test_wrong_model(self):
  (self.root/'model/0').write_text('changed')
  with self.assertRaises(Blocked):artifacts(self.d)
 def test_wrong_recovery(self):
  P(self.d['assets']['recovery_archive']['path']).write_text('changed')
  with self.assertRaises(Blocked):artifacts(self.d)
 def test_profile_changed(self):
  P(self.d['assets']['profile_source']['path']).write_text('changed')
  with self.assertRaises(Blocked):artifacts(self.d)

if __name__=='__main__':unittest.main()
