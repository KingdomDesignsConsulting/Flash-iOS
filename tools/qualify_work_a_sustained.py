#!/usr/bin/env python3
"""Bounded paired substantial-output HTTP/resident and replacement qualification.
Actual output length is an acceptance criterion, never inferred from max_tokens.
"""
import argparse,threading
from session_gate_support import *
from work_a_manifest import verify_bound_build
from experiment_session_token_exact import collect
from qualify_session_accumulation import wait_bounded_process
from build_release_corpus import TECH
ACTIVE_OUT=None

def main():
 global ACTIVE_OUT
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=P,required=True);p.add_argument('--manifest',type=P,required=True);p.add_argument('--native-gate',type=P,required=True);p.add_argument('--out',type=P,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);ACTIVE_OUT=a.out;verify_bound_build(a.manifest,a.binary,a.native_gate)
 prompts=['Write a detailed guide of at least 600 words in twelve paragraphs explaining versioned journals, crash recovery, checksum validation, and safe publication. Include worked examples and tradeoffs.',
  'Now write at least twelve substantial paragraphs on GPU memory admission, ownership, command completion, and rollback. Explain each step with examples rather than providing a short summary.',
  'Now give a detailed 600-word worked example tracing a journal transaction through prefill, generation, cancellation, recovery, and a later successful continuation.',
  TECH*6+'Continue this technical article with at least 600 additional words and concrete examples.']
 report=dict(status='RUNNING',release_manifest_sha256=sha(a.manifest),binary_sha256=sha(a.binary),runner_sha256=sha(P(__file__)),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),max_completion_tokens=384,required_visible_deltas=128,required_completion_tokens=192,cases=[]);write(a.out/'result.json',report);records={};budgets={}
 for mode in ['scalar','mask63']:
  rows=[];budget=[];sid='sustained-'+uuid.uuid4().hex
  with server(a.out/mode,binary=a.binary.resolve(),args=['--no-prefill-nrow' if mode=='scalar' else '--prefill-nrow'],env_extra={'FLASH_FE027_NUMERICS':'63'}) as s:
   def monitor():
    code,peak,reason=wait_bounded_process(s['process'],2400,16*1024**3,host_free_floor=15);budget.append(dict(exit=code,peak_rss_bytes=peak,stop_reason=reason))
   watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
   for index,prompt in enumerate(prompts):
    request=dict(model='qwen3.5',messages=([SYS] if index in (0,3) else [])+[dict(role='user',content=prompt)],temperature=0,seed=73941,max_tokens=384,stream=True,stream_options=dict(include_usage=True),flash_trace_id='sustained-'+str(index))
    if index!=3:
     request['session_id']=sid
     if index==0:request['flash_session_create']=True
    if index==1:request['thinking_token_budget']=64
    else:request['reasoning_effort']='off'
    response=stream_request(request,timeout=600);st=state(s,request);generated=waitfile(s['trace']/(request['flash_trace_id']+'-generated.json'));rid=next(x['id'] for x in response['events'] if x.get('id'));_,pt=collect(s['trace'],{},rid,request['flash_trace_id'])
    deltas=sum(bool(c.get('delta',{}).get('content')) for e in response['events'] for c in e.get('choices',[]));length_ok=deltas>=128 and response['timings']['generated_tokens']>=192
    row=dict(index=index,request=request,response=response,state=st,generated=generated,prompt=pt,visible_content_deltas=deltas,sustained_length_pass=length_ok);rows.append(row);write(a.out/(mode+'-records.json'),dict(rows=rows))
    assert st['accepted'] and st['history_complete'] and not st['failed'] and st['end_position']<=4096
    assert all(point['kv_lengths_match'] and not any(part['nonfinite'] for part in point['components']) for point in st['steps'])
    assert response['timings']['session_reused']==(index in (1,2))
    if mode=='mask63' and index==3:assert any('batch_rows' in x for x in st['steps']),'Replacement must really execute N128'
    print('SUSTAINED_TURN',stamp(),mode,index,'position',st['end_position'],'completion',response['timings']['generated_tokens'],'visible_deltas',deltas,'length_pass',length_ok,flush=True)
  watcher.join(20);assert budget and budget[0]['stop_reason'] is None;records[mode]=rows;budgets[mode]=budget[0]
 for left,right in zip(records['scalar'],records['mask63']):
  assert left['prompt']['token_ids']==right['prompt']['token_ids'];assert left['generated']['sampled_token_ids']==right['generated']['sampled_token_ids'];assert left['state']['effective_token_ids']==right['state']['effective_token_ids']
  points={x['position']:x['digest'] for x in left['state']['steps']};assert all(points.get(x['position'])==x['digest'] for x in right['state']['steps'])
  assert left['response']['visible']==right['response']['visible']
  report['cases'].append(dict(index=right['index'],state_exact=True,sampled_tokens_exact=True,end_position=right['state']['end_position'],candidate_observed_positions=len(right['state']['steps']),completion_tokens=right['response']['timings']['generated_tokens'],visible_content_deltas=right['visible_content_deltas'],length_pass=right['sustained_length_pass'],candidate_timings=right['response']['timings'],scalar_timings=left['response']['timings'],diagnostic_timing_scope='Per-position SHA observers enabled; not uninstrumented throughput'))
 passed=all(x['length_pass'] for x in report['cases']);report.update(status='PASS' if passed else 'INSUFFICIENT_GENERATED_LENGTH',budgets=budgets,all_observed_states_exact=True,independent_generated_tokens_exact=True,thinking_on_case=1,resident_turns=3,stateless_replacement_nrow=True);write(a.out/'result.json',report);return 0 if passed else 5
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  if ACTIVE_OUT:
   file=ACTIVE_OUT/'result.json';report=load(file) if file.exists() else {};report.update(status='FAIL',error_type=type(error).__name__,error=str(error));write(file,report)
  raise
