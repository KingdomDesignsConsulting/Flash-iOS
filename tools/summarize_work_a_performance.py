#!/usr/bin/env python3
"""Sanitize completed Work A performance evidence without upgrading partial trials."""
import argparse,json,pathlib,hashlib
P=pathlib.Path

def load(p):return json.loads(p.read_text())
def case(c):
 r=c.get('result',c)
 return dict(label=c['label'],started=c.get('started'),ended=c.get('ended'),timings=r['timings'],wire_ttft_ms=r['wire_ttft_ms'],wall_ms=r['wall_ms'],allocation=c['allocation'],host_phases=c.get('nrow_host_phases',{}))
def build(root,completion=None,validation=None):
 a=load(root/'performance-resume-20261106-16384/result.json');b=load(root/'performance-resume-20261106-32768/result.json')
 assert a['status']=='COMPLETED_EXPLORATORY' and {x['mode'] for x in a['rows']}=={'ordinary','mask63','scalar'} and a['repeats']==1
 assert b['status']=='STOPPED' and b['error_type']=='BrokenPipeError' and [x['mode'] for x in b['rows']]==['ordinary']
 assert a['release_manifest_sha256']==b['release_manifest_sha256']
 rows=[]
 for count,d in [(16384,a),(32768,b)]:
  for row in d['rows']:
   assert row['budget']['stop_reason'] is None
   assert [c['label'] for c in row['cases']]==['cold','warm']
   for c in row['cases']:assert c['timings']['context_tokens']==count and c['timings']['prefill_tokens']==count and c['timings']['cached_prefix_tokens']==0
   rows.append(dict(context_tokens=count,mode=row['mode'],status='COMPLETE_PROCESS_TRIAL',n=1,binary_sha256=row['binary_sha256'],pre_host_free_percent=row['host_free_before'],post_gpu=row['post_gpu'],memory=row['memory'],budget=row['budget'],cases=[case(c) for c in row['cases']],routes=row['boundary_routes']))
 partial=load(root/'performance-resume-20261106-32768/0-mask63/http-records.json')['cases'];assert len(partial)==1 and partial[0]['label']=='cold'
 single=dict(context_tokens=32768,mode='mask63',status='COMPLETE_REQUEST_IN_INTERRUPTED_TRIAL',scope='SSE finish/DONE and allocation observer completed; parent console pipe failed before warm request or final post-process guard record',cases=[case(partial[0])])
 baseline={x['mode']:x for x in a['rows']};warm={m:next(c['timings']['prefill_ms'] for c in row['cases'] if c['label']=='warm') for m,row in baseline.items()}
 routes=[x for row in b['rows'] for x in row['boundary_routes']];routing={str(n):{backend:sorted({x['layer'] for x in routes if x['length']==n and x['backend']==backend}) for backend in ['GPU','CPU']} for n in [32768,32769,32770,32771]}
 for n in [32768,32769]:assert routing[str(n)]['GPU' if n==32768 else 'CPU']==list(range(3,40,4))
 result=dict(status='PARTIAL_PERFORMANCE_QUALIFICATION',release_manifest_sha256=a['release_manifest_sha256'],completed_trials=rows,interrupted_trial_requests=[single],warm_16k_mask63_overhead_percent=(warm['mask63']/warm['ordinary']-1)*100,warm_16k_mask63_vs_scalar_throughput=warm['scalar']/warm['mask63'],ordinary_32k_boundary_routes=routing,variability='NOT_MEASURED: n=1 per mode/context/temperature; cold and warm are distinct conditions',confidence='Exploratory process-wall timing, launch/post GPU gated; OS cache not purged, in-run contention not independently separable, expert-cache contents may diverge by arithmetic path',missing=['32K mask63 warm complete process trial','32K scalar cold/warm','Second and third repetitions','Hardware timestamp attention latency','HTTP per-expert cache hit counters'],completion_attempt=load(root/'resume-reconciliation-20261110.json'))
 if completion is not None:
  assert validation is not None
  from validate_work_a_missing import validate
  new=load(completion/'result.json');proof=load(validation);variants=load(root/'build-variants.json')
  assert proof['status']=='ACCEPTED_EXPLORATORY_N1' and proof['result_sha256']==hashlib.sha256((completion/'result.json').read_bytes()).hexdigest()
  assert proof['release_manifest_sha256']==result['release_manifest_sha256']
  validate(new,result['release_manifest_sha256'],{m:variants['variants'][n]['sha256'] for m,n in [('mask63','infer-work-a-performance'),('scalar','infer-work-a-control')]},b['input_sha256'],b['rendered_ids_sha256'])
  for row in new['rows']:
   rows.append(dict(context_tokens=32768,mode=row['mode'],status='COMPLETE_PROCESS_TRIAL',n=1,binary_sha256=row['binary_sha256'],pre_host_free_percent=row['host_free_before'],post_gpu=row['post_gpu'],memory=row['memory'],budget=row['budget'],cases=[case(c) for c in row['cases']],routes=row['boundary_routes']))
  full={r['mode']:r for r in rows if r['context_tokens']==32768};comparison={}
  for label in ['cold','warm']:
   times={m:next(c['timings']['prefill_ms'] for c in row['cases'] if c['label']==label) for m,row in full.items()}
   comparison[label]=dict(mask63_time_overhead_percent=(times['mask63']/times['ordinary']-1)*100,mask63_vs_scalar_throughput=times['scalar']/times['mask63'])
  result.update(status='PERFORMANCE_GATE_COMPLETE_EXPLORATORY_N1',comparison_32k=comparison,new_completion={k:new[k] for k in ['started','ended','source_head','runner_sha256','release_manifest_sha256','max_process_seconds']},completion_validation=proof,comparison_scope='Reused November6 ordinary control versus later missing-only cohort, frozen source/model/settings; cross-date host/cache conditions are not identical',missing=result['missing'][2:])
 elif validation is not None:raise ValueError('Validation requires its completion directory')
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=P);p.add_argument('--out',required=True,type=P);p.add_argument('--completion',type=P);p.add_argument('--validation',type=P);a=p.parse_args();d=build(a.root,a.completion,a.validation);a.out.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');print(d['status'],'completed process trials',len(d['completed_trials']))
if __name__=='__main__':main()
