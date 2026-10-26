#!/usr/bin/env python3
"""Sequential paired live benchmark on an EXISTING isolated protocol server.
Never starts/stops a model. Does not qualify KV/GDN equality from answer parity.
"""
import argparse,json,pathlib,time,uuid,urllib.request,urllib.parse,statistics,subprocess
def gpu():
 import re
 r=subprocess.run(['ioreg','-r','-c','AGXAccelerator','-d','1'],capture_output=True,text=True,timeout=10)
 m=re.search(r'"Device Utilization %"\s*=\s*(\d+)',r.stdout)
 return int(m.group(1)) if m else None
def call(base,messages,sid=None,create=False):
 b=dict(model='qwen3.5',messages=messages,temperature=0,reasoning_effort='off',max_tokens=32,stream=True,stream_options={'include_usage':True})
 if sid:b['session_id']=sid
 if create:b['flash_session_create']=True
 request=urllib.request.Request(base.rstrip('/')+'/chat/completions',json.dumps(b).encode(),{'Content-Type':'application/json'})
 started=time.monotonic();first=None;chunks=[];content='';done=False
 with urllib.request.urlopen(request,timeout=600) as response:
  assert response.headers.get_content_type()=='text/event-stream'
  for line in response:
   if not line.startswith(b'data:'):continue
   raw=line[5:].strip()
   if raw==b'[DONE]':done=True;break
   x=json.loads(raw);assert not x.get('error') and not x.get('session_invalidated'),x
   chunks.append(x)
   for c in x.get('choices',[]):
    text=c.get('delta',{}).get('content','')
    if text and first is None:first=(time.monotonic()-started)*1000
    content+=text
 assert done and any(c.get('finish_reason') in ('stop','length') for x in chunks for c in x.get('choices',[]))
 timings=next(x['flash_timings'] for x in reversed(chunks) if 'flash_timings' in x)
 return dict(content=content,ttft_ms=first,elapsed_ms=(time.monotonic()-started)*1000,timings=timings,usage=next(x['usage'] for x in reversed(chunks) if x.get('usage')))
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:11243/v1');p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--rounds',type=int,default=2);p.add_argument('--document-lines',type=int,default=0);a=p.parse_args()
 url=urllib.parse.urlparse(a.base);assert url.hostname=='127.0.0.1' and url.port!=11241,'Dedicated loopback experiment only; production 11241 forbidden'
 readings=[]
 for _ in range(3):readings.append(gpu());time.sleep(.3)
 assert all(x is not None and x<30 for x in readings),readings
 a.out.parent.mkdir(parents=True,exist_ok=True);records=[]
 for i in range(a.rounds):
  code='ORBIT-73941';sid='bench-'+uuid.uuid4().hex
  document=('Reference document: the test code is '+code+'.\n')*a.document_lines
  initial={'role':'user','content':document+'\nRemember the test code '+code+'. Reply exactly READY.'}
  follow={'role':'user','content':'What is the test code? Reply only the exact code.'}
  created=call(a.base,[initial],sid,True);continued=call(a.base,[follow],sid)
  full=[initial,{'role':'assistant','content':created['content']},follow]
  control=call(a.base,full)
  assert continued['timings']['session_reused'] and not control['timings']['session_reused']
  assert continued['content'].strip()==control['content'].strip()==code,(continued,control)
  # Exact resident replay after replacement, using the same actual first turn.
  new_id='replay-'+uuid.uuid4().hex
  anchor=call(a.base,[initial],new_id,True);replay=call(a.base,[follow],new_id)
  assert anchor['content']==created['content'] and replay['content']==continued['content']
  if a.document_lines:assert created['usage']['prompt_tokens']>=4800,created
  records.append(dict(round=i,create=created,continuation=continued,stateless=control,replay_create=anchor,replay=replay,recovery_total_ms=anchor['elapsed_ms']+replay['elapsed_ms'],gpu_after=gpu()))
  report=dict(result='PASS',pre_gpu=readings,document_lines=a.document_lines,records=records,confidence='exploratory; no uncontended performance claim',state_parity='NOT MEASURED: raw canonical and resident token histories may differ')
  for key in ('ttft_ms','elapsed_ms'):
   report[key]={arm:{'median':statistics.median(r[arm][key] for r in records),'min':min(r[arm][key] for r in records),'max':max(r[arm][key] for r in records)} for arm in ('continuation','stateless','replay')}
  a.out.write_text(json.dumps(report,indent=2));print('PAIRED_PASS',i,created['usage']['prompt_tokens'],continued['timings']['prefill_tokens'],control['timings']['prefill_tokens'],flush=True)
if __name__=='__main__':main()
