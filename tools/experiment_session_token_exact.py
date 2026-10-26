#!/usr/bin/env python3
"""Token-exact resident versus canonical full-history diagnostic.

Requires experimental server launched with FLASH_SESSION_TOKEN_TRACE_DIR pointing
at an EMPTY existing directory. Reads exact prompt token IDs emitted by the
instrumented request path; does not claim KV/GDN/convolution state equality.
Never sends requests to production port 11241. Never launches a model.
"""
import argparse
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request
import uuid


def make_call(base, messages, sid=None, create=False):
    payload = {
        "model": "qwen3.5", "messages": messages, "stream": False,
        "temperature": 0, "reasoning_effort": "off", "max_tokens": 48,
    }
    if sid:
        payload["session_id"] = sid
    if create:
        payload["flash_session_create"] = True
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                                     data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    if "error" in result or not result.get("choices"):
        raise RuntimeError("Unexpected server response: " + str(result)[:500])
    return {
        "text": result["choices"][0]["message"].get("content", ""),
        "timings": result.get("flash_timings", {}),
        "usage": result.get("usage", {}),
        "id": result.get("id"),
    }


def collect(folder, previous, expected_id):
    for _ in range(50):
        found = sorted(set(folder.glob("chatcmpl-*.json")) - previous,
                       key=lambda path: path.stat().st_mtime_ns)
        for path in found:
            try:
                item = json.loads(path.read_text())
            except (ValueError, OSError):
                continue
            if item.get("request_id") == expected_id:
                ids = item["token_ids"]
                if item["prompt_tokens"] != len(ids):
                    raise ValueError("Token-trace length mismatch")
                return path, item
        time.sleep(.1)
    raise RuntimeError(f"Token trace missing for {expected_id}; was server started with FLASH_SESSION_TOKEN_TRACE_DIR?")


def digest(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def describe(trace, path):
    ids = trace["token_ids"]
    return {
        "file": str(path),
        "mode": trace["session_mode"],
        "prompt_tokens": len(ids),
        "sha256_token_ids": digest(ids),
        "thinking_enabled": trace["thinking_enabled"],
        "session_ended_with_eos": trace["session_ended_with_eos"],
    }


def compare(first, delta, canonical):
    initial = first["token_ids"]
    suffix = delta["token_ids"]
    full = canonical["token_ids"]
    # The initial generation adds output tokens and exact EOS/boundary handling.
    # These are NOT reconstructed from the first input tokens alone.
    lcp = 0
    for left, right in zip(suffix, full):
        if left != right:
            break
        lcp += 1
    # Look for the entire delta sequence at the canonical end; this is only
    # a suffix test, not proof that the preceding generated states are equal.
    suffix_match = len(full) >= len(suffix) and full[-len(suffix):] == suffix
    return {
        "create_token_count": len(initial),
        "resident_delta_token_count": len(suffix),
        "canonical_full_token_count": len(full),
        "resident_delta_matches_canonical_suffix": suffix_match,
        "delta_canonical_prefix_equal_tokens": lcp,
        "first_delta_token_ids": suffix[:12],
        "last_delta_token_ids": suffix[-12:],
        "canonical_last_token_ids": full[-12:],
        "limitation": "No generated-token trace or KV/GDN/convolution snapshot: full resident effective sequence and internal-state parity are not established.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:11243/v1")
    parser.add_argument("--trace-dir", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    opts = parser.parse_args()
    from urllib.parse import urlparse
    url = urlparse(opts.base)
    if (url.hostname not in ("127.0.0.1", "localhost")
            or url.port != 11243 or url.scheme != "http"):
        parser.error("This test is restricted to the isolated loopback server :11243")
    folder = opts.trace_dir.resolve()
    if not folder.is_dir():
        parser.error("trace directory must already exist")
    opts.out.parent.mkdir(parents=True, exist_ok=True)
    sentinel = "TOKEN-" + uuid.uuid4().hex[:12].upper()
    sid = "token-exact-" + uuid.uuid4().hex
    first_turn = {"role": "user", "content": f"Remember identifier {sentinel}. Reply briefly."}
    follow = {"role": "user", "content": "What identifier did I give you? Reply with identifier only."}
    records = {}
    def invoke(label, messages, session=None, create=False):
        before = set(folder.glob("chatcmpl-*.json"))
        reply = make_call(opts.base, messages, session, create)
        path, trace = collect(folder, before, reply["id"])
        records[label] = {"response": reply, "trace": describe(trace, path)}
        return trace, reply

    t1, r1 = invoke("resident_create", [first_turn], sid, True)
    t2, r2 = invoke("resident_continuation", [follow], sid)
    t3, r3 = invoke("canonical_full", [
        first_turn, {"role": "assistant", "content": r1["text"]}, follow
    ])
    # Replay under a distinct session, rebuilding from the canonical transcript.
    t4, r4 = invoke("explicit_replay_create", [
        first_turn, {"role": "assistant", "content": r1["text"]}, follow
    ], "replay-" + uuid.uuid4().hex, True)
    cmp = compare(t1, t2, t3)
    records["comparison"] = cmp
    records["checks"] = {
        "resident_retains_identifier": sentinel in r2["text"],
        "canonical_recalls_identifier": sentinel in r3["text"],
        "replay_recalls_identifier": sentinel in r4["text"],
        "canonical_and_replay_token_ids_identical": t3["token_ids"] == t4["token_ids"],
        "canonical_and_replay_answers_identical": r3["text"] == r4["text"],
    }
    records["functional_passed"] = all(records["checks"].values())
    records["state_equivalence"] = "NOT_ESTABLISHED"
    records["sentinel"] = sentinel
    opts.out.write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps({"checks": records["checks"], "functional_passed":
                      records["functional_passed"], "suffix_match":
                      cmp["resident_delta_matches_canonical_suffix"],
                      "state_equivalence": "NOT_ESTABLISHED",
                      "report": str(opts.out)}, indent=2))
    return 0 if records["functional_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
