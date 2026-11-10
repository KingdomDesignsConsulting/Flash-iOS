#!/usr/bin/env python3
"""Sanitize completed Work A performance evidence without upgrading partial trials."""
import argparse,json,pathlib
P=pathlib.Path

def load(p):return json.loads(p.read_text())
def case(c):
 r=c.get('result',c)
 return dict(label=c['label'],timings=r['timings'],wire_ttft_ms=r['wire_ttft_ms'],wall_ms=r['wall_ms'],allocation=c['allocation'],host_phases=c.get('nrow_host_phases',{}))
def build(root):
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
 return dict(status='PARTIAL_PERFORMANCE_QUALIFICATION',release_manifest_sha256=a['release_manifest_sha256'],completed_trials=rows,interrupted_trial_requests=[single],warm_16k_mask63_overhead_percent=(warm['mask63']/warm['ordinary']-1)*100,warm_16k_mask63_vs_scalar_throughput=warm['scalar']/warm['mask63'],ordinary_32k_boundary_routes=routing,variability='NOT_MEASURED: n=1 per mode/context/temperature; cold and warm are distinct conditions',confidence='Exploratory process-wall timing, launch/post GPU gated; OS cache not purged, in-run contention not independently separable, expert-cache contents may diverge by arithmetic path',missing=['32K mask63 warm complete process trial','32K scalar cold/warm','Second and third repetitions','Hardware timestamp attention latency','HTTP per-expert cache hit counters'],completion_attempt=load(root/'resume-reconciliation-20261110.json'))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();d=build(a.root);a.out.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');print(d['status'],'completed process trials',len(d['completed_trials']))
if __name__=='__main__':main()
