import contextlib,threading,unittest
from pathlib import Path
from unittest.mock import patch
import qualify_named_profile_http as profile
class ProfileWatch(unittest.TestCase):
 def test_cleanup_precedes_monitor_join(self):
  closed=threading.Event()
  @contextlib.contextmanager
  def raw(*args,**kwargs):
   try:yield dict(process=object(),out=Path('synthetic'))
   finally:closed.set()
  def monitor(*args,**kwargs):
   assert closed.wait(1),'Watchdog joined before server cleanup';return -15,123,None
  with patch.object(profile,'_raw_server',raw),patch.object(profile,'wait_bounded_process',monitor):
   with profile.server():self.assertFalse(closed.is_set())
  self.assertTrue(closed.is_set())
 def test_limit_failure_is_not_success(self):
  closed=[]
  @contextlib.contextmanager
  def raw(*args,**kwargs):
   try:yield dict(process=object(),out=Path('synthetic'))
   finally:closed.append(True)
  with patch.object(profile,'_raw_server',raw),patch.object(profile,'wait_bounded_process',return_value=(125,123,'RSS_LIMIT')):
   with self.assertRaises(AssertionError):
    with profile.server():pass
  self.assertTrue(closed)
if __name__=='__main__':unittest.main()
