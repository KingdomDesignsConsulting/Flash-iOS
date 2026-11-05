"""Fail-closed binding for Work A builds, manifests and completed native evidence."""
import json,math,pathlib,re
from run_session_state_mission import MODEL,sha
P=pathlib.Path

def verify_native_gate(path,manifest_digest):
 gate=json.loads(path.read_text());assert gate['status']=='PASS' and gate['release_manifest_sha256']==manifest_digest
 native=json.loads((path.parent/'native/nrow-oracle.json').read_text());meta=json.loads((path.parent/'native/result.json').read_text());rows=native['rows']
 assert meta['status']=='PASS' and native['status']=='NUMERICAL_PASS' and native['completed_position']==32768 and len(rows)==256
 assert [row['position'] for row in rows]==list(range(128,32769,128))
 assert meta['binary_sha256']==gate['binary_sha256']
 for row in rows:
  errors=[row['state_max_abs'],row['hidden']['max_abs'],row['logits']['max_abs']]
  assert all(math.isfinite(x) and x>=0 for x in errors) and errors[0]<1e-3 and errors[1]<=1e-3 and errors[2]<=1e-2
  assert row['candidate_digest'] and row['candidate_digest']==row['reference_digest'] and row['pass'] and row['finite'] and row['greedy_equal'] and row['kv_lengths_and_mirrors']
 text=(path.parent/'native/engine.log').read_text();routes={}
 for n,l,c in re.findall(r'\[release-n128-attention\] seq=(\d+) layer=(\d+) cap=(\d+) backend=GPU',text):
  assert int(c)==32768;routes.setdefault(int(n),set()).add(int(l))
 for n in [8192,8193,16384,16385,24576,32768]:assert routes.get(n)==set(range(3,40,4)),('Missing actual candidate GPU boundary',n)
 return dict(status='PASS',endpoints=len(rows),actual_candidate_gpu_boundaries={str(k):sorted(v) for k,v in routes.items()},native_binary_sha256=meta['binary_sha256'])

def verify_bound_build(manifest_path,binary,native_gate):
 root=manifest_path.parent;manifest=json.loads(manifest_path.read_text());digest=sha(manifest_path);repo=P(__file__).resolve().parents[1]
 for name,h in manifest['source_sha256'].items():assert sha(repo/name)==h,'Frozen runtime changed: '+name
 expected=manifest['binary_sha256']
 if sha(binary)!=expected:
  variants=json.loads((root/'build-variants.json').read_text());assert variants['release_manifest_sha256']==digest;assert variants['variants'][binary.name]['sha256']==sha(binary),'Unauthenticated build'
 for name,meta in manifest['model_artifacts'].items():
  stat=(P(MODEL)/name).stat();assert (stat.st_size,stat.st_ino,stat.st_mtime_ns)==(meta['bytes'],meta['inode'],meta['mtime_ns']),'Model artifact changed'
 authoritative=json.loads((root/'authoritative-model-files.json').read_text());assert authoritative['release_manifest_sha256']==digest
 for name,meta in authoritative['files'].items():assert sha(P(MODEL)/name)==meta['sha256']
 gate=verify_native_gate(native_gate,digest);assert gate['native_binary_sha256']==expected
 return gate
