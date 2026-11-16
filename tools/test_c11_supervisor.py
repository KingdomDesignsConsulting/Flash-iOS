import json,os,pathlib,signal,subprocess,sys,tempfile,threading,time,unittest
from supervise_qualified_serve import supervise,HOST_MIN,RSS_MAX
class SupervisorTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def run_case(self,sample,command=None,**kw):
  return supervise(command or [sys.executable,'-c','import time;time.sleep(5)'],os.environ.copy(),self.root/'run',sample,interval=.05,max_seconds=2,lock_path=self.root/'lock',**kw)
 def sample(self,pid):return dict(host_available_bytes=HOST_MIN,rss_bytes=1,start_abstime=123)
 def test_normal(self):self.assertEqual(self.run_case(self.sample,[sys.executable,'-c','pass'])['status'],'EXITED')
 def test_prelaunch(self):
  r=self.run_case(lambda _:dict(host_available_bytes=HOST_MIN-1));self.assertFalse(r['model_started'])
 def test_missing_prelaunch(self):
  def fail(_):raise OSError('missing telemetry')
  self.assertFalse(self.run_case(fail)['model_started'])
 def test_low_host(self):
  def sample(pid):return dict(host_available_bytes=HOST_MIN-(pid!=0),rss_bytes=1,start_abstime=123)
  self.assertEqual(self.run_case(sample)['stop_reason'],'host_reserve')
 def test_rss(self):
  def sample(pid):return dict(host_available_bytes=HOST_MIN,rss_bytes=RSS_MAX if pid else 1,start_abstime=123)
  self.assertEqual(self.run_case(sample)['stop_reason'],'process_rss')
 def test_missing_running(self):
  def sample(pid):
   if pid:raise OSError('telemetry gone')
   return self.sample(pid)
  self.assertEqual(self.run_case(sample)['stop_reason'],'telemetry_unavailable')
 def test_cancel(self):
  stop=threading.Event();stop.set();self.assertEqual(self.run_case(self.sample,stop=stop)['stop_reason'],'operator_cancel')
 def test_deadline(self):
  r=supervise([sys.executable,'-c','import time;time.sleep(5)'],os.environ.copy(),self.root/'run',self.sample,interval=.05,max_seconds=.1,lock_path=self.root/'lock');self.assertEqual(r['stop_reason'],'lifetime_deadline')
 def test_exclusive_cooperating_lock_and_unrelated_survives(self):
  import fcntl
  unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])
  fd=os.open(self.root/'lock',os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   r=self.run_case(self.sample);self.assertFalse(r['model_started']);self.assertIsNone(unrelated.poll())
  finally:os.close(fd);unrelated.terminate();unrelated.wait()
 def test_child_inherits_lock_after_parent_closes_descriptor(self):
  import fcntl
  fd=os.open(self.root/'lock',os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'],pass_fds=(fd,));os.close(fd)
  other=os.open(self.root/'lock',os.O_RDWR)
  try:
   with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
   child.terminate();child.wait();fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
  finally:
   if child.poll() is None:child.kill();child.wait()
   os.close(other)
 def test_changed_child_birth(self):
  calls=0
  def sample(pid):
   nonlocal calls
   calls+=1;return dict(host_available_bytes=HOST_MIN,rss_bytes=1,start_abstime=calls)
  self.assertEqual(self.run_case(sample)['stop_reason'],'telemetry_unavailable')
if __name__=='__main__':unittest.main()
