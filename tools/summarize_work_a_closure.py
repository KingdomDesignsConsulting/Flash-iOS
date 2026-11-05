#!/usr/bin/env python3
"""Bounded sanitized Work A evidence; never launches inference or grants release."""
import argparse,datetime,json,pathlib,re
from run_session_state_mission import sha
from work_a_manifest import verify_native_gate
P=pathlib.Path

def read(path):
 try:return json.loads(path.read_text())
 except FileNotFoundError:return dict(status='NOT_RUN')
 except json.JSONDecodeError:return dict(status='INCOMPLETE_JSON')

def summarize(root):
 manifest=read(root/'release-manifest.json');md=sha(root/'release-manifest.json');out=dict(status='EVIDENCE_ONLY_REVIEW_REQUIRED',updated=datetime.datetime.now().astimezone().isoformat(),starting_head=manifest['head'],runtime_repair_commit=manifest['runtime_repair_commit'],release_manifest_sha256=md,candidate_binary_sha256=manifest['binary_sha256'],source_tree=manifest['tree'],runtime_source_sha256=manifest['source_sha256'],model_contract=manifest['model_contract'],execution=manifest['execution'],fixtures={k:{field:v[field] for field in ['sha256','bytes']} for k,v in manifest.get('fixtures',{}).items()},production_modified=False,raw_payloads_exported=False)
 out['identity_self_test']=read(root/'identity-proof.json')
 repro=read(root/'repro-evidence.json');out['build_reproducibility']={k:v for k,v in repro.items() if k in ['whole_file_exact','all_sections_exact','normalized_payload_exact','exclusions']}
 out['template_comparison']=read(root/'template-comparison.json')
 out['preflight']={k:v for k,v in read(root/'preflight257/result.json').items() if k in ['status','started','ended','input_tokens','completed_position','pre_gpu','max_errors','observed_native_rss_bytes','stop_reason','binary_sha256']}
 native=read(root/'repaired-32768/result.json');out['native_32768']={k:v for k,v in native.items() if k in ['status','started','ended','exit','release_manifest_sha256','binary_sha256','count','preflight','host_free_before','observed_endpoints','persistent_fingerprints_exact','max_errors']}
 if native.get('status')=='PASS':
  try:out['native_32768']['strict_verification']=verify_native_gate(root/'repaired-32768/result.json',md)
  except (AssertionError,KeyError,ValueError,OSError) as error:out['native_32768'].update(status='EVIDENCE_INVALID',validation_error_type=type(error).__name__)
 meta=read(root/'repaired-32768/native/result.json');out['native_32768']['resource']={k:v for k,v in meta.items() if k in ['observed_native_rss_bytes','peak_child_rss_bytes','rss_limit_gib','host_free_floor_percent','stop_reason','pre_gpu','exit']}
 oracle=read(root/'repaired-32768/native/nrow-oracle.json')
 if oracle.get('rows'):
  out['native_32768']['endpoints']=[dict(position=r['position'],state_max_abs=r['state_max_abs'],hidden_max_abs=r['hidden']['max_abs'],logits_max_abs=r['logits']['max_abs'],persistent_fingerprint_exact=bool(r.get('candidate_digest')) and r.get('candidate_digest')==r.get('reference_digest'),greedy_equal=r['greedy_equal'],finite=r['finite'],kv_lengths_and_mirrors=r['kv_lengths_and_mirrors'],passed=r['pass']) for r in oracle['rows']]
 memory=read(root/'repaired-32768/native/memory-observations.json')
 if memory.get('samples'):
  keys=['physical_footprint_bytes','physical_footprint_peak_bytes','resident_bytes','metal_current_allocated_bytes','two_oracle_snapshots_malloc_bytes'];out['native_32768']['memory_peak']={k:max(x[k] for x in memory['samples']) for k in keys}
 for name in ['literal','sustained','decode-timing','profile','cancellation']:
  raw=read(root/name/'result.json');out['named_profile' if name=='profile' else name]={k:v for k,v in raw.items() if k not in ['profile','command','requests','messages','events','traces','token_ids','generated_token_ids','sampled_token_ids','effective_token_ids']}
 out['performance']={}
 for count in [16384,32768]:
  raw=read(root/f'performance-{count}/result.json');item={k:v for k,v in raw.items() if k in ['status','started','ended','count','repeats','release_manifest_sha256','runner_sha256','input_sha256','rendered_ids_sha256','cache_scope','attention_latency_scope','summary','confidence','error_type','error']}
  rows=[]
  for row in raw.get('rows',[]):
   selected={k:v for k,v in row.items() if k in ['trial','mode','binary_sha256','post_gpu','host_free_before','budget','memory','cases','boundary_routes','expert_cache_hit_counters_available']};phases=row.get('nrow_host_phase_records',[]);totals={}
   for phase in phases:
    for key,value in phase.items():totals[key]=totals.get(key,0)+value
   selected['profile_phase_totals_two_requests']=totals;rows.append(selected)
  item['rows']=rows;item['completed_process_trials']=len(rows);out['performance'][str(count)]=item
 # Defensive recursive privacy filter for future nested additions.
 forbidden={'messages','events','traces','token_ids','sampled_token_ids','effective_token_ids','forwarded_token_ids','completed_token_ids','generated_token_ids','tensor_values','raw_sse','request_payload','response_payload','request','response','requests','abort','observed','command','profile','error','content','visible','rendered','prompt','reasoning_text','content_text'}
 def clean(value):
  if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in forbidden}
  if isinstance(value,list):return [clean(v) for v in value]
  return value
 return clean(out)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=P);p.add_argument('--out',required=True,type=P);a=p.parse_args();result=summarize(a.root);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print('SANITIZED_WORK_A',a.out)
if __name__=='__main__':main()
