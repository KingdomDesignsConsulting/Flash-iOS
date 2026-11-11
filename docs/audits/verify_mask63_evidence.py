#!/usr/bin/env python3
"""Read-only independent audit of private experimental evidence; no model/service access."""
import argparse,hashlib,json,math,pathlib,re,subprocess
P=pathlib.Path
ROOT=P(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(x,message):
 if not x:raise RuntimeError(message)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--evidence',type=P,required=True);ap.add_argument('--out',type=P,required=True);a=ap.parse_args();r=a.evidence
 m=json.loads((r/'release-manifest.json').read_text()); mh=sha(r/'release-manifest.json')
 g=json.loads((r/'repaired-32768/result.json').read_text());n=json.loads((r/'repaired-32768/native/nrow-oracle.json').read_text());meta=json.loads((r/'repaired-32768/native/result.json').read_text())
 require(g['status']=='PASS' and meta['status']=='PASS' and meta['exit']==0 and n['status']=='NUMERICAL_PASS','status/exit')
 require(g['release_manifest_sha256']==mh,'manifest binding')
 command=meta['command'];binary=P(command[0]);require(sha(binary)==m['binary_sha256']==g['binary_sha256']==meta['binary_sha256'],'binary binding')
 for name,h in m['source_sha256'].items():
  require(sha(ROOT/name)==h,'candidate source '+name);require(sha(r/'frozen-source'/name)==h,'frozen source '+name)
 require([x['position'] for x in n['rows']]==list(range(128,32769,128)),'endpoint coverage')
 maxima=[0,0,0];component_counts=set()
 for row in n['rows']:
  require(row['candidate_digest'] and row['candidate_digest']==row['reference_digest'],'fingerprint')
  require(all(row[k] for k in ['pass','finite','greedy_equal','kv_lengths_and_mirrors']),'row flags')
  vals=[row['state_max_abs'],row['hidden']['max_abs'],row['logits']['max_abs']]
  require(all(math.isfinite(v) and v>=0 for v in vals),'finite metrics')
  require(vals[0]<1e-3 and vals[1]<=1e-3 and vals[2]<=1e-2,'tolerances')
  maxima=[max(x,y) for x,y in zip(maxima,vals)]
  require(row['state_different']==0,'state different');component_counts.add(len(row['components']))
  for c in row['components']:
   require(c['different']==0 and c['nonfinite']==0 and c['max_abs']==0,'component state')
  require(row['hidden']['nonfinite']==row['logits']['nonfinite']==0,'outputs finite')
 routes={}
 for pos,layer,cap in re.findall(r'\[release-n128-attention\] seq=(\d+) layer=(\d+) cap=(\d+) backend=GPU',(r/'repaired-32768/native/engine.log').read_text()):
  require(int(cap)==32768,'GPU cap');routes.setdefault(int(pos),set()).add(int(layer))
 for pos in [8192,8193,16384,16385,24576,32768]:require(routes.get(pos)==set(range(3,40,4)),'GPU coverage '+str(pos))
 public=json.loads((ROOT/'docs/results/work-a-mask63-release-closure-2026-11-04.json').read_text())
 require(public['candidate_binary_sha256']==m['binary_sha256'] and public['release_manifest_sha256']==mh,'public source binding')
 result=dict(status='PASS',scope='Existing experimental evidence only; no inference rerun; no production access',candidate_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),manifest_sha256=mh,binary_sha256=m['binary_sha256'],runtime_source_files=len(m['source_sha256']),endpoints=len(n['rows']),components_per_endpoint=sorted(component_counts),max_errors=dict(state=maxima[0],hidden=maxima[1],logits=maxima[2]),gpu_routes={str(k):sorted(v) for k,v in routes.items()},artifact_sha256={p:sha(r/p) for p in ['repaired-32768/native/nrow-oracle.json','repaired-32768/native/result.json','repaired-32768/result.json','performance-closure.json']})
 a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
