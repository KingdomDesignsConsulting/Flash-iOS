#!/usr/bin/env python3
"""Stage-2 Flash-iOS effective token-history diagnostic.

Run the existing four-path experiment first against experimental :11243 with
FLASH_SESSION_TOKEN_TRACE_DIR set. This script reads its private result/traces.
It does NOT assert KV/GDN/convolution state equality or contact a server.
"""
import argparse
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def first_mismatch(a, b):
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return {
        "common_prefix": common,
        "first_mismatch_index": common if common < max(len(a), len(b)) else None,
        "left_id": a[common] if common < len(a) else None,
        "right_id": b[common] if common < len(b) else None,
        "left_count": len(a),
        "right_count": len(b),
        "left_extra": a[common:common + 12],
        "right_extra": b[common:common + 12],
        "identical": a == b,
    }


def record(result, name):
    item = result[name]
    prompt = load(item["trace"]["file"])
    genmeta = item.get("generated")
    if not genmeta:
        raise ValueError(f"{name}: missing generated trace; rebuild instrumented server")
    generated = load(genmeta["file"])
    needed = ("forwarded_token_ids", "forwarded_positions",
              "completed_token_ids", "completed_positions")
    for key in needed:
        if key not in generated:
            raise ValueError(f"{name}: missing {key}; use updated tracing binary")
    forwarded, fpos = generated["forwarded_token_ids"], generated["forwarded_positions"]
    completed, cpos = generated["completed_token_ids"], generated["completed_positions"]
    if len(forwarded) != len(fpos) or len(completed) != len(cpos):
        raise ValueError(f"{name}: ID/position lengths disagree")
    if len(completed) > len(forwarded):
        raise ValueError(f"{name}: more completed than forwarded")
    if forwarded[:len(completed)] != completed or fpos[:len(completed)] != cpos:
        raise ValueError(f"{name}: completed forwards are not a prefix of attempts")
    if any(right != left + 1 for left, right in zip(cpos, cpos[1:])):
        raise ValueError(f"{name}: non-contiguous completed positions")
    return prompt, generated


def effective_prompt(result, name, generated):
    state = load(result[name]["state_trace"])
    if not state["history_complete"]:
        raise ValueError(f"{name}: incomplete effective history")
    end = (generated["forwarded_positions"][0] if generated["forwarded_positions"]
           else state["end_position"])
    ids = state["effective_token_ids"]
    if end > len(ids):
        raise ValueError(f"{name}: prompt extends past completed history")
    return ids[:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage1", required=True, type=Path,
                   help="JSON report from experiment_session_token_exact.py")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = load(args.stage1)
    initial, a = record(result, "resident_create")
    delta, b = record(result, "resident_continuation")
    canonical, c = record(result, "canonical_full")
    replay, d = record(result, "explicit_replay_create")
    actual=load(result["resident_create"]["state_trace"])
    if not actual["history_complete"]:
        raise ValueError("Incomplete effective history; do not omit cached prefix tokens")
    timeline=actual["effective_token_ids"]+delta["token_ids"]
    canonical_ids=effective_prompt(result,"canonical_full",c)
    replay_ids=effective_prompt(result,"explicit_replay_create",d)
    # Request-boundary position checks are diagnostic, not hidden assumptions:
    # the resident path may deliberately reuse saved state or prompt prefixes.
    continuity = {
        "initial_completed_last_position": (a["completed_positions"][-1]
                                            if a["completed_positions"] else None),
        "initial_end_pos": a["end_pos"],
        "resident_delta_prompt_tokens": len(delta["token_ids"]),
        "resident_delta_generated_first_position": (b["forwarded_positions"][0]
                                                       if b["forwarded_positions"] else None),
        "initial_session_reusable": a["session_reusable"],
        "continuation_session_reusable": b["session_reusable"],
    }
    checks = {
        "all_completed_are_prefix_of_forwarded": True,
        "canonical_prompt_equals_replay": canonical_ids == replay_ids,
        "initial_request_succeeded": not a["request_state_failed"],
        "continuation_request_succeeded": not b["request_state_failed"],
        "initial_completed_count": len(a["completed_token_ids"]),
        "initial_forward_attempt_count": len(a["forwarded_token_ids"]),
        "initial_sample_attempt_count": len(a["generated_token_ids"]),
        "continuation_completed_count": len(b["completed_token_ids"]),
        "initial_sample_vs_effective_mismatch": first_mismatch(
            a["generated_token_ids"], a["completed_token_ids"]),
    }
    report = {
        "source_report": str(args.stage1),
        "checks": checks,
        "continuity": continuity,
        "resident_committed_candidate_vs_canonical_prompt": first_mismatch(
            timeline, canonical_ids),
        "canonical_vs_explicit_replay": first_mismatch(
            canonical_ids, replay_ids),
        "interpretation": (
            "Resident candidate is the original request prompt + successful "
            "generated forwards + next request delta. This checks token-level "
            "history, but does not guarantee cached-prefix or request-boundary "
            "identity; differing chat-template wrappers are expected to be "
            "reported, not normalized away."
        ),
        "state_equivalence": "NOT_ESTABLISHED",
        "gpu_state_fingerprints": "See separate matched-token mission results; not inferred here",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "canonical_replay_identical": checks["canonical_prompt_equals_replay"],
        "resident_vs_canonical": report["resident_committed_candidate_vs_canonical_prompt"],
        "state_equivalence": report["state_equivalence"],
        "report": str(args.out),
    }, indent=2))
    return 0 if all((checks["canonical_prompt_equals_replay"],
                     checks["initial_request_succeeded"],
                     checks["continuation_request_succeeded"])) else 2


if __name__ == "__main__":
    raise SystemExit(main())
