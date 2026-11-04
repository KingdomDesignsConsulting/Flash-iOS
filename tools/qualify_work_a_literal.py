#!/usr/bin/env python3
"""Paired scalar/N128 literal diagnosis, followed by identical-token native CLI.
Does not change templates, model weights, adapters, or expected literal assertions.
"""
import argparse,re,struct,threading
from session_gate_support import *
from work_a_manifest import verify_bound_build
from experiment_session_token_exact import collect
from qualify_session_accumulation import wait_bounded_process
ACTIVE_OUT=None

def make_cases(messages):
 return [dict(name='original',messages=messages,options={},target='ADAPTER_FOLLOWUP_73941'),
  dict(name='latest-only',messages=[messages[0],messages[-1]],options={},target='ADAPTER_FOLLOWUP_73941'),
  dict(name='short-history',messages=[messages[0],dict(role='user',content='Reply exactly ADAPTER_73941.'),messages[-2],messages[-1]],options={},target='ADAPTER_FOLLOWUP_73941'),
  dict(name='distinct-literal',messages=messages[:-1]+[dict(role='user',content='Reply exactly BLUE.')],options={},target='BLUE'),
  dict(name='explicit-override',messages=messages[:-1]+[dict(role='user',content='The old answer is obsolete. For this turn reply exactly ADAPTER_FOLLOWUP_73941. Do not repeat ADAPTER_73941.')],options={},target='ADAPTER_FOLLOWUP_73941'),
  dict(name='thinking-off',messages=messages,options=dict(reasoning_effort='off'),target='ADAPTER_FOLLOWUP_73941'),
  dict(name='thinking-on',messages=messages,options=dict(thinking_token_budget=64),target='ADAPTER_FOLLOWUP_73941'),
  dict(name='sampling',messages=messages,options=dict(temperature=0.6,seed=73941),target='ADAPTER_FOLLOWUP_73941')]

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=P,required=True);p.add_argument('--sdk-record',type=P,required=True);p.add_argument('--manifest',type=P,required=True);p.add_argument('--native-gate',type=P,required=True);p.add_argument('--out',type=P,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out
 verify_bound_build(a.manifest,a.binary,a.native_gate)
 sdk=load(a.sdk_record);assert len(sdk['requests'])==2;cases=make_cases(sdk['requests'][1]['messages']);records={};budgets={};b=a.binary.resolve();report=dict(status='RUNNING',release_manifest_sha256=sha(a.manifest),binary_sha256=sha(b),runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),cases=[]);write(a.out/'result.json',report)
 for mode in ['scalar','mask63']:
  rows=[];budget=[]
  with server(a.out/mode,binary=b,args=['--no-prefill-nrow' if mode=='scalar' else '--prefill-nrow'],env_extra={'FLASH_FE027_NUMERICS':'63'}) as s:
   def monitor():
    code,peak,reason=wait_bounded_process(s['process'],1800,16*1024**3,host_free_floor=15);budget.append(dict(exit=code,peak_rss_bytes=peak,stop_reason=reason))
   watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
   for case in cases:
    req=dict(model='qwen3.5',messages=case['messages'],temperature=0,seed=73941,max_tokens=192,stream=True,stream_options=dict(include_usage=True),flash_trace_id='literal-'+case['name'],**{})
    req.update(case['options']);resp=stream_request(req,timeout=240);st=state(s,req);rid=next(x['id'] for x in resp['events'] if x.get('id'));_,prompt=collect(s['trace'],{},rid,req['flash_trace_id']);generated=waitfile(s['trace']/(req['flash_trace_id']+'-generated.json'))
    row=dict(name=case['name'],request=req,response=resp,state=st,prompt=prompt,generated=generated,literal_honored=resp['visible'].strip()==case['target']);rows.append(row);write(a.out/(mode+'-records.json'),dict(rows=rows))
    assert st['accepted'] and st['history_complete'] and not st['failed']
    assert all(point['kv_lengths_match'] and not any(part['nonfinite'] for part in point['components']) for point in st['steps'])
    print('LITERAL_CASE',stamp(),mode,case['name'],'literal_honored',row['literal_honored'],'generated',resp['timings']['generated_tokens'],flush=True)
  watcher.join(20);assert budget and budget[0]['stop_reason'] is None;records[mode]=rows;budgets[mode]=budget[0]
 for left,right in zip(records['scalar'],records['mask63']):
  same_inputs=left['prompt']['token_ids']==right['prompt']['token_ids'];assert same_inputs
  # Stochastic sampling is a controlled observation, not deterministic parity.
  deterministic=left['name']!='sampling';pointmap={x['position']:x['digest'] for x in left['state']['steps']}
  exact=left['state']['effective_token_ids']==right['state']['effective_token_ids'] and all(pointmap.get(x['position'])==x['digest'] for x in right['state']['steps'])
  same_samples=left['generated']['sampled_token_ids']==right['generated']['sampled_token_ids']
  if deterministic:assert exact and same_samples and left['response']['visible']==right['response']['visible']
  report['cases'].append(dict(name=left['name'],inputs_exact=same_inputs,deterministic=deterministic,state_exact=exact,sampled_ids_exact=same_samples,scalar_literal_honored=left['literal_honored'],candidate_literal_honored=right['literal_honored'],scalar_completion_tokens=left['response']['timings']['generated_tokens'],candidate_completion_tokens=right['response']['timings']['generated_tokens']))
 original=records['scalar'][0];ids=original['prompt']['token_ids'];fixture=a.out/'original-rendered.bin';fixture.write_bytes(struct.pack('<I',len(ids))+struct.pack('<'+'I'*len(ids),*ids));pre=gate()
 cmd=[str(b),'--model',MODEL,'--tiered','--no-prefill-nrow','--prompt-tokens',str(fixture),'--temperature','0','--seed','73941','--tokens','192'];print('LITERAL_CLI_START',stamp(),json.dumps(cmd),flush=True)
 with (a.out/'native-cli.log').open('w') as log:
  proc=subprocess.Popen(cmd,cwd=b.parent,env=dict(os.environ,FLASH_FE027_NUMERICS='63'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);code,peak,reason=wait_bounded_process(proc,300,16*1024**3,host_free_floor=15)
 print('LITERAL_CLI_STOP',stamp(),code,flush=True);assert code==0 and reason is None
 parsed=[int(x) for x in re.findall(r'\[gen \d+/\d+\] token_id=(\d+)',(a.out/'native-cli.log').read_text())];sampled=original['generated']['sampled_token_ids'];assert parsed and len(parsed)>=len(sampled)-1 and parsed==sampled[:len(parsed)]
 report.update(status='DIAGNOSIS_COMPLETE',budgets=budgets,native_cli=dict(exit=code,pre_gpu=pre,reported_sample_prefix_exact=True,reported_tokens=len(parsed),http_sampled_tokens=len(sampled),peak_rss_bytes=peak),classification='Incorrect original literal reproduced with identical native-rendered input in fresh scalar CLI, bypassing HTTP/SDK/session reuse; model/native-response behavior, not proven universal intrinsic model limitation',original_literal_failure_preserved=not original['literal_honored'],template_changed=False);write(a.out/'result.json',report);return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   file=ACTIVE_OUT/'result.json';report=load(file) if file.exists() else {};report.update(status='FAIL',error_type=type(error).__name__,error=str(error));write(file,report)
  raise
