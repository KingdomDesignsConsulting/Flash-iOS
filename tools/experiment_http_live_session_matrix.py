#!/usr/bin/env python3
"""Live resident-session matrix: reuse, streamed eviction rejection, safe replay.

Run only against the hardened experimental server on a dedicated test port.
The script creates/replaces resident sessions and should not share a port
with a real interactive conversation.
"""
import argparse
import json
import pathlib
import time
import urllib.error
import urllib.request
import uuid

def call(base, messages, session=None, create=False, stream=False):
    payload={"model":"qwen3.5","messages":messages,"stream":stream,
             "temperature":0,"reasoning_effort":"off","max_tokens":64}
    if session is not None: payload["session_id"]=session
    if create: payload["flash_session_create"]=True
    req=urllib.request.Request(base.rstrip("/")+"/chat/completions",
        json.dumps(payload).encode(),{"Content-Type":"application/json"})
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=300) as resp:
            status=resp.status
            raw=resp.read().decode("utf-8",errors="replace")
            content_type=resp.headers.get("Content-Type","")
    except urllib.error.HTTPError as exc:
        status=exc.code
        raw=exc.read().decode("utf-8",errors="replace")
        content_type=exc.headers.get("Content-Type","")
    if "text/event-stream" in content_type or raw.startswith("data:"):
        events=[]
        for line in raw.splitlines():
            if line.startswith("data:"):
                data=line[5:].strip()
                if data=="[DONE]": events.append({"done":True}); continue
                try: events.append(json.loads(data))
                except ValueError: events.append({"unparsed":data[:500]})
        return {"status":status,"elapsed_ms":round((time.monotonic()-start)*1000,2),
                "content_type":content_type,"events":events}
    try: data=json.loads(raw)
    except ValueError: data={"unparsed":raw[:600]}
    return {"status":status,"elapsed_ms":round((time.monotonic()-start)*1000,2),
            "content_type":content_type,"body":data}

def text_of(response):
    return response.get("body",{}).get("choices",[{}])[0].get("message",{}).get("content","")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",default="http://127.0.0.1:11243/v1")
    parser.add_argument("--out",default="Testing/HTTP-Prefix-Reuse/live-session-matrix.json")
    args=parser.parse_args()
    code="AXIOM-"+uuid.uuid4().hex[:12].upper()
    a="live-a-"+uuid.uuid4().hex[:16]
    b="live-b-"+uuid.uuid4().hex[:16]
    initial={"role":"user","content":f"Remember the experimental identifier {code}. Acknowledge briefly."}
    follow={"role":"user","content":"What exact experimental identifier did I provide earlier? Answer with just the identifier."}
    result={"sentinel":code,"base":args.base,"tests":{}}
    tests=result["tests"]
    tests["create_a"]=call(args.base,[initial],a,create=True)
    tests["continue_a"]=call(args.base,[follow],a)
    tests["create_b"]=call(args.base,[{"role":"user","content":"Reply READY."}],b,create=True)
    tests["stale_a_nonstream"]=call(args.base,[follow],a)
    tests["stale_a_stream"]=call(args.base,[follow],a,stream=True)
    tests["replay_stateless"]=call(args.base,[initial,
        {"role":"assistant","content":text_of(tests["create_a"])},follow])
    stale=tests["stale_a_nonstream"]
    streaming=tests["stale_a_stream"]
    body=stale.get("body",{})
    events=streaming.get("events",[])
    # Streaming may use HTTP 200 with explicit error event; an absent signal fails.
    signal_events=[e for e in events if e.get("session_invalidated") is True
                   or e.get("resend_full_history") is True
                   or (isinstance(e.get("error"),dict) and
                       e["error"].get("type")=="session_invalidated")]
    checks={
        "create_a_200":tests["create_a"]["status"]==200,
        "active_session_reused":tests["continue_a"]["status"]==200 and
              tests["continue_a"].get("body",{}).get("flash_timings",{}).get("session_reused")==1,
        "active_session_retains_code":code in text_of(tests["continue_a"]),
        "create_b_200":tests["create_b"]["status"]==200,
        "stale_nonstream_409_signal":stale["status"]==409 and
             body.get("session_invalidated") is True and
             body.get("resend_full_history") is True,
        "stale_stream_explicit_signal":bool(signal_events),
        "stateless_replay_recovers_code":tests["replay_stateless"]["status"]==200 and
             code in text_of(tests["replay_stateless"]),
    }
    result["checks"]=checks
    result["passed"]=all(checks.values())
    output=pathlib.Path(args.out).expanduser()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"checks":checks,"passed":result["passed"],"saved":str(output)},indent=2))
    return 0 if result["passed"] else 2

if __name__=="__main__":
    raise SystemExit(main())
