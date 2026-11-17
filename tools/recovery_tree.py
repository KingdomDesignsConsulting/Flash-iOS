#!/usr/bin/env python3
"""Streaming, model-free tree inventory/comparison. No production writes.

The manifest is a trusted input, not its own authentication authority. symlinks
must stay within a role root; special files and unrecorded entries fail closed.
"""
import argparse,ctypes,hashlib,json,os,re,stat,subprocess
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def xattr_values(p):
 if hasattr(os,'listxattr'):
  return {k:os.getxattr(p,k,follow_symlinks=False) for k in sorted(os.listxattr(p,follow_symlinks=False))}
 if os.uname().sysname!='Darwin':raise RuntimeError('xattr enumeration unavailable')
 libc=ctypes.CDLL(None,use_errno=True)
 libc.listxattr.restype=ctypes.c_ssize_t
 libc.listxattr.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int]
 libc.getxattr.restype=ctypes.c_ssize_t
 libc.getxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]
 path=os.fsencode(p);size=libc.listxattr(path,None,0,1)
 if size<0:raise OSError(ctypes.get_errno(),'listxattr failed',str(p))
 buf=ctypes.create_string_buffer(size)
 if libc.listxattr(path,buf,size,1)!=size:raise OSError('xattr enumeration changed')
 result={}
 for name in sorted(n for n in buf.raw.split(b'\0') if n):
  n=libc.getxattr(path,name,None,0,0,1)
  if not 0<=n<=64*1024*1024:raise OSError('invalid xattr size')
  value=ctypes.create_string_buffer(n)
  if libc.getxattr(path,name,value,n,0,1)!=n:raise OSError('xattr changed')
  result[os.fsdecode(name)]=value.raw
 return result

def xattr_hashes(p):
 return {k:hashlib.sha256(v).hexdigest() for k,v in xattr_values(p).items()}

def copy_xattrs(source,destination):
 # Caller constrains destination to a fresh private tree, never source paths.
 expected=xattr_values(source);actual=xattr_values(destination)
 libc=ctypes.CDLL(None,use_errno=True)
 libc.removexattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
 libc.setxattr.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_int]
 for name in actual.keys()-expected.keys():
  if libc.removexattr(os.fsencode(destination),os.fsencode(name),1)!=0:raise OSError(ctypes.get_errno(),'private xattr removal failed')
 for name,value in expected.items():
  if actual.get(name)!=value:
   buf=ctypes.create_string_buffer(value)
   if libc.setxattr(os.fsencode(destination),os.fsencode(name),buf,len(value),0,1)!=0:raise OSError(ctypes.get_errno(),'private xattr restore failed')

def metadata(p):
 s=p.lstat()
 result=dict(mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid,mtime_ns=s.st_mtime_ns,flags=getattr(s,'st_flags',0))
 result['xattrs']=xattr_hashes(p)
 if os.uname().sysname=='Darwin':
  a=subprocess.run(['/bin/ls','-lde',str(p)],capture_output=True,text=True,check=True)
  result['acl']=[line.strip() for line in a.stdout.splitlines() if re.match(r'^\s*\d+:',line)]
 else:result['acl']=[]
 return result

def inventory(root):
 root=Path(root).absolute()
 if root.is_symlink():raise ValueError('role root may not be a symlink')
 entries={}
 def walk(p,rel):
  before=p.lstat();row=metadata(p)
  if stat.S_ISLNK(before.st_mode):
   target=os.readlink(p)
   if os.path.isabs(target) or os.path.commonpath([str((p.parent/target).resolve()),str(root.resolve())]) != str(root.resolve()):raise ValueError('unsafe symlink '+str(p))
   row.update(kind='symlink',target=target)
  elif stat.S_ISDIR(before.st_mode):
   row['kind']='directory'
   for child in sorted(p.iterdir()):walk(child,rel+'/'+child.name if rel!='.' else child.name)
  elif stat.S_ISREG(before.st_mode):
   row.update(kind='file',bytes=before.st_size,sha256=sha(p))
  else:raise ValueError('unsupported special file '+str(p))
  after=p.lstat()
  if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('tree changed during inventory '+str(p))
  entries[rel]=row
 walk(root,'.')
 return entries

def compare(expected,actual,ownership=True):
 if expected.keys()!=actual.keys():raise ValueError('missing/unexpected tree entries')
 for key in expected:
  a=dict(expected[key]);b=dict(actual[key])
  if not ownership:
   for name in ['uid','gid']:a.pop(name,None);b.pop(name,None)
  if a!=b:raise ValueError('metadata/content mismatch at '+key+' fields '+str([k for k in a if a.get(k)!=b.get(k)]))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--original-path');p.add_argument('--role');p.add_argument('--verify',action='store_true');p.add_argument('--allow-staging-owner',action='store_true');a=p.parse_args()
 if a.verify:
  m=json.loads(a.manifest.read_text());compare(m['entries'],inventory(a.root),not a.allow_staging_owner);print('PASS: complete tree '+('including owners' if not a.allow_staging_owner else 'OWNER EXCLUDED; staging-only'))
 else:
  if not a.role or not a.original_path or not Path(a.original_path).is_absolute():p.error('capture requires role and original absolute path')
  with a.manifest.open('x') as f:json.dump(dict(schema=1,role=a.role,original_absolute_path=a.original_path,entries=inventory(a.root)),f,indent=2);f.write('\n')
if __name__=='__main__':main()
