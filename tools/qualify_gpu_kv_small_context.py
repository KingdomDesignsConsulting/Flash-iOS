#!/usr/bin/env python3
"""Exercise allocated score stride below compile-time GPU cap with Metal validation."""
import argparse,json,os,pathlib,re,struct,subprocess
from qualify_gpu_16k import MODEL,sha
P=pathlib.Path
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=P,required=True);a=ap.parse_args()
root=P(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
fixture=root/'Testing/Temporary Testing Files/Resources/prefill-1k-1024.bin'
b=fixture.read_bytes();tokens=struct.unpack_from('<65I',b,4)
prompt=a.out/'prompt65.bin';prompt.write_bytes(struct.pack('<66I',65,*tokens))
rows=[]
for arm,capacity in [('8k',128),('16k',128),('lazy16k',128),('lazy16k',65536)]:
 env=os.environ.copy();env.update(FLASH_QUAL_CONTEXT=str(capacity),MTL_DEBUG_LAYER='1')
 command=[str(root/'metal_infer'/('infer-qual-'+arm)),'--model',MODEL,'--tiered','--no-malloc-cache','--no-expert-prefetch','--prompt-tokens',str(prompt),'--tokens','4']
 log=a.out/f'{arm}-{capacity}.log'
 with log.open('w') as f:r=subprocess.run(command,cwd=root/'metal_infer',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=120)
 text=log.read_text(errors='replace');ids=list(map(int,re.findall(r'token_id=(\d+)',text)))
 row=dict(arm=arm,capacity=capacity,exit=r.returncode,reported_tokens=ids,log=str(log),binary_sha256=sha(root/'metal_infer'/('infer-qual-'+arm)))
 rows.append(row)
 if r.returncode or len(ids)!=3 or re.search('failed assertion|Invalid device|out.of.bounds|ERROR:',text,re.I):raise RuntimeError(row)
assert all(x['reported_tokens']==rows[0]['reported_tokens'] for x in rows)
(a.out/'report.json').write_text(json.dumps({'result':'PASS','note':'CLI reports three subsequent sampled IDs for four requested tokens','runs':rows},indent=2))
print(json.dumps({'result':'PASS','runs':rows},indent=2))
