#!/usr/bin/env python3
"""Fail-closed, sanitized combine diagnostics. Never copies raw operands/IDs."""
import argparse,hashlib,json,math,pathlib
LAYERS={0,2,3,23}
POSITIONS={0,1,7,31,63,127}
def summarize(report,state):
    rows=report['rows'];expected={(phase,l,p) for phase in range(2) for l in LAYERS for p in POSITIONS}
    actual=[(r['phase'],r['layer'],r['position']) for r in rows]
    if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('missing or duplicate actual observations')
    if report['dimensions']!=2048:raise ValueError('unexpected model geometry')
    failures=[];result=[];configs=set()
    if not state.get('active_state_unchanged'):failures.append('private replay mutated state or check missing')
    for r in rows:
        label=f"{r['phase']}:{r['layer']}:{r['position']}"
        if not r.get('expected_live_replay_exact'):failures.append(label+': replay does not reproduce live output')
        if not r.get('trace_vs_original_gpu',{}).get('exact'):failures.append(label+': stage trace does not reproduce original GPU kernel')
        stages=r['stages']
        names=[('weighted_product',k) for k in range(8)]+[('expert_accumulation',k) for k in range(8)]+[(s,-1) for s in ['sigmoid','shared_contribution','residual_plus_experts','final']]
        if [(s['stage'],s['slot']) for s in stages]!=names:raise ValueError('missing or reordered stages')
        metrics=[r['gpu_replay_vs_live'],r['cpu_replay_vs_live'],r['trace_vs_original_gpu']]+[s['difference'] for s in stages]
        metrics+=r.get('operand_differences',[])+[r['weights'],r['shared_score'],r['actual_output_difference']]
        for m in metrics:
            if m.get('nonfinite',0) or not math.isfinite(m['max_abs']) or not math.isfinite(m['rms']):raise ValueError('nonfinite metric')
        if len(r['operand_differences'])!=10:raise ValueError('missing operand coverage')
        identity=hashlib.sha256(json.dumps(r['ids'],separators=(',',':')).encode()).hexdigest();configs.add(identity)
        same=bool(r['same_expert_ids'] and r['weights']['exact'] and r['shared_score']['exact'] and all(m['exact'] for m in r['operand_differences']))
        first=next(({'stage':s['stage'],'slot':s['slot'],'difference':s['difference']} for s in stages if not s['difference']['exact']),None)
        result.append({k:r[k] for k in ['phase','layer','position','path','gpu_replay_vs_live','cpu_replay_vs_live','trace_vs_original_gpu','operand_differences','weights','shared_score','same_expert_ids','actual_output_difference']}|dict(identical_actual_operands=same,configuration_sha256=identity,first_difference=first,stages=stages))
    if len(configs)<2:failures.append('only one expert configuration observed')
    return dict(causal_validation_pass=not failures,validation_failures=failures,rows=result,distinct_expert_configurations=len(configs),scope='Sampled actual operands/live outputs; original-GPU and CPU replays; trace final authenticated before interpreting diagnostic stages. Rounded products are not separately materialized original FMA intermediates.')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);a=p.parse_args()
    x=summarize(json.loads((a.directory/'combine-operators.json').read_text()),json.loads((a.directory/'combine-replay-state.json').read_text()))
    a.out.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:x[k] for k in ['causal_validation_pass','validation_failures','distinct_expert_configurations']}));return 0 if x['causal_validation_pass'] else 3
if __name__=='__main__':raise SystemExit(main())
