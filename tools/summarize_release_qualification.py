#!/usr/bin/env python3
"""Sanitize private qualification evidence. Never exports tokens or tensor data."""
import argparse,json,math,pathlib
P=pathlib.Path

def read(p):return json.loads(p.read_text())
def oracle(p):
 meta=read(p/'result.json') if (p/'result.json').exists() else {}
 result={k:meta[k] for k in ['status','exit','input_tokens','completed_position','batches','binary_sha256','fixture_sha256','source_head','source_sha256','peak_child_rss_bytes','observed_native_rss_bytes','rss_limit_gib','stop_reason','pre_gpu'] if k in meta}
 if not (p/'nrow-oracle.json').exists():return dict(result,status=result.get('status','RUNNING' if (p/'engine.log').exists() else 'NOT_RUN'))
 n=read(p/'nrow-oracle.json');rows=n['rows']
 if not rows:
  assert result.get('status')!='PASS','Successful report without observed endpoints'
  return dict(result,observed_endpoints=0)
 maximum=lambda key:max(float(x[key]['max_abs']) for x in rows)
 errors=dict(state=max(float(x['state_max_abs']) for x in rows),hidden=maximum('hidden'),logits=maximum('logits'))
 assert all(math.isfinite(x) for x in errors.values())
 exact=all(x.get('reference_digest') and x['reference_digest']==x.get('candidate_digest') for x in rows)
 passes=all(x['pass'] and x['finite'] and x['greedy_equal'] and x['kv_lengths_and_mirrors'] and 0<=float(x['state_max_abs'])<1e-3 and 0<=float(x['hidden']['max_abs'])<=1e-3 and 0<=float(x['logits']['max_abs'])<=1e-2 for x in rows)
 result.update(observed_endpoints=len(rows),max_errors=errors,exact_recorded_persistent_fingerprints=exact,all_observed_greedy_finite_kv_checks=passes)
 if result.get('status')=='PASS':assert passes and exact and n['status']=='NUMERICAL_PASS' and n['completed_position']==meta['input_tokens']
 if (p/'memory-observations.json').exists():
  samples=read(p/'memory-observations.json')['samples'];last=samples[-1]
  keys=['physical_footprint_bytes','physical_footprint_peak_bytes','resident_bytes','metal_current_allocated_bytes','two_oracle_snapshots_malloc_bytes']
  result['memory']=dict(peak_observed={k:max(x[k] for x in samples) for k in keys},final={k:v for k,v in last.items() if k not in ['metal_buffers']})
  final=result['memory']['final'];raw_alias=final.get('cpu_kv_aliases_metal_reserved_bytes',0);gpu_kv=final.get('metal_categories_reserved_bytes',{}).get('attention_kv',0)
  final['cpu_kv_shared_view_span_bytes']=min(raw_alias,gpu_kv)
  if final.get('memory_schema',1)==1:
   final['cpu_kv_base_alias_reservation_bytes']=final.pop('cpu_kv_aliases_metal_reserved_bytes',0);final['alias_counter_note']='Schema 1 counted the CPU reservation after base-address alias detection. Actual shared view span is bounded by GPU view lengths; raw source data remains private and unchanged.'
 if not passes:
  bad=next(x for x in rows if not x['pass']);largest=max(bad['components'],key=lambda x:x['max_abs']);result['failure']=dict(position=bad['position'],component=largest['component'],layer=largest['layer'],max_abs=largest['max_abs'])
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();root=a.root
 out=dict(starting_engineering_head='eda0e73fd2eca1c8d48caebf9d4d124232eb0d0f',starting_documentation_head='64a5d51bb76c928e8d6ff0ee8535cee64286e597',mask=63,independent={},long={},short={},performance='No new performance claim; mandatory gates decide eligibility',production_modified=False,raw_tokens_exported=False)
 for name in ['technical','programming','conversation','reasoning','tools','structured-stress']:out['independent'][name]=oracle(root/'independent'/name)
 for count in [16384,32768]:
  path=root/'long'/str(count)
  if count==32768 and not path.exists():path=root/'long32k'/str(count)
  out['long'][str(count)]=oracle(path)
 for name,path in [('stream_faults','short-armed/stream-faults'),('named_profile','short-armed/profile'),('cancellation','short-armed/cancellation'),('capacity','protocol-modes/capacity'),('protocol','protocol-modes/protocol'),('cpu_linear','protocol-modes/cpu-linear'),('chains_off','protocol-modes/chains-off'),('legacy_kv','protocol-modes/legacy-kv'),('disabled','protocol-modes/disabled-mask'),('tool_interruption','final-safety/tool-interruption-retry'),('cache_allocation_faults','final-safety/cache-faults'),('long_http','final-safety/long-http'),('disk_restore','final-safety/disk'),('live_adapter','final-safety/live-adapter')]:
  file=root/path/'result.json'
  if not file.exists():out['short'][name]={'status':'NOT_RUN'};continue
  r=read(file);allowed=['status','cases','requests','behavioral_identifier_retained','checkpoint_bytes','state_exact','recovery_exact','baseline_matches_scalar_control','post_rejection_continuation_matches_scalar','injection_position','inside_actual_incomplete_tool_envelope','partial_tool_delta_emitted','scalar_recovery_and_followup_exact','prefix','end_position','positions_compared','save_ms','restore_ms','wrong_prefix_and_mode_rejected','different_numerics_rejected','rejected_mask','rejection_exit','load_binary_sha256','resident_turns','candidate_observation_points','exact_shared_observations','reference_exit','reference_stop_reason','real_flash_inference','real_sdk_chat','mock_prediction_controller','GUI_tested','stateless_full_history','native_prompts']
  item={k:r[k] for k in allowed if k in r}
  if name=='cancellation':item['cases']=[{k:x[k] for k in ['phase','invalidated','stale_status','health_ms','cancellation_ms','recovery_end'] if k in x} for x in r['cases']]
  if name in ['cpu_linear','chains_off','legacy_kv','disabled']:item.update({k:r[k] for k in ['source_head','binary_sha256','nrow','padding_words','status','requests'] if k in r})
  out['short'][name]=item
 # Paths are not needed in public results; commands and raw payloads stay private.
 def sanitize(x):
  if isinstance(x,dict):return {k:sanitize(v) for k,v in x.items() if k not in ['command','profile','model','source','fixture','checkpoint','out','abort','observed']}
  if isinstance(x,list):return [sanitize(v) for v in x]
  return x
 out=sanitize(out);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print('SANITIZED_RESULTS',a.out)
if __name__=='__main__':main()
