#!/usr/bin/env python3
"""Freeze source/build/model identities without hashing enormous expert weights."""
import argparse,datetime,hashlib,json,pathlib,subprocess,struct,shutil
from run_session_state_mission import MODEL,sha
P=pathlib.Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--fixtures-root',type=P);a=p.parse_args();repo=P(__file__).resolve().parents[1]
 git=lambda *args:subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
 assert not git('status','--porcelain','--untracked-files=no'),'Tracked candidate must be clean'
 paths=git('ls-files','metal_infer').splitlines();sources={name:sha(repo/name) for name in paths if (repo/name).is_file() and P(name).suffix in ('.m','.h','.inc','.metal') or name=='metal_infer/Makefile'}
 artifacts={}
 for path in sorted(P(MODEL).iterdir()):
  if not path.is_file():continue
  st=path.stat();item=dict(bytes=st.st_size,inode=st.st_ino,mtime_ns=st.st_mtime_ns)
  if path.suffix=='.json' and st.st_size<=64*1024**2:item['sha256']=sha(path)
  artifacts[path.name]=item
 manifest=dict(schema=1,created=datetime.datetime.now().astimezone().isoformat(),head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),branch=git('branch','--show-current'),runtime_repair_commit='ac06b920dbb7e26b804480b36eea4dbe83b40d4e',binary_sha256=sha(a.binary),binary_bytes=a.binary.stat().st_size,source_sha256=sources,model_artifacts=artifacts,model_contract=dict(model='Qwen3.5-35B-A3B',quantization='tiered Q2/Q4',layers=40,experts=256,top_k=8),execution=dict(mask=63,nrow=128,gpu_kv_tokens=32768,backing='lazy shared KV',prefetch_enabled=True,ownership_revision='nrow-prefetch-ownership-v2',global_execution_version=3,layout_version=2,raw_format=1,zstd_storage_format=2,full_executable_in_cache_identity=False),build_command='make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-work-a-release',production_modified=False)
 a.out.parent.mkdir(parents=True,exist_ok=True)
 if a.fixtures_root:
  corpus=json.loads((a.fixtures_root/'corpus.json').read_text());manifest['fixtures']={}
  for count in (16384,32768):
   src=a.fixtures_root/f'technical-{count}.bin';data=src.read_bytes();assert len(data)==4*(count+1) and struct.unpack_from('<I',data)[0]==count
   expected=next(row for row in corpus['cases'] if row['count']==count);assert sha(src)==expected['fixture_sha256']
   dst=a.out.parent/src.name;assert src.resolve()!=dst.resolve() and not dst.exists();shutil.copy2(src,dst);manifest['fixtures'][str(count)]=dict(path=str(dst.resolve()),sha256=sha(dst),bytes=len(data))
 with a.out.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
 authoritative={}
 for name in ['config.json','tokenizer.bin','packed_experts_tiered/tiered_manifest.json']:
  path=P(MODEL)/name
  if path.exists():
   assert path.stat().st_size<=64*1024**2;authoritative[name]=dict(bytes=path.stat().st_size,sha256=sha(path))
 with a.out.with_name('authoritative-model-files.json').open('x') as f:json.dump(dict(release_manifest_sha256=sha(a.out),files=authoritative),f,indent=2);f.write('\n')
 print('MANIFEST',a.out,'binary',manifest['binary_sha256'],'sources',len(sources))
if __name__=='__main__':main()
