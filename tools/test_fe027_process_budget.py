import subprocess,sys,unittest
from qualify_session_accumulation import wait_bounded_process
class ProcessBudget(unittest.TestCase):
    def child(self,code):
        p=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.addCleanup(lambda:p.poll() is None and p.kill())
        return p
    def test_success(self):
        p=self.child('pass');code,_,reason=wait_bounded_process(p,5,1024**3)
        self.assertEqual((code,reason),(0,None));self.assertIsNotNone(p.poll())
    def test_rss_limit_stops_owned_child(self):
        p=self.child('import time; data=bytearray(32*1024*1024); time.sleep(30)')
        code,peak,reason=wait_bounded_process(p,5,1024**2)
        self.assertEqual((code,reason),(125,'RSS_LIMIT'));self.assertGreater(peak,1024**2);self.assertIsNotNone(p.poll())
    def test_timeout_stops_owned_child(self):
        p=self.child('import time; time.sleep(30)');code,_,reason=wait_bounded_process(p,.01,0)
        self.assertEqual((code,reason),(124,'TIMEOUT'));self.assertIsNotNone(p.poll())
if __name__=='__main__':unittest.main()
