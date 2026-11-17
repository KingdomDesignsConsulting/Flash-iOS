import copy,hashlib,json,os,tempfile,time,unittest
from pathlib import Path
from supervise_qualified_serve import validate_production_plan
class Plans(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name).resolve();self.bin=self.root/'candidate';self.bin.write_bytes(b'fixture');self.source=self.root/'source.h';self.source.write_text('fixture');h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  self.c=self.root/'candidate.json';self.c.write_text(json.dumps({'candidate_source_sha':'1'*40,'binary_sha256':h(self.bin),'source_sha256':{'source.h':h(self.source)}}));self.b=self.root/'backup.json';self.b.write_text('fixture backup evidence')
  self.data=dict(production_cutover_authorized=True,recovery_policy_accepted=True,complete_backup_verified=True,canary_accepted=True,port=11241,operator_uid=os.getuid(),expires_unix=1001,model_path=str(self.root/'model'),candidate_source_sha='1'*40,candidate_binary_sha256=h(self.bin),candidate_manifest={'path':str(self.c),'sha256':h(self.c)},recovery_manifest={'path':str(self.b),'sha256':h(self.b)})
 def tearDown(self):self.t.cleanup()
 def check(self):
  p=self.root/'authorization.json';p.write_text(json.dumps(self.data));p.chmod(0o600);return validate_production_plan(p,self.bin,self.root/'model',self.root,now=1000)
 def test_positive_synthetic_only(self):self.check()
 def test_missing_authorization(self):self.data['production_cutover_authorized']=False;self.assertRaises(ValueError,self.check)
 def test_missing_canary(self):self.data['canary_accepted']=False;self.assertRaises(ValueError,self.check)
 def test_missing_recovery(self):self.data['complete_backup_verified']=False;self.assertRaises(ValueError,self.check)
 def test_policy_unaccepted(self):self.data['recovery_policy_accepted']=False;self.assertRaises(ValueError,self.check)
 def test_expired(self):self.data['expires_unix']=999;self.assertRaises(ValueError,self.check)
 def test_unbounded(self):self.data['expires_unix']=999999;self.assertRaises(ValueError,self.check)
 def test_wrong_uid(self):self.data['operator_uid']+=1;self.assertRaises(ValueError,self.check)
 def test_binary(self):self.data['candidate_binary_sha256']='0'*64;self.assertRaises(ValueError,self.check)
 def test_backup_changed(self):self.b.write_text('wrong');self.assertRaises(ValueError,self.check)
 def test_source_changed(self):self.source.write_text('wrong');self.assertRaises(ValueError,self.check)
 def test_model_changed(self):self.data['model_path']='/wrong';self.assertRaises(ValueError,self.check)
if __name__=='__main__':unittest.main()
