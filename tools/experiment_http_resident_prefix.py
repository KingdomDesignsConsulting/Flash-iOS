#!/usr/bin/env python3
"""Isolated HTTP resident-session vs full-history experiment for Flash-iOS.

Runs on the target HTTP server; does not edit state files. A resident session
may replace an existing server session: use a dedicated test port/server.
"""
import argparse
import json
import time
import uuid
import urllib.error
import urllib.request

def request(base, messages, session=None, max_tokens=80, create=False):
    payload = {
        "model": "qwen3.5", "messages": messages, "stream": False,
        "temperature": 0, "reasoning_effort": "off",
        "max_tokens": max_tokens,
    }
    if session is not None:
        payload["session_id"] = session
    if create:
        payload["flash_session_create"] = True
    started = time.monotonic()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            result = json.loads(response.read())
            status = response.status
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read(1024)!r}") from exc
    elapsed = time.monotonic() - started
    if status != 200 or result.get("error") or result.get("session_invalidated"):
        raise RuntimeError(f"Non-successful response: {str(result)[:1200]}")
    choice = result.get("choices", [{}])[0]
    if choice.get("finish_reason") not in ("stop", "length"):
        raise RuntimeError(f"Unexpected finish_reason: {choice}")
    text = choice.get("message", {}).get("content", "")
    return {"elapsed_s": round(elapsed, 3), "content": text,
            "usage": result.get("usage"), "flash_timings": result.get("flash_timings"),
            "finish_reason": choice.get("finish_reason")}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:11241/v1")
    ap.add_argument("--context-file", help="Optional UTF-8 text to add to initial user prompt")
    ap.add_argument("--max-tokens", type=int, default=80)
    args = ap.parse_args()
    source = open(args.context_file, encoding="utf-8").read() if args.context_file else (
        "The equipment serial identifier is COBALT-731. "
        "The research specimen was stored in Bay 14. "
        "Only these two facts are in scope.")
    first = {"role": "user", "content": source + "\nAcknowledge in one short sentence."}
    follow = {"role": "user", "content":
              "What is the equipment serial identifier and where was the specimen stored? "
              "Answer in one sentence."}
    session = "prefix-probe-" + uuid.uuid4().hex[:20]
    # Sequence is intentional: the full-history control runs LAST so it cannot
    # evict the resident checkpoint before the continuation is tested.
    initial = request(args.base, [first], session=session, max_tokens=args.max_tokens, create=True)
    assistant = {"role": "assistant", "content": initial["content"]}
    continued = request(args.base, [follow], session=session, max_tokens=args.max_tokens)
    control = request(args.base, [first, assistant, follow], max_tokens=args.max_tokens)
    u = continued.get("flash_timings") or {}
    cu = control.get("flash_timings") or {}
    report = {
        "session_id": session,
        "initial": initial, "continuation": continued, "full_history_control": control,
        "continuation_text_matches_full_history": continued["content"] == control["content"],
        "continuation_prefill_tokens": u.get("prefill_tokens"),
        "control_prefill_tokens": cu.get("prefill_tokens"),
        "saved_prefill_tokens": (
            cu["prefill_tokens"] - u["prefill_tokens"]
            if isinstance(cu.get("prefill_tokens"), (int,float))
            and isinstance(u.get("prefill_tokens"), (int,float)) else None),
        "limitations": [
            "The current server may silently accept an absent session as a new session.",
            "This does not qualify restart, eviction, interruption, or another concurrent chat.",
            "The session continuation and full-history templates must be checked for exact parity.",
            "Server may persist an active in-memory session until another request replaces it."],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["continuation_text_matches_full_history"]:
        print("FAIL: continuation text differs from control; investigate rendering/state.", flush=True)
        return 2
    if report["saved_prefill_tokens"] is not None and report["saved_prefill_tokens"] <= 0:
        print("FAIL: no prefill saved.", flush=True)
        return 3
    print("PROVISIONAL PASS: matched answer; compare prefill and state logs before qualification.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
