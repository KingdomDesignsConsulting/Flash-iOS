#!/usr/bin/env python3
"""Summarize private matched-input routing traces without exporting raw scores.
Ordering is labelled explicitly: batch execution is layer-major, scalar is token-major.
Neither ordering establishes unobserved intermediate full-model state equality.
"""
import argparse,json,pathlib

def analyze(trace):
    ref,cand=trace['reference'],trace['candidate']
    expected={f'{layer}:{pos}' for layer in range(trace['layers']) for pos in range(trace['start'],trace['end'])}
    if set(ref)!=expected or set(cand)!=expected:
        raise ValueError('incomplete or extra routing observations')
    changes=[];ordered=0;max_score=0.;same_post=0
    for key,a in ref.items():
        b=cand[key]
        if a['layer']!=b['layer'] or a['position']!=b['position']:
            raise ValueError('mismatched routing observation identity')
        x,y=a['router_scores'],b['router_scores']
        if len(x)!=len(y) or not x:raise ValueError('router score shape mismatch')
        score=max(abs(u-v) for u,v in zip(x,y));max_score=max(max_score,score)
        ordered+=a['experts']!=b['experts']
        same_post+=bool(a.get('post_sha256')) and a.get('post_sha256')==b.get('post_sha256')
        if set(a['experts'])==set(b['experts']):continue
        selected=set(a['experts']);other=set(range(len(x)))-selected
        changes.append(dict(layer=a['layer'],position=a['position'],score_max_abs=score,
            reference_cutoff_margin=min(x[i] for i in selected)-max(x[i] for i in other),
            candidate_cutoff_margin=min(y[i] for i in set(b['experts']))-max(y[i] for i in set(range(len(y)))-set(b['experts']))))
    return dict(observations=len(expected),ordered_selection_changes=ordered,expert_set_changes=len(changes),
        max_router_score_difference=max_score,exact_post_inputs=same_post,
        first_by_layer_then_position=min(changes,key=lambda x:(x['layer'],x['position'])) if changes else None,
        first_by_position_then_layer=min(changes,key=lambda x:(x['position'],x['layer'])) if changes else None)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path);a=p.parse_args()
    result=analyze(json.loads(a.trace.read_text()));text=json.dumps(result,indent=2)+'\n'
    if a.out:a.out.write_text(text)
    else:print(text,end='')
if __name__=='__main__':main()
