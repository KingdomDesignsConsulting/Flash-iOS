#!/usr/bin/env python3
"""Read-only source capture + private complete-tree backup/rehearsal. No service control.

Requires operator-confirmed exclusive window, absence of visible cache users,
pre/post content inventories. A manual recovery proposal is NOT operator approval.
"""
import argparse,datetime,json,os,shutil,subprocess,tarfile,posixpath,time
from pathlib import Path
from recovery_tree import inventory,compare,sha,copy_xattrs,restore_metadata

def writer_check(roots):
 observed=[]
 for root in roots:
  p=subprocess.run(['lsof','-nP','+D',str(root),'-Fpcfan'],capture_output=True,text=True,timeout=30)
  if p.returncode not in [0,1] or p.stderr.strip():raise RuntimeError('quiescence inspection failed: '+p.stderr[:200])
  if p.stdout.strip():raise RuntimeError('cache users visible; refusing snapshot')
  observed.append({'root':str(root),'no_open_users_visible':True})
 return observed

def safe_archive(path):
 seen=set()
 with tarfile.open(path,'r|') as tf:
  for m in tf:
   n=posixpath.normpath(m.name)
   if n in seen:raise ValueError('duplicate archive entry')
   seen.add(n)
   if n.startswith('/') or n=='..' or n.startswith('../'):raise ValueError('archive traversal')
   if not (m.isdir() or m.isfile() or m.issym() or m.islnk()):raise ValueError('archive special entry')
   if m.issym() or m.islnk():
    target=posixpath.normpath(posixpath.join(posixpath.dirname(n) if m.issym() else '',m.linkname))
    if m.linkname.startswith('/') or target=='..' or target.startswith('../'):raise ValueError('unsafe archive link')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,required=True);p.add_argument('--project',type=Path,required=True);p.add_argument('--model',type=Path,required=True);p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('--resume-incomplete',action='store_true');a=p.parse_args()
 if not a.operator_exclusive_model:p.error('exclusive window required')
 root=a.destination.resolve();project=a.project.resolve()
 if root==project or project in root.parents:p.error('non-production destination required')
 if root.exists():
  if not a.resume_incomplete or root.is_symlink() or root.stat().st_uid!=os.getuid():p.error('fresh destination or explicit owned incomplete resume required')
  old=json.loads((root/'recovery-report.json').read_text())
  if old.get('status')!='INCOMPLETE':p.error('only incomplete capture may resume')
  shutil.copy2(root/'recovery-report.json',root/('previous-attempt-'+str(time.time_ns())+'.json'))
 os.umask(0o077);root.mkdir(mode=0o700,parents=True,exist_ok=a.resume_incomplete);package=root/'package';package.mkdir(exist_ok=a.resume_incomplete)
 report={'status':'INCOMPLETE','started':datetime.datetime.now().astimezone().isoformat(),'production_modified':False,'operator_recovery_acceptance':'PENDING','disaster_recovery_independence':'NOT SATISFIED: local same-disk copy','roles':{},'errors':[]}
 def save():(root/'recovery-report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 try:
  caches=[project/'warm-state',project/'warm-tools-cache']
  home=Path.home()/'.flash-moe'
  if home.exists():caches.append(home)
  report['quiescence_before']=writer_check(caches)
  sources={'warm-state':caches[0],'warm-tools-cache':caches[1],'old-infer':project/'metal_infer/infer','historical-candidate':project/'metal_infer/infer-candidate-lazy32k','shader':project/'metal_infer/shaders.metal','shared-header':project/'metal_infer/gguf_iq_shared.h','zstd':Path('/opt/homebrew/opt/zstd/lib/libzstd.1.dylib').resolve()}
  if home.exists():sources['home-state']=home
  manifests={}
  for role,source in sources.items():
   print('CAPTURE_ROLE',role,flush=True);before=inventory(source)
   if not (package/role).exists():subprocess.run(['/usr/bin/ditto','--rsrc','--extattr','--acl',str(source),str(package/role)],check=True)
   compare(before,inventory(source))
   for rel in before:
    src=source if rel=='.' else source/rel;dst=package/role if rel=='.' else package/role/rel
    copy_xattrs(src,dst)
   stored=inventory(package/role)
   owner_exact=True
   try:compare(before,stored)
   except ValueError:
    compare(before,stored,ownership=False,staging_provenance=True);owner_exact=False
   manifests[role]={'original_absolute_path':str(source),'entries':before,'stored_entries':stored,'owners_exact':owner_exact}
   report['roles'][role]={'entries':len(before),'bytes':sum(e.get('bytes',0) for e in before.values()),'owners_exact':owner_exact}
   save()
  # Metadata and exact small authoritative model files; weights remain external.
  model_entries={}
  for path in sorted(a.model.rglob('*')):
   if not path.is_file() or '.cache' in path.parts or path.name=='.DS_Store':continue
   st=path.stat();item={'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'inode':st.st_ino}
   if st.st_size<=64*1024*1024:
    item['sha256']=sha(path)
    copy=package/'model-metadata'/path.relative_to(a.model);copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,copy)
    if sha(copy)!=item['sha256']:raise ValueError('model metadata copy mismatch')
   model_entries[str(path.relative_to(a.model))]=item
  report['model_policy']='Original path + size/mtime/inode for large weights; authoritative small files content-hashed. External weights NOT independently backed up; requires explicit acceptance.'
  model={'original_absolute_path':str(a.model),'files':model_entries,'large_weights_full_hash':False}
  (package/'model-dependencies.json').write_text(json.dumps(model,indent=2)+'\n')
  config={'status':'PROPOSED MANUAL RECOVERY; OPERATOR ACCEPTANCE REQUIRED','cwd':str(project/'metal_infer'),'argv':['./infer-candidate-lazy32k','--model',str(a.model),'--tiered','--serve','11241','--prefill-nrow','--timing'],'inherited_environment':'UNRECORDED','source_association':'3a87663a72c6c88922dbd7fd9f82842e588a5dc6','latest_launcher':'UNPROVEN','resident_sessions':'Resend full history/new IDs after restart'}
  (package/'proposed-manual-recovery.json').write_text(json.dumps(config,indent=2)+'\n')
  # Preserve tracked runtime reconstruction inputs separately, without alleging
  # that the live checkout produced either old executable.
  srcdir=package/'checkout-reference-sources';srcdir.mkdir(exist_ok=a.resume_incomplete)
  names=subprocess.check_output(['git','ls-files','metal_infer'],cwd=project,text=True).splitlines()
  for name in names:
   src=project/name
   if src.is_file() and (src.suffix in ['.m','.h','.inc','.metal'] or src.name=='Makefile'):
    dst=srcdir/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  hist=project/'Testing/gpu-32k-attention/integration-gate-02'
  for name in ['report.json','http/build.log']:
   src=hist/name
   if src.is_file():shutil.copy2(src,package/('historical-'+src.name))
  report['quiescence_after']=writer_check(caches)
  for role,source in sources.items():compare(manifests[role]['entries'],inventory(source))
  (root/'source-manifests.json').write_text(json.dumps(manifests,indent=2)+'\n')
  (package/'source-manifests.json').write_text(json.dumps(manifests,indent=2)+'\n')
  expected=inventory(package);(root/'package-manifest.json').write_text(json.dumps(expected,indent=2)+'\n')
  archive=root/'recovery.tar'
  if archive.exists():raise ValueError('retaining existing archive; refusing overwrite')
  subprocess.run(['/usr/bin/tar','--acls','--xattrs','-cpf',str(archive),'-C',str(package),'.'],check=True)
  report['archive_sha256']=sha(archive);report['archive_bytes']=archive.stat().st_size
  safe_archive(archive)
  restored=root/'restored';restored.mkdir()
  subprocess.run(['/usr/bin/tar','--acls','--xattrs','-xpf',str(archive),'-C',str(restored)],check=True)
  restore_metadata(restored,expected)
  restored_inventory=inventory(restored)
  try:compare(expected,restored_inventory)
  except ValueError:
   compare(expected,restored_inventory,staging_provenance=True)
   report['restore_os_metadata_exception']='Only OS-added com.apple.provenance absent in or differs under OS policy; original xattr hashes preserved in source manifest'
  report['offline_tree_restore']='PASS all package entries, bytes, modes, mtime, flags, ACLs, uid/gid as stored; xattr exceptions explicitly recorded if present'
  report['source_metadata_policy']='Original owner/xattr metadata retained in source-manifests; staging may have changed uid/gid and OS-added com.apple.provenance. Full original-metadata recovery acceptance remains pending.'
  report['source_owners_exact']=all(x['owners_exact'] for x in manifests.values())
  report['status']='VERIFIED_LOCAL_TREE_PACKAGE_PENDING_RECOVERY_POLICY'
 except Exception as e:
  report['errors'].append(type(e).__name__+': '+str(e));raise
 finally:
  report['ended']=datetime.datetime.now().astimezone().isoformat();save()
 print('RECOVERY_RESULT',report['status'],flush=True)
if __name__=='__main__':main()
