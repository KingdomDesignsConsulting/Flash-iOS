#!/usr/bin/env python3
"""Build private legal histories using infer's unchanged native renderer/tokenizer.
Render-only mode never loads model weights or initializes Metal.
"""
import argparse,json,os,pathlib,struct,subprocess,hashlib
from run_session_state_mission import MODEL,sha,stamp
P=pathlib.Path
TECH='A distributed storage service records immutable versions in a journal. Each transaction carries a sequence number and a checksum. Readers validate the complete record before publishing a new index. If an interrupted write leaves a partial suffix, recovery retains the last committed version. The diagnostic compares independent snapshots instead of assuming that a successful response proves durable state. '
CODE='def merge_counts(left, right):\n    result = dict(left)\n    for key, value in right.items():\n        result[key] = result.get(key, 0) + value\n    return result\n# Input: {"north": 3, "south": 5}; check empty keys and duplicate values.\n'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--model',default=MODEL);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 sys={'role':'system','content':'You are a helpful assistant.'}
 user=lambda text:dict(role='user',content=text)
 tools=[dict(type='function',function=dict(name='lookup',description='Retrieve a synthetic inventory record by key.',parameters=dict(type='object',properties={'key':{'type':'string'}},required=['key'],additionalProperties=False)))]
 conversation=[sys]
 for i in range(18):conversation += [user(f'For experiment {i}, retain the label ORBIT-{i} and explain how a versioned journal prevents partial reads.'),dict(role='assistant',content=f'Experiment {i} uses complete records and checksums. The previous committed version remains available after interruption.')]
 conversation += [user('Compare the final two experiments without changing their labels.')]
 cases=[dict(name='technical',messages=[sys,user(TECH*10)]),dict(name='programming',messages=[sys,user(CODE*14+'Explain the invariants and propose tests.')]),dict(name='conversation',messages=conversation),dict(name='reasoning',thinking=True,messages=[sys,user(('A train travels 17 kilometers in 23 minutes. Compare three exact rational ways to compute the distance after another 19 minutes, keeping units explicit. '*18)+'Explain each assumption before answering.')]),dict(name='tools',tools=tools,messages=[sys,user(TECH*6+'Look up the synthetic key A17.'),dict(role='assistant',content='',tool_calls=[dict(id='call-inventory',type='function',function=dict(name='lookup',arguments='{"key":"A17"}'))]),dict(role='tool',tool_call_id='call-inventory',content='{"key":"A17","count":9,"status":"complete"}'),user('Summarize the returned record and explain the integrity checks.')]),dict(name='structured-stress',stress_only=True,messages=[sys,user('\n'.join(f'row={i:04d}; group={i%13}; checksum={(i*37)%997}; state=complete; owner=synthetic' for i in range(80)))])]
 manifest=dict(started=stamp(),binary_sha256=sha(a.binary),serialization='unchanged native Qwen renderer/tokenizer, explicit system, complete generation prompt',cases=[])
 def render(cs,label):
  inp=a.out/(label+'-input.json');out=a.out/(label+'-render.json');inp.write_text(json.dumps(dict(cases=cs)))
  env=dict(os.environ,FLASH_SESSION_RENDER_INPUT=str(inp.resolve()),FLASH_SESSION_RENDER_OUTPUT=str(out.resolve()))
  with (a.out/(label+'-render.log')).open('w') as f:r=subprocess.run([str(a.binary.resolve()),'--model',a.model,'--tiered'],cwd=a.binary.resolve().parent,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=60)
  assert r.returncode==0,(label,r.returncode);x=json.loads(out.read_text());assert not x['model_loaded'] and not x['metal_initialized'];return x['cases']
 def store(c,row):
  ids=row['token_ids'];f=a.out/(c['name']+'.bin');f.write_bytes(struct.pack('<I',len(ids))+struct.pack('<'+'I'*len(ids),*ids));manifest['cases'].append(dict(name=c['name'],count=len(ids),fixture=str(f.resolve()),fixture_sha256=sha(f),rendered_sha256=hashlib.sha256(row['rendered'].encode()).hexdigest(),stress_only=c.get('stress_only',False),thinking=c.get('thinking',False)));print(c['name'],len(ids),flush=True)
 rows=render(cases,'independent')
 for c,row in zip(cases,rows):store(c,row)
 # Complete native-rendered histories at exact context lengths; no ID truncation.
 words=TECH.split()
 for target in [16384,32768]:
  n=int(target*.65);text=' '.join((words*((n+len(words)-1)//len(words)))[:n]);done=False
  for attempt in range(16):
   c=dict(name=f'technical-{target}',messages=[sys,user(text)]);row=render([c],f'long-{target}-{attempt}')[0];delta=target-row['count']
   if delta==0:store(c,row);done=True;break
   if delta>0:text+=' x'*delta
   else:text=' '.join(text.split()[:max(1,len(text.split())+delta)])
  assert done,('Cannot construct exact legal history',target)
 manifest['ended']=stamp();(a.out/'corpus.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
