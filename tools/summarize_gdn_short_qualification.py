#!/usr/bin/env python3
"""Read-only, fail-closed aggregation of the bounded GDN qualification artifacts."""
import argparse,json,pathlib,hashlib,math
P=pathlib.Path
def require(value,why):
 if not value:raise RuntimeError(why)
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();r=a.root
 reports=[json.loads((r/n/'result.json').read_text()) for n in ['full-model-matrix1','full-model-matrix2','chains-off-route1']]
 cases=[];common={};maxima=dict(state=0.,hidden=0.,logits=0.);endpoints=0
 for report in reports:
  for case in report['cases']:
   require(case['status']=='PASS' and case['persistent_exact'],'case state');width,n=case['width'],case['tokens'];folder=r/('chains-off-route1' if report.get('engine_args') else ('full-model-matrix1' if width==32 and n==33 else 'full-model-matrix2'))/f'n{width}-t{n}';native=json.loads((folder/'nrow-oracle.json').read_text());rows=native['rows'];endpoints+=len(rows)
   require(native['completed_position']==n and rows and rows[-1]['position']==n,'completed endpoint')
   for row in rows:
    require(row['pass'] and row['finite'] and row['greedy_equal'] and row['kv_lengths_and_mirrors'],'native flags')
    require(row['reference_digest']==row['candidate_digest'] and row['state_max_abs']==0,'exact active state')
    values=[row['state_max_abs'],row['hidden']['max_abs'],row['logits']['max_abs']];require(all(math.isfinite(x) and x>=0 for x in values),'finite errors');require(values[0]<1e-3 and values[1]<=1e-3 and values[2]<=1e-2,'limits')
    for k,v in zip(maxima,values):maxima[k]=max(maxima[k],v)
    if not report.get('engine_args'):
     pos=row['position'];require(pos not in common or common[pos]==row['reference_digest'],'common-prefix reference changed');common[pos]=row['reference_digest']
   cases.append(dict(width=width,tokens=n,engine_args=report.get('engine_args',[]),endpoints=len(rows),max_errors=case['max_errors'],persistent_exact=True,binary_sha256=case['binary_sha256'],native_artifact_sha256=case['raw_oracle_sha256']))
 require(len(cases)==8,'eight full-model cases required')
 routes=json.loads((r/'chains-off-route1/n128-t129/route-probe.json').read_text());ref=routes['reference'];cand=routes['candidate'];require(len(ref)==5120 and ref.keys()==cand.keys(),'routing coverage');margins=[];score=weight=0.;mid=post=0
 for key,x in ref.items():
  y=cand[key];require(x['experts']==y['experts'],'expert identity/order mismatch');score=max(score,max(abs(u-v) for u,v in zip(x['router_scores'],y['router_scores'])));weight=max(weight,max(abs(u-v) for u,v in zip(x['weights'],y['weights'])));sorted_scores=sorted(x['router_scores'],reverse=True);margins.append(sorted_scores[7]-sorted_scores[8]);mid+=x['mid_sha256']!=y['mid_sha256'];post+=x['post_sha256']!=y['post_sha256']
 disk=json.loads((r/'disk-suffix2/result.json').read_text());require(disk['status']=='PASS' and disk['matched_positions']==130,'disk result');saved=json.loads((r/'disk-suffix2/save/disk-save.json').read_text());loaded=json.loads((r/'disk-suffix2/load/disk-load.json').read_text());require(saved['compatibility']==loaded['compatibility'] and saved['prefix_signature']==loaded['prefix_signature'],'disk identity')
 for x,y in zip(saved['rows'],loaded['rows']):require(x['position']==y['position'] and x['digest']==y['digest'] and x['kv_lengths_match'] and y['kv_lengths_match'],'disk states')
 shared={}
 for row in saved['rows']:
  if row['position'] in common:require(row['digest']==common[row['position']],'disk versus independent oracle');shared[str(row['position'])]=True
 result=dict(status='PASS_BOUNDED',model_cases=cases,observed_endpoints=endpoints,max_errors=maxima,routing=dict(decisions=len(ref),expert_ids_order_exact=True,router_score_max_abs=score,weight_max_abs=weight,minimum_top8_top9_margin=min(margins),hidden_mid_hash_differences=mid,hidden_post_hash_differences=post),disk=dict(status='PASS',positions=130,checkpoint_bytes=disk['checkpoint_bytes'],checkpoint_sha256=disk['checkpoint_sha256'],compatibility=disk['compatibility'],prefix_signature=disk['prefix_signature'],independent_oracle_shared_positions=shared),source_baseline='21a073174fb1feb828f2d28762293d1803e66a9a',limitations=['Not long-context qualification','No full-model raw gate projection capture','No claim of unobservable per-token batch state','N8/N16 only component-level, not new serving modes','No actual decoded text in disk oracle'],preserved_failure='disk-suffix1: SIGABRT caused by an undersized driver basename and missing diagnostic path validation; fixed without serializer/math changes')
 a.out.write_text(json.dumps(result,indent=2)+'\n');print('PASS_BOUNDED',len(cases),'cases',endpoints,'endpoints',maxima)
if __name__=='__main__':main()
