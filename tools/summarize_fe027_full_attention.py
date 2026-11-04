#!/usr/bin/env python3
"""Sanitize bounded tensor comparisons; fail closed on missing replay coverage.
Raw float files and token histories are never copied into this summary.
"""
import argparse,json,math,pathlib
POSITIONS=[0,1,7,30,31,32,63,127]
VALIDATIONS=['scalar_q_projection_replay_vs_live','scalar_k_projection_replay_vs_live','scalar_v_projection_replay_vs_live','reference_preparation_replay_vs_live','reference_attention_replay_vs_live','reference_gate_replay_vs_live','oprojection_replay_vs_live','residual_cpu_add_vs_live']
def summarize(tensors,replays,state):
    rows=replays['rows']
    if sorted(r['position'] for r in rows)!=POSITIONS:raise ValueError('missing or duplicate replay rows')
    reasons=[]
    if not state.get('active_state_unchanged'):reasons.append('private replay changed active state or check missing')
    for r in rows:
        for key in VALIDATIONS+(['cpu_q_normalization_replay_vs_live','cpu_k_normalization_replay_vs_live'] if r['position']<31 else []):
            m=r.get(key)
            if m is None or not m.get('exact') or m.get('nonfinite',0):reasons.append(f"{r['position']}:{key} failed or absent")
    actual={};missing={}
    for r in tensors['rows']:
        if r['stage'].startswith('kv_'):continue
        shape=r['dimensions']
        if math.prod(shape)!=r['floats']:raise ValueError('tensor dimension mismatch')
        if not(r['reference_observed'] and r['candidate_observed']):missing.setdefault(r['stage'],[]).append(r['position']);continue
        if r['nonfinite'] or not math.isfinite(r['max_abs']):raise ValueError('nonfinite actual comparison')
        stages=actual.setdefault(r['stage'],[])
        stages.append({k:r[k] for k in ['layer','position','row','dimensions','floats','exact','max_abs','rms','different','bit_different','first_different','reference_path','candidate_path']})
    if any(sorted(r['position'] for r in actual.get(key,[]))!=POSITIONS for key in ['layer_input','input_norm','qproj','kproj','vproj','q_rope','k_rope','attention_gated','oprojection','residual']):raise ValueError('missing actual stage coverage')
    first={key:next((r for r in sorted(vals,key=lambda x:x['position']) if not r['exact']),None) for key,vals in actual.items()}
    maxima={}
    for row in rows:
        for k,v in row.items():
            if isinstance(v,dict) and 'max_abs' in v:
                if not math.isfinite(v['max_abs']) or v.get('nonfinite',0):raise ValueError('nonfinite replay')
                maxima[k]=max(maxima.get(k,0),v['max_abs'])
    return dict(causal_validation_pass=not reasons,validation_failures=reasons,positions=POSITIONS,geometry={k:replays[k] for k in ['heads','head_dim','rotary_dim']},actual_stages=actual,first_observed_differences=first,unobservable_comparisons=missing,identical_input_maxima=maxima,scope='Only sampled actual layer tensors. Fused normalized intermediates are unobservable; nonrotary-slice RMS comparison is a separate identical-input probe. No intermediate full-model states inferred.')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();load=lambda name:json.loads((a.directory/name).read_text())
    result=summarize(load('full-attention-tensors.json'),load('full-attention-identical-inputs.json'),load('full-attention-replay-state.json'));a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['causal_validation_pass','validation_failures','geometry','identical_input_maxima']},indent=2));return 0 if result['causal_validation_pass'] else 3
if __name__=='__main__':raise SystemExit(main())
