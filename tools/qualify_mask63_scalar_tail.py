#!/usr/bin/env python3
"""Finish only the unstarted scalar arm after an owned GPU-drain gate hold."""
import argparse,hashlib,json,pathlib,time
from qualify_mask63_missing import Arm,MODERATE,body,require,sha,stamp,R

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--reference-report',type=pathlib.Path,required=True);p.add_argument('--prior-report',type=pathlib.Path,required=True);p.add_argument('--operator-exclusive-model',action='store_true');p.add_argument('--resource-retry-authorized',action='store_true');a=p.parse_args();require(a.operator_exclusive_model,'exclusive model window required')
 a.out.mkdir(parents=True,exist_ok=False);m=json.loads((a.out.parent/'candidate-manifest.json').read_text());ref=json.loads(a.reference_report.read_text());prior=json.loads(a.prior_report.read_text())
 for d in [ref,prior]:require(d['source_sha']==m['candidate_source_sha'] and d['binary_sha256']==m['binary_sha256'],'retained source/binary mismatch')
 resource_stop=prior.get('supervisor',{}).get('stop_reason') in ['host_reserve','process_rss','telemetry_unavailable']
 if resource_stop:
  require(a.resource_retry_authorized,'new explicit resource-window confirmation required after actual stop')
  require(prior['reference_sha256']==sha(a.reference_report),'retained N128 reference changed')
 else:
  require(prior.get('error','').startswith('GPU admission'),'not an unstarted GPU-gated scalar arm')
  require(len(prior['arms'])==1 and prior['arms'][0].get('detail')=='CONTROLLED_EXTERNAL_TELEMETRY_LOSS','no unacknowledged actual resource failure')
  require(all(c['status']=='PASS' for c in prior['cases']) and len(prior['cases'])==4,'earlier missing cases not complete')
 require(sha(R/'metal_infer/infer-mask63-supervised-20261117')==m['binary_sha256'],'binary changed')
 for name,want in m['source_sha256'].items():require(sha(R/name)==want,'runtime source changed '+name)
 baseline=next(c['response'] for c in ref['cases'] if c['case']=='bounded_N128_prefill')
 report={'status':'INCOMPLETE','started':stamp(),'source_sha':m['candidate_source_sha'],'binary_sha256':m['binary_sha256'],'reference_sha256':sha(a.reference_report),'prior_sha256':sha(a.prior_report),'production_access':False,'cases':[]}
 try:
  with Arm(a.out/'scalar',scalar=True) as control:
   code,response=control.request(body(MODERATE,'scalar-final-tail'))
   require(code==200,'scalar request failed')
   def norm(d):return (d['choices'][0]['message'],d['choices'][0]['finish_reason'],d['usage'])
   require(norm(response)==norm(baseline),'scalar/N128 visible output or token counts differ')
   require(response['usage']['prompt_tokens']==276,'effective input count differs')
   require('nrow_chunks=0' in control.log(),'scalar prefill route absent')
   report['cases'].append({'case':'scalar_N128_same_input_visible_agreement','status':'PASS','response':response,'scope':'Visible content, finish and usage match; no new hidden/logit/KV tensor assertion'})
  report['supervisor']=control.result;report['status']='PASS'
 except Exception as e:
  report['status']='FAIL';report['error']=str(e)
  if 'control' in locals():report['supervisor']=control.result
  elif (a.out/'scalar/result.json').exists():report['supervisor']=json.loads((a.out/'scalar/result.json').read_text())
  if report.get('supervisor',{}).get('stop_reason') in ['host_reserve','process_rss','telemetry_unavailable'] or report.get('supervisor',{}).get('status')=='BLOCKED':report['status']='BLOCKED_RESOURCE'
 finally:
  report['ended']=stamp();(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('SCALAR_TAIL',report['status'],report.get('error'),flush=True)
 return 0 if report['status']=='PASS' else 3
if __name__=='__main__':raise SystemExit(main())
