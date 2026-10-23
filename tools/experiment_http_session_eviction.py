#!/usr/bin/env python3
"""Session-loss fault probe. Run ONLY on a dedicated Flash-iOS serving port.

Demonstrates whether a reused session_id after eviction can silently lose
prior context. This is an expected-vulnerability test, not an enablement switch.
"""
import argparse, json, time, uuid, urllib.request, urllib.error
def send(base, messages, sid=None, create=False):
    data={"model":"qwen3.5","messages":messages,"stream":False,
          "max_tokens":60,"temperature":0,"reasoning_effort":"off"}
    if sid: data["session_id"]=sid
    if create: data["flash_session_create"]=True
    t=time.monotonic()
    req=urllib.request.Request(base.rstrip("/")+"/chat/completions",
             json.dumps(data).encode(),{"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=300) as r:
            result=json.load(r); status=r.status
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="replace")
        try: result=json.loads(body)
        except ValueError: result={"body":body[:500]}
        status=e.code
    return {"status":status,"elapsed_s":round(time.monotonic()-t,3),
            "content":result.get("choices",[{}])[0].get("message",{}).get("content",""),
            "error":result.get("error"),"session_invalidated":result.get("session_invalidated"),
            "resend_full_history":result.get("resend_full_history"),
            "flash_timings":result.get("flash_timings",{})}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base",default="http://127.0.0.1:11241/v1")
    p.add_argument("--out",default=None)
    args=p.parse_args()
    sentinel="AXIOM-"+uuid.uuid4().hex[:12].upper()
    a="fault-probe-a-"+uuid.uuid4().hex[:12]
    b="fault-probe-b-"+uuid.uuid4().hex[:12]
    initial={"role":"user","content":"Remember this secret experimental code exactly: "+sentinel+". Acknowledge briefly."}
    follow={"role":"user","content":"What is the secret experimental code I gave earlier? If no earlier code is in context, say UNKNOWN."}
    first=send(args.base,[initial],a,create=True)
    second=send(args.base,[{"role":"user","content":"Say READY."}],b,create=True) # replaces active session
    stale=send(args.base,[follow],a) # MUST fail with replay signal
    full=send(args.base,[initial,{"role":"assistant","content":first["content"]},follow])
    lost=(sentinel not in stale["content"])
    signaled=(stale["status"]!=200 or stale["session_invalidated"] is True
              or stale["resend_full_history"] is True or stale["error"] is not None)
    result={"test":"resident session lost after replacement","initial":first,
            "replacement":second,"stale_continuation":stale,"full_history_control":full,
            "reference_code_present_in_full_history":sentinel in full["content"],
            "stale_session_explicitly_rejected":signaled,
            "stale_session_lost_context":lost,
            "unsafe_silent_loss_observed":lost and not signaled,
            "expected_secure_behavior":"stale continuation must be rejected with replay signal"}
    output=json.dumps(result,indent=2)
    if args.out:
        from pathlib import Path
        dst=Path(args.out).expanduser();dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text(output+"\n")
    print(output)
    return 2 if result["unsafe_silent_loss_observed"] else (0 if signaled else 3)
if __name__=="__main__":
    raise SystemExit(main())
