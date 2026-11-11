#!/usr/bin/env python3
"""Synthetic offline manifests only; never inspect a real installed artifact."""
import importlib.util,pathlib,tempfile,hashlib,json,copy,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('provenance',R/'tools/verify_release_provenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
results=[]
with tempfile.TemporaryDirectory(prefix='c11-offline-fixture-') as d:
 p=pathlib.Path(d);artifact=p/'fictional-artifact';artifact.write_text('synthetic offline test only\n')
 data=dict(authorized_inventory=True,source_commit='1'*40,release_commit='2'*40,launcher_owner='SYNTHETIC TEST OWNER',launcher_definition='SYNTHETIC TEST ONLY',installed_executable=str(artifact),startup_argv=['SYNTHETIC-NOT-EXECUTED'],startup_environment={'FLASH_FE027_NUMERICS':'63'},runtime_dependencies=[str(artifact)],model_identity='synthetic-model-hash',cache_backups=[str(p/'fictional-backup-a'),str(p/'fictional-backup-b')],rollback_argv=['SYNTHETIC-NOT-EXECUTED'],rollback_environment={'SYNTHETIC':'ONLY'},rollback_test_plan='Fictional test, no rollback execution',files=[dict(path=str(artifact),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())])
 variants=[('complete synthetic listed artifact',None,True),('unauthorized',lambda x:x.update(authorized_inventory=False),False),('missing owner',lambda x:x.pop('launcher_owner'),False),('no files',lambda x:x.update(files=[]),False),('wrong digest',lambda x:x['files'][0].update(sha256='0'*64),False),('missing artifact',lambda x:x['files'][0].update(path=str(p/'absent')),False),('relative artifact',lambda x:x['files'][0].update(path='relative'),False),('invalid digest',lambda x:x['files'][0].update(sha256='xyz'),False),('one backup root',lambda x:x.update(cache_backups=['one']),False),('invalid argv type',lambda x:x.update(startup_argv='not-an-array'),False),('invalid environment type',lambda x:x.update(startup_environment=[]),False),('same source unexplained',lambda x:x.update(release_commit=x['source_commit']),False)]
 for name,change,want in variants:
  x=copy.deepcopy(data)
  if change:change(x)
  manifest=p/'manifest.json';manifest.write_text(json.dumps(x));run=subprocess.run([sys.executable,str(R/'tools/verify_release_provenance.py'),'--manifest',str(manifest)],capture_output=True,text=True)
  if (run.returncode==0)!=want:raise RuntimeError((name,run.stdout,run.stderr))
  results.append(dict(case=name,exit=run.returncode,expected_accept=want))
 # Deliberately demonstrate scope: named fields are not artifact-role bindings.
 x=copy.deepcopy(data);x.update(installed_executable='/FICTIONAL/NOT-READ',runtime_dependencies=['/FICTIONAL/NOT-READ'],cache_backups=['/FICTIONAL/A','/FICTIONAL/B'])
 if m.check_package(x):raise RuntimeError('Unexpected stronger role validation; update limitation')
report=dict(status='PASS',cases=results,scope='Synthetic manifest CLI validation only. True authorization flag belongs solely to fictional positive fixtures; no real inventory claim.',limitation='Validator hashes only files[]. It does not establish existence/hash-role binding for installed_executable, dependencies or backup roots, validate actual launcher mapping, create archives or test rollback. C11-02 remains OPEN.')
(R/'docs/audits/c11-verification-evidence/provenance.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: 12 synthetic provenance CLI cases; artifact-role limitation confirmed')
