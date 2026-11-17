import unittest
from qualify_mask63_missing import wait_gpu
class Gate(unittest.TestCase):
 def check_values(self,values):
  source=iter(values);return wait_gpu(lambda:next(source),lambda _:None,len(values))
 def test_three_low(self):self.assertEqual(self.check_values([0,17,29]),[0,17,29])
 def test_owned_gpu_draining(self):self.assertEqual(self.check_values([67,15,17,19])[-3:],[15,17,19])
 def test_30_is_not_below_threshold(self):self.assertEqual(len(self.check_values([30,24,24,25])),4)
 def test_intervening_peak_resets(self):self.assertEqual(len(self.check_values([29,31,29,29,29])),5)
 def test_unknown_is_not_safe(self):
  with self.assertRaises(RuntimeError):self.check_values([None,None,None])
 def test_persistent_load_never_admits(self):
  with self.assertRaises(RuntimeError):self.check_values([31]*60)
 def test_negative_reading_never_admits(self):
  with self.assertRaises(RuntimeError):self.check_values([-1,-1,-1])
if __name__=='__main__':unittest.main()
