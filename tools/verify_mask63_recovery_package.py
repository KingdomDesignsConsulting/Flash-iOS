#!/usr/bin/env python3
"""Authenticate and freshly restore the software-rollback package, never production.
Full model hashes stream; operational launch is a separate, explicitly guarded step.
"""
import argparse,datetime,json,os,pathlib,posixpath,shutil,subprocess,tarfile
from recovery_tree import sha,inventory,compare,restore_metadata
from prepare_mask63_recovery import safe_archive
P=pathlib.Path
HISTORICAL='497ccfb734e17a7fa7f3369265b739dedf51e8b2cde55fed07e8a77d50db1909'
SOURCE='3a87663a72c6c88922dbd7fd9f82842e588a5dc6'

def main():
 p=argparse.ArgumentParser();p.add_argument('--backup',type=P,required=True);p.add_argument('--release-manifest',type=P,required=True);p.add_argument('--model-manifest',type=P,required=True);p.add_argument('--out',type=P,required=True);a=p.parse_args()
 os.umask(0o077);a.out.mkdir(parents=True,exist_ok=False,mode=0o700)
 m=json.loads(a.release_manifest.read_text());report={'status':'INCOMPLETE','started':datetime.datetime.now().astimezone().isoformat(),'production_modified':False,'purpose':'Same-disk software rollback, not disk-failure recovery','selected_executable':'infer-candidate-lazy32k','selected_source_association':SOURCE,'limitations':['Original group/provenance metadata normalization remains explicit','Model and OS/system libraries remain external same-host dependencies']}
 def save():(a.out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  archive=a.backup/'recovery.tar';expected=json.loads((a.backup/'package-manifest.json').read_text());model=json.loads(a.model_manifest.read_text())
  if sha(archive)!=m['recovery_archive_sha256'] or archive.stat().st_size!=m['recovery_archive_bytes']:raise ValueError('archive checksum/size')
  if sha(a.model_manifest)!=m['model_manifest_sha256'] or model['files']!=m['model_files']:raise ValueError('model checksum manifest identity')
  safe_archive(archive)
  seen=set();metadata_entries=0
  with tarfile.open(archive,'r|') as tf:
   for member in tf:
    name=posixpath.normpath(member.name)
    if name not in expected:
     parent,base=posixpath.split(name)
     target=posixpath.join(parent,base[2:]) if base.startswith('._') else None
     if target not in expected or not member.isfile():raise ValueError('unexpected archive entry '+name)
     metadata_entries+=1;continue
    row=expected[name];seen.add(name)
    if member.mode!=row['mode'] or member.uid!=row['uid'] or member.gid!=row['gid']:raise ValueError('archive mode/owner metadata '+name)
    if row['kind']=='file':
     if not member.isfile() or member.size!=row['bytes']:raise ValueError('archive file type/length')
     import hashlib
     h=hashlib.sha256();stream=tf.extractfile(member)
     for block in iter(lambda:stream.read(1048576),b''):h.update(block)
     if h.hexdigest()!=row['sha256']:raise ValueError('archive content checksum '+name)
    elif row['kind']=='directory':
     if not member.isdir():raise ValueError('archive directory type')
    elif not member.issym() or member.linkname!=row['target']:raise ValueError('archive link target')
  if seen!=set(expected):raise ValueError('archive membership incomplete')
  report.update(archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,package_manifest_sha256=sha(a.backup/'package-manifest.json'),source_manifest_sha256=sha(a.backup/'source-manifests.json'),archive_entries_checked=len(seen),metadata_entries_checked=metadata_entries)
  extracted=a.out/'extracted';extracted.mkdir()
  subprocess.run(['/usr/bin/tar','--acls','--xattrs','-xpf',str(archive),'-C',str(extracted)],check=True)
  if json.loads((extracted/'source-manifests.json').read_text())!=json.loads((a.backup/'source-manifests.json').read_text()):raise ValueError('embedded source/role manifest differs')
  restore_metadata(extracted,expected);compare(expected,inventory(extracted));report['fresh_archive_restore']='PASS all stored contents and metadata'
  # Restore an executable-relative directory layout; no original path is written.
  runtime=a.out/'runtime';(runtime/'metal_infer/prefill_probe').mkdir(parents=True)
  mapping={'metal_infer/infer-candidate-lazy32k':extracted/'historical-candidate','metal_infer/shaders.metal':extracted/'shader','metal_infer/gguf_iq_shared.h':extracted/'shared-header','metal_infer/prefill_probe/chunk_kernels.metal':extracted/'checkout-reference-sources/metal_infer/prefill_probe/chunk_kernels.metal'}
  required={}
  for rel,src in mapping.items():
   shutil.copy2(src,runtime/rel);required[rel]=sha(runtime/rel)
  if required['metal_infer/infer-candidate-lazy32k']!=HISTORICAL:raise ValueError('wrong historical executable')
  repo=P(__file__).resolve().parents[1]
  for rel in list(required)[1:]:
   content=subprocess.check_output(['git','show',SOURCE+':'+rel],cwd=repo)
   import hashlib
   if hashlib.sha256(content).hexdigest()!=required[rel]:raise ValueError('historical source dependency differs '+rel)
  for role in ['warm-state','warm-tools-cache']:
   subprocess.run(['/usr/bin/ditto','--rsrc','--extattr','--acl',str(extracted/role),str(runtime/role)],check=True)
   compare(inventory(extracted/role),inventory(runtime/role),ownership=False,staging_provenance=True)
  home=runtime/'home';home.mkdir()
  if (extracted/'home-state').exists():
   subprocess.run(['/usr/bin/ditto','--rsrc','--extattr','--acl',str(extracted/'home-state'),str(home/'.flash-moe')],check=True)
   compare(inventory(extracted/'home-state'),inventory(home/'.flash-moe'),ownership=False,staging_provenance=True)
  dylib=P('/opt/homebrew/opt/zstd/lib/libzstd.1.dylib')
  if sha(dylib)!=sha(extracted/'zstd'):raise ValueError('installed Zstd differs from backup')
  modelroot=P(model['root']);stamps={};total=0
  for name,row in model['files'].items():
   path=modelroot/name
   if P(name).is_absolute() or '..' in P(name).parts:raise ValueError('model path traversal')
   before=path.stat()
   if before.st_size!=row['bytes'] or sha(path)!=row['sha256']:raise ValueError('model content changed '+name)
   after=path.stat()
   if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('model changed during checksum')
   stamps[name]={'bytes':after.st_size,'inode':after.st_ino,'mtime_ns':after.st_mtime_ns};total+=after.st_size
   print('VERIFIED_MODEL_FILE',name,flush=True)
  # Exact selected old binary + runtime dependencies; explicit environment avoids
  # undocumented inherited flags. Legacy native context admission is NOT upgraded.
  selected={'schema':1,'selected_runtime':'historical infer-candidate-lazy32k','executable_sha256':HISTORICAL,'historical_source_association':SOURCE,'runtime_root':str(runtime.resolve()),'files':required,'model_root':str(modelroot),'model_manifest_path':str(a.model_manifest.resolve()),'model_manifest_sha256':sha(a.model_manifest),'model_stat':stamps,'zstd_path':str(dylib),'zstd_sha256':sha(dylib),'archive_sha256':report['archive_sha256'],'environment':{'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin','HOME':str(home.resolve()),'LANG':'en_US.UTF-8','TMPDIR':'/private/tmp'},'engine_args':['--tiered','--prefill-nrow','--timing'],'native_context_guard':'Historical engine cap65536; does not contain new qualified32K admission. Operational smoke is short; new candidate enforces32K natively.','resource_policy':{'host_reserve_bytes':6*1024**3,'rss_limit_exclusive_bytes':16*1024**3,'supervised_models':1},'software_rollback_only':True}
  (a.out/'selected-recovery.json').write_text(json.dumps(selected,indent=2)+'\n')
  report.update(status='PASS_CHECKSUMS_FRESH_RESTORE_AND_DEPENDENCIES',selected_manifest_sha256=sha(a.out/'selected-recovery.json'),model_files=len(stamps),model_bytes=total,runtime_files=required,zstd_sha256=sha(dylib),system_dependencies=subprocess.check_output(['otool','-L',str(runtime/'metal_infer/infer-candidate-lazy32k')],text=True),operational_model_test='NOT RUN BY THIS VERIFIER')
 except Exception as e:report['error']=str(e);raise
 finally:report['ended']=datetime.datetime.now().astimezone().isoformat();save()
 print('RECOVERY_VERIFIED',report['status'],flush=True)
if __name__=='__main__':main()
