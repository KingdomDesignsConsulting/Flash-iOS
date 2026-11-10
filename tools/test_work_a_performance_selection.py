import unittest
from benchmark_work_a_long import selected_modes
class Selection(unittest.TestCase):
 def test_resume_only_missing_modes(self):
  rows=selected_modes('mask63,scalar','control','candidate');self.assertEqual([r[0] for r in rows],['mask63','scalar']);self.assertEqual(rows[0],('mask63','candidate',63,True));self.assertEqual(rows[1],('scalar','control',0,False))
 def test_default_controls_preserved(self):self.assertEqual([r[0] for r in selected_modes('ordinary,mask63,scalar','c','e')],['ordinary','mask63','scalar'])
 def test_invalid_and_duplicate_modes_reject(self):
  for value in ['',',','mask63,mask63','scalar,unknown']:
   with self.assertRaises(ValueError):selected_modes(value,'c','e')
if __name__=='__main__':unittest.main()
