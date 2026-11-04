import subprocess,sys,unittest
from unittest.mock import patch
from qualify_session_accumulation import wait_bounded_process
class ProcessBudget(unittest.TestCase):
    def child(self,code):
        p=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        def cleanup():
            if p.poll() is None:p.kill()
            p.wait(timeout=5)
        self.addCleanup(cleanup)
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
    def test_host_pressure_stops_owned_child(self):
        p=self.child('import time; time.sleep(30)')
        with patch('qualify_session_accumulation.host_free_percent',return_value=5):
            code,_,reason=wait_bounded_process(p,5,0,host_free_floor=15,pressure_interval=.001)
        self.assertEqual((code,reason),(125,'HOST_MEMORY_PRESSURE'));self.assertIsNotNone(p.poll())
    def test_missing_host_monitor_fails_closed(self):
        p=self.child('import time; time.sleep(30)')
        with patch('qualify_session_accumulation.host_free_percent',return_value=None):
            code,_,reason=wait_bounded_process(p,5,0,host_free_floor=15)
        self.assertEqual((code,reason),(125,'HOST_MEMORY_MONITOR_ERROR'));self.assertIsNotNone(p.poll())
    def test_denied_rss_monitor_fails_closed(self):
        p=self.child('import time; time.sleep(30)')
        with patch('qualify_session_accumulation.subprocess.run',side_effect=PermissionError('ps denied')):
            code,_,reason=wait_bounded_process(p,5,1024**3)
        self.assertEqual((code,reason),(125,'RSS_MONITOR_ERROR'));self.assertIsNotNone(p.poll())
if __name__=='__main__':unittest.main()
