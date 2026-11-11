import unittest
from qualify_work_a_literal import parse_cli_samples,parse_cli_visible
class Samples(unittest.TestCase):
 def test_first_sample_is_not_dropped(self):
  log='[debug] Top 5 logits (next_token=21):\ntext [gen 1/256] token_id=22 (2 ms)\n[gen 2/256] token_id=23 (2 ms)'
  self.assertEqual(parse_cli_samples(log),[21,22,23])
 def test_native_stdout_kept_separate_from_progress(self):
  self.assertEqual(parse_cli_visible('startup\n--- Output ---\nADAPTER_73941<|im_end|>\n\n--- Statistics ---\ncounts'),'ADAPTER_73941')
 def test_missing_output_section_rejected(self):
  with self.assertRaises(AssertionError):parse_cli_visible('startup only')
 def test_missing_first_sample_rejected(self):
  with self.assertRaises(AssertionError):parse_cli_samples('[gen 1/256] token_id=22')
if __name__=='__main__':unittest.main()
