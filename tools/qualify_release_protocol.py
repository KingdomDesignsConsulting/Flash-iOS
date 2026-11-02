#!/usr/bin/env python3
"""Bounded paired buffered/SSE API checks with actual native token traces."""
import argparse
from experiment_session_token_exact import collect
from qualify_release_stream_faults import stream
from session_gate_support import *
def normalized(message):
 tools=[]
 for t in message.get('tool_calls',[]):
  f=t['function'];tools.append(dict(name=f['name'],arguments=json.loads(f['arguments'])))
 return dict(content=message.get('content') or '',reasoning_content=message.get('reasoning_content') or '',tools=tools)
def buffered(events):
 msg={'content':'','reasoning_content':'','tool_calls':[]};tools={};finish=None;usage=None;rid=None
 for e in events:
  if not isinstance(e,dict):continue
  assert 'error' not in e,e
  rid=rid or e.get('id')
  if e.get('usage'):usage=e['usage']
  for ch in e.get('choices',[]):
   if ch.get('finish_reason'):finish=ch['finish_reason']
   d=ch.get('delta',{})
   for key in ['content','reasoning_content']:msg[key]+=d.get(key) or ''
   for t in d.get('tool_calls',[]):
    f=tools.setdefault(t['index'],{'name':'','arguments':''});delta=t.get('function',{})
    for key in f:f[key]+=delta.get(key) or ''
 msg['tool_calls']=[dict(function=tools[k]) for k in sorted(tools)]
 return rid,normalized(msg),finish,usage

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=P);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);records=[]
 tools=[dict(type='function',function=dict(name='echo',description='Echo a supplied synthetic payload.',parameters=dict(type='object',properties={'payload':{'type':'string'}},required=['payload'],additionalProperties=False)))]
 cases=[('plain-off',False,None,'Reply exactly STATE-73941.'),('plain-on',True,None,'Compute 17 times 23 and give the answer.'),('tool-off',False,tools,'Use echo once with payload exactly ok.'),('tool-on',True,tools,'Use echo once with payload exactly ok.'),('content-and-tool',False,tools,'First say Checking. Then use echo once with payload exactly ok.')]
 with server(a.out/'server',args=['--prefill-nrow']) as s:
  for name,thinking,ts,prompt in cases:
   b=body([SYS,{'role':'user','content':prompt}],'protocol-'+uuid.uuid4().hex,True);b.update(max_tokens=64,reasoning_effort='high' if thinking else 'off')
   if thinking:b['thinking_token_budget']=1
   if ts:b['tools']=ts
   code,reply=call(b);assert code==200,(name,code,reply)
   rid=reply['id'];_,pt=collect(s['trace'],{},rid,b['flash_trace_id'],'prompt');_,gen=collect(s['trace'],{},rid,b['flash_trace_id'],'generated');st=state(s,b)
   b.update(session_id='protocol-'+uuid.uuid4().hex,flash_trace_id='protocol-'+uuid.uuid4().hex,stream=True,stream_options={'include_usage':True})
   code,events,raw=stream(b);(a.out/(name+'.sse')).write_text(raw);assert code==200 and events[-1]=='[DONE]' and events.count('[DONE]')==1
   srid,sm,finish,usage=buffered(events);_,sp=collect(s['trace'],{},srid,b['flash_trace_id'],'prompt');_,sg=collect(s['trace'],{},srid,b['flash_trace_id'],'generated');sst=state(s,b)
   n=normalized(reply['choices'][0]['message']);assert sm==n,(name,'normalized events',n,sm)
   assert finish==reply['choices'][0]['finish_reason'];assert usage==reply['usage'],(name,'usage',usage,reply['usage'])
   assert sp['token_ids']==pt['token_ids'] and sg['sampled_token_ids']==gen['sampled_token_ids'],(name,'native tokens')
   equal(st,sst)
   assert usage['prompt_tokens']==pt['prompt_tokens'] and usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
   ui=[i for i,e in enumerate(events) if isinstance(e,dict) and e.get('usage')];assert ui and max(ui)<len(events)-1
   actual=bool(n['tools']);started=248058 in gen['sampled_token_ids'];assert not started or actual or reply.get('session_invalidated'),(name,'tool marker silently dropped')
   records.append(dict(case=name,status='PASS',finish_reason=finish,prompt_tokens=pt['prompt_tokens'],generated_tokens=gen['completion_tokens'],native_prompt_and_sampled_ids_equal=True,normalized_events_equal=True,resident_state_equal=True,usage_before_done=True,structured_tool_call=actual,tool_start_token_emitted=started,content_plus_tool_observed=bool(n['content']) and actual,buffered_timings=reply.get('flash_timings'),stream_usage=usage))
   write(a.out/'result.json',dict(status='RUNNING',cases=records))
 write(a.out/'result.json',dict(status='PASS',cases=records,external_tools_executed=False,lm_studio_adapter='NOT RUN',content_plus_tools='Observed only if content_plus_tool_observed=true; otherwise model did not produce requested combination.'))
 return 0
if __name__=='__main__':raise SystemExit(main())
