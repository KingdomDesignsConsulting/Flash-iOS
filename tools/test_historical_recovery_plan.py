import json,os,tempfile,unittest
from pathlib import Path
from launch_historical_recovery import authorize_production
class Plans(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'synthetic.json';self.selection={'archive_sha256':'b'*64,'model_root':'/SYNTHETIC_MODEL_NOT_LOADED'}
  self.d=dict(production_cutover_authorized=True,software_rollback_only=True,fallback_native_context_guard_acknowledged=True,purpose='historical-rollback',operator_uid=os.getuid(),port=11241,selection_sha256='a'*64,archive_sha256='b'*64,model_path=self.selection['model_root'],expires_unix=1001)
 def tearDown(self):self.tmp.cleanup()
 def check(self):
  self.path.write_text(json.dumps(self.d));self.path.chmod(0o600);return authorize_production(self.path,'a'*64,self.selection,now=1000)
 def test_synthetic_positive(self):self.check()
 def test_no_cutover_authorization(self):self.d['production_cutover_authorized']=False;self.assertRaises(ValueError,self.check)
 def test_legacy_guard_not_acknowledged(self):self.d['fallback_native_context_guard_acknowledged']=False;self.assertRaises(ValueError,self.check)
 def test_wrong_selection(self):self.d['selection_sha256']='c'*64;self.assertRaises(ValueError,self.check)
 def test_wrong_archive(self):self.d['archive_sha256']='c'*64;self.assertRaises(ValueError,self.check)
 def test_wrong_owner(self):self.d['operator_uid']+=1;self.assertRaises(ValueError,self.check)
 def test_expired(self):self.d['expires_unix']=999;self.assertRaises(ValueError,self.check)
 def test_wrong_port(self):self.d['port']=11250;self.assertRaises(ValueError,self.check)
if __name__=='__main__':unittest.main()
